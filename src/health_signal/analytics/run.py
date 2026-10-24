import logging
import multiprocessing
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from ..assessments import PhaseSource, PhaseStreamSource
from ..config import Config
from ..datasource import FileDataSource
from ..methods import AEDSEO
from ..profile import PROFILES
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
    profiles = {f.id: PROFILES[f.profile] for f in config.data.feeds}
    sources = {f.id: FileDataSource(f.dir, profiles[f.id]) for f in config.data.feeds}
    series, refs, warnings = assessed_series(config, sources)
    method = AEDSEO.name
    analytics = config.analytics
    settings = [(method, "year_start_week", str(config.surveillance.year_start_week)),
                (method, "min_seasons", str(analytics.min_seasons)),
                *((method, "wave_pathogen", p) for p in sorted(analytics.wave_pathogens)),
                (method, "package_version", main_backend.version)]
    stores = {f.id: FeedStore(f.assessments, profiles[f.id], full=full) for f in config.data.feeds if f.assessments}
    for store in stores.values():
        store.check_settings(settings)   # before any fitting: a mismatch should cost nothing

    # A series shown on several tabs is phased in waves only if every one of those pathogens circulates in waves,
    # so e.g. ILI on the COVID tab doesn't put COVID's wave shading on the influenza tab's chart.
    pathogens: dict[int, set[str]] = {}
    for (pathogen, _, _), s in refs.items():
        pathogens.setdefault(id(s), set()).add(pathogen)
    jobs_to_run: list[tuple[Series, list[str], dict]] = []
    for s in series:
        store = stores[s.feed]
        last = store.last_week(s, method)
        weeks = [p for p in s.periods if last is None or p > last]
        if weeks:
            options = dict(method=AEDSEO, start_week=config.surveillance.year_start_week,
                           min_seasons=analytics.min_seasons,
                           waves=pathogens[id(s)] <= set(analytics.wave_pathogens),
                           state=store.resume(s, method))
            jobs_to_run.append((s, weeks, options))
    weeks_done = graded = fitted = 0
    with ProcessPoolExecutor(max_workers=jobs, mp_context=multiprocessing.get_context("spawn")) if jobs > 1 \
            else nullcontext() as pool:
        # Lazily, so a long backfill reports each series as it finishes rather than all at the end.
        results = (pool.map(_fit_in_worker, [(factory, s, w, o) for s, w, o in jobs_to_run]) if pool
                   else (assess_series(s, w, main_backend, **o) for s, w, o in jobs_to_run))
        for (s, weeks, _), result in zip(jobs_to_run, results):
            stores[s.feed].add(s, method, result)
            weeks_done += len(weeks)
            graded += result.graded
            fitted += result.fitted
            log.info("%s %s %s %s: %d weeks, %d graded", s.feed, s.location, s.indicator, s.dimensions,
                     len(weeks), result.graded)
            if not result.graded:
                warnings.append(f"{s.feed} {s.location} {s.indicator} {s.dimensions}: no week could be graded")
    if weeks_done and not fitted:
        # Reported zeros still grade without a fit, so count fits: none at all is a systemic failure, not thin data.
        raise RuntimeError(f"no week could be fitted across {len(jobs_to_run)} series; check R/aedseo and the feeds' "
                           f"history (aedseo needs a complete past season)")
    for store in stores.values():
        store.write(settings)
    if analytics.phase_streams:
        _write_phases(config, refs, stores, profiles)
    for warning in warnings:
        log.warning(warning)
    log.info("assessed %d series: %d weeks computed, %d graded", len(series), weeks_done, graded)
    return Summary(len(series), weeks_done, graded, warnings)


def _write_phases(config: Config, refs: dict, stores: dict[str, FeedStore], profiles: dict) -> None:
    phases, streams = [], []
    for entry in config.analytics.phase_streams:
        by_role = {}
        for role, ref in entry.streams.items():
            s = refs.get((entry.pathogen, entry.location, ref))
            if s is None:
                raise ValueError(f"analytics.phase_streams {entry.pathogen}/{entry.location}: panel {ref!r} has no "
                                 f"assessed series at {entry.location}")
            by_role[role] = stores[s.feed].phases(s, entry.method)
        phases += pathogen_phases(entry, by_role, waves=entry.pathogen in config.analytics.wave_pathogens)
        streams += stream_rows(entry, config)
    phase_path, stream_path = Path(config.data.phases), Path(config.data.phase_streams)
    files = {
        phase_path: (_PHASE_COLUMNS, [[r[c] for c in _PHASE_COLUMNS]
                                      for r in sorted(phases, key=lambda r: [r[c] for c in _PHASE_COLUMNS])]),
        stream_path: (_STREAM_COLUMNS, [[r[c] for c in _STREAM_COLUMNS]
                                        for r in sorted(streams, key=lambda r: [r[c] for c in _STREAM_COLUMNS])]),
    }
    write_validated(files, lambda drafts: (PhaseSource(drafts[phase_path]),
                                           PhaseStreamSource(drafts[stream_path], profiles)))
