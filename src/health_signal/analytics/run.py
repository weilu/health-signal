import logging
import multiprocessing
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

from ..assessments import PHASE_COLUMNS, PHASE_OPTIONAL, STREAM_COLUMNS, PhaseSource, PhaseStreamSource
from ..config import Config
from ..datasource import FileDataSource
from ..methods import AEDSEO, MEM, METHODS
from ..profile import Profile
from .aedseo_r import RAedseo
from .backend import Backend
from .engine import SeriesResult, assess_series
from .mem_engine import assess_mem_series
from .phase import pathogen_phases, stream_rows
from .series import Series, assessed_series
from .store import FeedStore, lock_assessments, write_validated

log = logging.getLogger("health_signal.analytics")

# One backend per method per worker process: an embedded R can't be shared across processes or rebuilt per series
# cheaply.
_worker_backends: dict[str, object] = {}


@dataclass
class Summary:
    series: int
    weeks: int
    graded: int
    warnings: list[str] = field(default_factory=list)


@dataclass
class _Job:
    method: str
    grade: Callable[..., SeriesResult]   # the method's per-series step
    series: Series
    weeks: list[str]
    options: dict


def _fit_in_worker(job: tuple) -> SeriesResult:
    factory, j = job
    if j.method not in _worker_backends:
        _worker_backends[j.method] = factory()
    return j.grade(j.series, j.weeks, _worker_backends[j.method], **j.options)


def _default_backends() -> dict[str, Callable]:
    return {"aedseo": RAedseo}


def assess(config: Config, *, full: bool = False, method: str | None = None, jobs: int = 1,
           backend: Callable[[], Backend] | dict[str, Callable] | None = None) -> Summary:
    """Assess the panel-derived series of every feed with an `assessments` dir and write the contract tables
    (spec §6.3.1), with each graded method; only weeks after each series' last assessed one, unless `full`
    (every method's, or `method`'s alone). `backend`: a factory per method, or aedseo's alone."""
    if config.data is None:
        raise ValueError("the config has no data.feeds to assess")
    if method is not None and method not in config.analytics.methods:
        raise ValueError(f"{method!r} isn't one of analytics.methods {config.analytics.methods}")
    if "aedseo" in config.analytics.methods and config.surveillance.year_start_week == 1:
        # aedseo's season ends the week before it starts, and it has no week 0: every fit would fail.
        raise RuntimeError("aedseo can't model a season starting in week 1; set surveillance.year_start_week "
                           "to 2-52 (e.g. 21 for W21-W20 respiratory seasons)")
    backends = _default_backends() | (backend if isinstance(backend, dict) else {"aedseo": backend} if backend else {})
    with lock_assessments([f.assessments for f in config.data.feeds if f.assessments]):
        return _assess(config, (method or True) if full else False, jobs, backends)


def graded_series(config: Config, method: str, series: list[Series]) -> list[Series]:
    """The series `method` grades: those its allowlist names, or all. A method without phases assumes one epidemic a
    season, so it leaves out a series graded in waves, and refuses one named for it."""
    allow = config.method_panels(method)
    chosen = series if allow is None else [s for s in series if s.panels & allow]
    if METHODS[method].phases:
        return chosen
    waves = set(config.analytics.wave_pathogens)
    in_waves = [s for s in chosen if s.pathogens <= waves]
    if allow is not None and in_waves:
        raise ValueError(f"analytics.{method}.panels: {_label(in_waves[0])} is graded in waves, "
                         f"which {method} can't model (it assumes one epidemic a season)")
    return [s for s in chosen if s not in in_waves]


def _modelling_rules(method: str, profile: Profile) -> list[tuple[str, str, str]]:
    # The profile, extension included, decides how each series is fitted, so a change to it needs --full.
    rules = [("count_unit", u) for u in profile.count_units]
    rules += [("censored_quality", q) for q in profile.censored_qualities]
    rules += [("denominator", f"{d.rate} ({d.unit or 'any unit'}) / {d.denominator} per {d.per:g}")
              for d in profile.denominators]
    return sorted((method, setting, value) for setting, value in rules)


def _in_waves(config: Config, s: Series) -> bool:
    # Only if every tab showing it is a wave pathogen: ILI on the COVID tab keeps influenza's seasons.
    return s.pathogens <= set(config.analytics.wave_pathogens)


def _aedseo_part(config, version, chosen, stores, profiles):
    """aedseo's settings per feed and its jobs: seasons or waves, resumed from each series' phase state."""
    method, analytics = AEDSEO.name, config.analytics
    wave_end = analytics.aedseo.wave_end
    settings = [(method, setting, str(value)) for setting, value in {
        "year_start_week": config.surveillance.year_start_week, "min_seasons": analytics.min_seasons,
        "steps_with_decrease": wave_end.steps_with_decrease, "burden_level_decrease": wave_end.burden_level_decrease,
        "package_version": version,
        # How a wave may start (rules.wave_phase): tables phased under an earlier rule can't be extended.
        "wave_start": "own_alarm"}.items()]
    settings += [(method, "wave_pathogen", p) for p in sorted(analytics.wave_pathogens)]
    # Phasing is recorded per series: one switching between waves and seasons needs --full.
    feed_settings = {feed: settings + _modelling_rules(method, profiles[feed])
                     + sorted((method, "wave_series", _label(s)) for s in chosen if s.feed == feed and _in_waves(config, s))
                     + stores[feed].kept_wave_series({_label(s) for s in chosen if s.feed == feed})
                     for feed in stores}
    for feed, store in stores.items():
        store.check_wave_series([(_label(s), _in_waves(config, s)) for s in chosen
                                 if s.feed == feed and store.last_week(s, method)])
    common = dict(method=AEDSEO, start_week=config.surveillance.year_start_week, min_seasons=analytics.min_seasons)
    jobs = []
    for s in chosen:
        store = stores[s.feed]
        last = store.resume_week(s, method)
        weeks = [p for p in s.periods if last is None or p > last]
        if weeks:
            jobs.append(_Job(method, assess_series, s, weeks, {**common, "waves": wave_end if _in_waves(config, s) else None,
                                                              "state": store.resume(s, method)}))
    return feed_settings, jobs


def _mem_part(config, version, chosen, stores, profiles):
    """MEM's settings per feed and its jobs: thresholds per season in MEM's own window, no phases."""
    method, mem = MEM.name, config.analytics.mem
    settings = [(method, setting, str(value)) for setting, value in {
        "season_start_week": mem.season_start_week, "seasons": mem.seasons,
        "min_seasons": config.analytics.min_seasons, "package_version": version}.items()]
    # Which values are stand-ins decides what MEM sees as missing; it has no exposure model, so denominators don't.
    feed_settings = {feed: settings + sorted((method, "censored_quality", q) for q in profiles[feed].censored_qualities)
                     for feed in stores}
    options = dict(start_week=mem.season_start_week, seasons=mem.seasons, min_seasons=config.analytics.min_seasons)
    jobs = []
    for s in chosen:
        last = stores[s.feed].resume_week(s, method)
        weeks = [p for p in s.periods if last is None or p > last]
        if weeks:
            jobs.append(_Job(method, assess_mem_series, s, weeks, options))
    return feed_settings, jobs


_PARTS = {"aedseo": _aedseo_part, "mem": _mem_part}


def _assess(config: Config, full: bool | str, jobs: int, backends: dict[str, Callable]) -> Summary:
    profiles = config.feed_profiles()
    sources = {f.id: FileDataSource(f.dir, profiles[f.id]) for f in config.data.feeds}
    series, refs, warnings = assessed_series(config, sources)
    # Per feed: an emptied or mis-mounted feed dir looks like this, and publishing would replace its good tables
    # with empty ones even while another feed still has series.
    empty = [f.id for f in config.data.feeds if f.assessments and not any(s.feed == f.id for s in series)]
    if empty:
        raise RuntimeError(f"no series to assess in feed {', '.join(empty)}: none of its single-series panels has "
                           f"rows at a selectable location; check the feed's dir"
                           + "".join(f"\n  {w}" for w in warnings))
    stores = {f.id: FeedStore(f.assessments, profiles[f.id], full=full) for f in config.data.feeds if f.assessments}
    feed_settings = {feed: [] for feed in stores}
    jobs_to_run: list[tuple[Callable, _Job]] = []
    for method in config.analytics.methods:
        if method not in backends:
            raise RuntimeError(f"no backend for method {method!r}")
        factory = backends[method]
        part_settings, part_jobs = _PARTS[method](config, factory().version, graded_series(config, method, series),
                                                  stores, profiles)
        for feed, store in stores.items():
            store.check_settings(part_settings[feed], method)   # before any fitting, so a mismatch costs nothing
            feed_settings[feed] += part_settings[feed]
        jobs_to_run += [(factory, j) for j in part_jobs]
    if full:
        for feed, store in stores.items():
            # Every feed's rebuild starts now, so dying before a feed still resumes it as a rebuild.
            store.checkpoint(feed_settings[feed])
    # Slowest first (wave fits, then the longest), so the run doesn't end on one worker's long series.
    jobs_to_run.sort(key=lambda job: (job[1].options.get("waves") is None, -len(job[1].weeks)))
    # With prior fits, weeks no fit can place are the data (a broken R raises BackendError instead).
    history = any(stores[j.series.feed].last_week(j.series, j.method) for _, j in jobs_to_run)
    weeks_done = graded = fitted = 0
    with ProcessPoolExecutor(max_workers=jobs, mp_context=multiprocessing.get_context("spawn")) if jobs > 1 \
            else nullcontext() as pool:
        # As each series finishes, not in submission order, so a long backfill reports and saves it straight away.
        if pool:
            futures = {pool.submit(_fit_in_worker, job): job[1] for job in jobs_to_run}
            results = ((futures[f], f.result()) for f in as_completed(futures))
        else:
            local: dict[str, object] = {}
            results = ((j, j.grade(j.series, j.weeks, local.setdefault(j.method, factory()), **j.options))
                       for factory, j in jobs_to_run)
        try:
            for j, result in results:
                s = j.series
                stores[s.feed].add(s, j.method, result)
                weeks_done += len(j.weeks)
                graded += result.graded
                fitted += result.fitted
                log.info("%s %s %s %s %s: %d weeks, %d graded", j.method, s.feed, s.location, s.indicator,
                         s.dimensions, len(j.weeks), result.graded)
                if not result.graded:
                    warnings.append(f"{j.method} {s.feed} {s.location} {s.indicator} {s.dimensions}: "
                                    f"no week could be graded")
                if fitted:   # checkpoint only after a real fit, so a resume never builds on unfitted rows
                    stores[s.feed].checkpoint(feed_settings[s.feed])
        except BaseException:
            if pool:
                pool.shutdown(cancel_futures=True)   # don't grade the rest only to discard it
            raise
    if weeks_done and not fitted:
        if not history:   # nothing fitted and nothing to stand on: publishing would replace good tables
            raise RuntimeError(f"no week could be fitted across {len(jobs_to_run)} series; check R and the methods' "
                               f"packages, and the feeds' history (each method needs complete past seasons)")
        warnings.append(f"no new week could be fitted across {len(jobs_to_run)} series (too little usable history); "
                        f"they are published as not graded and fitted again next run")
    # All drafted and validated before any served table is replaced: a failure anywhere leaves the last run up.
    files = {}
    for feed, store in stores.items():
        files |= store.files(feed_settings[feed])
    with_phases = AEDSEO.name in config.analytics.methods and config.analytics.phase_streams
    phase_files, check_phases = _phase_files(config, refs, stores, profiles) if with_phases else ({}, None)
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


def _table(columns: list[str], rows: list[dict]) -> tuple[list[str], list[list]]:
    return columns, sorted([row[c] for c in columns] for row in rows)


def _label(s: Series) -> str:
    return f"{s.location} {s.indicator} {urlencode(sorted(s.dimensions.items()))}"


def _phase_files(config: Config, refs: dict, stores: dict[str, FeedStore], profiles: dict):
    """The phase tables as write_validated files, and how to validate their drafts."""
    phases, streams = [], []
    for entry in config.analytics.phase_streams:
        by_role, provisional, resolved = {}, {}, {}
        for role, ref in entry.streams.items():
            s = refs.get((entry.pathogen, entry.location, ref))
            if s is None:
                raise ValueError(f"analytics.phase_streams {entry.pathogen}/{entry.location}: panel {ref!r} has no "
                                 f"assessed series at {entry.location}")
            by_role[role] = stores[s.feed].phases(s, entry.method)
            provisional[role] = stores[s.feed].provisional(s, entry.method)
            resolved[role] = s
        phases += pathogen_phases(entry, by_role, waves=entry.pathogen in config.analytics.wave_pathogens,
                                  provisional=provisional)
        streams += stream_rows(entry, resolved)
    phase_path, stream_path = Path(config.data.phases), Path(config.data.phase_streams)
    files = {phase_path: _table([*PHASE_COLUMNS, *PHASE_OPTIONAL], phases), stream_path: _table(STREAM_COLUMNS, streams)}
    return files, lambda drafts: (PhaseSource(drafts[phase_path]), PhaseStreamSource(drafts[stream_path], profiles))
