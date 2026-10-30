import logging
import multiprocessing
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

from ..assessments import PhaseSource, PhaseStreamSource
from ..config import Config
from ..datasource import FileDataSource
from ..methods import AEDSEO
from .aedseo_r import RAedseo
from .backend import Backend
from .engine import SeriesResult, assess_series
from .phase import pathogen_phases, stream_rows
from .series import Series, assessed_series
from .store import FeedStore, write_validated

log = logging.getLogger("health_signal.analytics")

_PHASE_COLUMNS = ["location", "pathogen", "period", "method", "phase"]
_STREAM_COLUMNS = ["location", "pathogen", "method", "role", "feed", "series"]
_worker_backend: Backend | None = None


@dataclass
class Summary:
    series: int
    weeks: int
    graded: int
    warnings: list[str] = field(default_factory=list)


def _fit_in_worker(job: tuple) -> SeriesResult:
    # One backend per worker process: an embedded R can't be shared across processes or rebuilt per series cheaply.
    global _worker_backend
    factory, series, weeks, options = job
    if _worker_backend is None:
        _worker_backend = factory()
    return assess_series(series, weeks, _worker_backend, **options)


def assess(config: Config, *, full: bool = False, jobs: int = 1,
           backend: Callable[[], Backend] | None = None) -> Summary:
    """Assess the panel-derived series of every feed with an `assessments` dir and write the contract tables
    (spec §6.3.1); only weeks after each series' last assessed one, unless `full`."""
    if config.data is None:
        raise ValueError("the config has no data.feeds to assess")
    if config.surveillance.year_start_week == 1:
        # aedseo's season ends the week before it starts, and it has no week 0: every fit would fail.
        raise RuntimeError("aedseo can't model a season starting in week 1; set surveillance.year_start_week "
                           "to 2-52 (e.g. 21 for W21-W20 respiratory seasons)")
    factory = backend or RAedseo
    main_backend = factory()
    profiles = {f.id: config.profile(f.profile) for f in config.data.feeds}
    sources = {f.id: FileDataSource(f.dir, profiles[f.id]) for f in config.data.feeds}
    series, refs, warnings = assessed_series(config, sources)
    # Per feed: an emptied or mis-mounted feed dir looks like this, and publishing would replace its good tables
    # with empty ones even while another feed still has series.
    empty = [f.id for f in config.data.feeds if f.assessments and not any(s.feed == f.id for s in series)]
    if empty:
        raise RuntimeError(f"no series to assess in feed {', '.join(empty)}: none of its single-series panels has "
                           f"rows at a selectable location; check the feed's dir"
                           + "".join(f"\n  {w}" for w in warnings))
    method = AEDSEO.name
    analytics = config.analytics
    wave_end = analytics.aedseo.wave_end
    settings = [(method, "year_start_week", str(config.surveillance.year_start_week)),
                (method, "min_seasons", str(analytics.min_seasons)),
                *((method, "wave_pathogen", p) for p in sorted(analytics.wave_pathogens)),
                (method, "steps_with_decrease", str(wave_end.steps_with_decrease)),
                (method, "burden_level_decrease", wave_end.burden_level_decrease),
                (method, "package_version", main_backend.version)]
    # A series shown on several tabs is phased in waves only if every one of those pathogens circulates in waves,
    # so e.g. ILI on the COVID tab doesn't put COVID's wave shading on the influenza tab's chart.
    pathogens: dict[int, set[str]] = {}
    for (pathogen, _, _), s in refs.items():
        pathogens.setdefault(id(s), set()).add(pathogen)
    in_waves = {id(s) for s in series if pathogens[id(s)] <= set(analytics.wave_pathogens)}
    stores = {f.id: FeedStore(f.assessments, profiles[f.id], full=full) for f in config.data.feeds if f.assessments}
    # Which series are phased in waves is recorded too: one moving between waves and seasons (e.g. a panel added
    # to another tab) has stored rows phased the other way, so it needs a full run like any changed setting.
    feed_settings = {feed: settings + sorted((method, "wave_series", _label(s))
                                             for s in series if s.feed == feed and id(s) in in_waves)
                     for feed in stores}
    for feed, store in stores.items():
        # Before any fitting: a mismatch should cost nothing.
        store.check_settings(feed_settings[feed])
        store.check_wave_series([(_label(s), id(s) in in_waves) for s in series
                                 if s.feed == feed and store.last_week(s, method)])
        if full:
            # Every feed's rebuild starts now, so a run that dies before reaching one still resumes it as a
            # rebuild instead of from its old served rows.
            store.checkpoint(feed_settings[feed])

    jobs_to_run: list[tuple[Series, list[str], dict]] = []
    for s in series:
        store = stores[s.feed]
        last = store.resume_week(s, method)
        weeks = [p for p in s.periods if last is None or p > last]
        if weeks:
            options = dict(method=AEDSEO, start_week=config.surveillance.year_start_week,
                           min_seasons=analytics.min_seasons,
                           waves=wave_end if id(s) in in_waves else None,
                           state=store.resume(s, method))
            jobs_to_run.append((s, weeks, options))
    # Whether any series computed now already has fitted history: then weeks no fit can place are the data, not
    # a broken R, and are published ungraded rather than stopping the run.
    history = any(stores[s.feed].last_week(s, method) for s, _, _ in jobs_to_run)
    weeks_done = graded = fitted = 0
    with ProcessPoolExecutor(max_workers=jobs, mp_context=multiprocessing.get_context("spawn")) if jobs > 1 \
            else nullcontext() as pool:
        # As each series finishes, not in submission order, so a long backfill reports and saves it straight away.
        if pool:
            futures = {pool.submit(_fit_in_worker, (factory, s, w, o)): (s, w) for s, w, o in jobs_to_run}
            results = ((*futures[f], f.result()) for f in as_completed(futures))
        else:
            results = ((s, w, assess_series(s, w, main_backend, **o)) for s, w, o in jobs_to_run)
        try:
            for s, weeks, result in results:
                stores[s.feed].add(s, method, result)
                weeks_done += len(weeks)
                graded += result.graded
                fitted += result.fitted
                log.info("%s %s %s %s: %d weeks, %d graded", s.feed, s.location, s.indicator, s.dimensions,
                         len(weeks), result.graded)
                if not result.graded:
                    warnings.append(f"{s.feed} {s.location} {s.indicator} {s.dimensions}: no week could be graded")
                if fitted:
                    # A checkpoint, so an interrupted run resumes from here; only once aedseo has fitted
                    # something, so a broken R's ungraded rows are never what a resume builds on.
                    stores[s.feed].checkpoint(feed_settings[s.feed])
        except BaseException:
            if pool:
                pool.shutdown(cancel_futures=True)   # don't grade the rest only to discard it
            raise
    if weeks_done and not fitted and history:
        warnings.append(f"no new week could be fitted across {len(jobs_to_run)} series; they are published as not "
                        f"graded (if this persists, check R/aedseo)")
    if weeks_done and not fitted and not history:
        # Reported zeros still grade without a fit, so count fits with usable bands: none at all is a systemic
        # failure, not thin data.
        raise RuntimeError(f"no week could be fitted across {len(jobs_to_run)} series; check R/aedseo and the feeds' "
                           f"history (aedseo needs a complete past season)")
    # Every table is drafted and validated before any served one is replaced, so a failure anywhere (a phase
    # stream, one feed's table) leaves the dashboard on its last complete run.
    files = {}
    for feed, store in stores.items():
        files |= store.files(feed_settings[feed])
    phase_files, check_phases = _phase_files(config, refs, stores, profiles) if analytics.phase_streams else ({}, None)
    files |= phase_files

    def validate(drafts):
        for store in stores.values():
            store.validate(drafts)
        if check_phases:
            check_phases(drafts)

    write_validated(files, validate)
    for store in stores.values():
        store.discard_checkpoint()
    for warning in warnings:
        log.warning(warning)
    log.info("assessed %d series: %d weeks computed, %d graded", len(series), weeks_done, graded)
    return Summary(len(series), weeks_done, graded, warnings)


def _label(s: Series) -> str:
    return f"{s.location} {s.indicator} {urlencode(sorted(s.dimensions.items()))}"


def _phase_files(config: Config, refs: dict, stores: dict[str, FeedStore], profiles: dict):
    """The phase tables as write_validated files, and how to validate their drafts."""
    phases, streams = [], []
    for entry in config.analytics.phase_streams:
        by_role, resolved = {}, {}
        for role, ref in entry.streams.items():
            s = refs.get((entry.pathogen, entry.location, ref))
            if s is None:
                raise ValueError(f"analytics.phase_streams {entry.pathogen}/{entry.location}: panel {ref!r} has no "
                                 f"assessed series at {entry.location}")
            by_role[role] = stores[s.feed].phases(s, entry.method)
            resolved[role] = s
        phases += pathogen_phases(entry, by_role, waves=entry.pathogen in config.analytics.wave_pathogens)
        streams += stream_rows(entry, resolved)
    phase_path, stream_path = Path(config.data.phases), Path(config.data.phase_streams)
    files = {
        phase_path: (_PHASE_COLUMNS, [[r[c] for c in _PHASE_COLUMNS]
                                      for r in sorted(phases, key=lambda r: [r[c] for c in _PHASE_COLUMNS])]),
        stream_path: (_STREAM_COLUMNS, [[r[c] for c in _STREAM_COLUMNS]
                                        for r in sorted(streams, key=lambda r: [r[c] for c in _STREAM_COLUMNS])]),
    }
    return files, lambda drafts: (PhaseSource(drafts[phase_path]), PhaseStreamSource(drafts[stream_path], profiles))
