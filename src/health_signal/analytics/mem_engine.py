"""Grading a series with the Moving Epidemic Method: one fit per season from the seasons before it, then each week."""
import math

from ..methods import MEM
from .backend import NO_BANDS, FitError, MemBackend, MemFit
from .engine import SeriesResult
from .rules import MIN_SEASON_WEEKS, SeasonState, level_for, mem_trend, season_of, season_phase, weeks_between
from .series import Series

SLOTS = 53


def _slot(period: str, start_week: int) -> int:
    # Week numbers in season order, week 53 its own slot, so week 1 lines up in every season.
    week = int(period.split("-W")[1])
    return week - start_week if week >= start_week else SLOTS - start_week + week


def _graded_bounds(thresholds: tuple[float, ...]) -> tuple[float, ...]:
    # mem doesn't order its thresholds: after low-peaked seasons the medium one can fall below the epidemic one, and
    # MEM then grades every epidemic week at least medium. Raising each to the one below grades the same and draws.
    if not all(math.isfinite(t) for t in thresholds):
        return NO_BANDS
    bounds, floor = [], -math.inf
    for t in thresholds:
        floor = max(floor, t)
        bounds.append(floor)
    return tuple(bounds)


def assess_mem_series(series: Series, weeks: list[str], backend: MemBackend, *, start_week: int, seasons: int,
                      min_seasons: int, state: SeasonState) -> SeriesResult:
    """Grade `weeks` of one series, each by the thresholds MEM sets for its season from the seasons before it."""
    unmodelled = [math.isnan(e) for e in series.exposure] or [False] * len(series.values)
    censored = series.censored or [False] * len(series.values)
    # MEM has no exposure model: a stand-in or a week without its denominator is simply missing.
    fitted = [math.nan if c or u else v for v, c, u in zip(series.values, censored, unmodelled)]
    by_season: dict[int, list[float]] = {}
    for period, value in zip(series.periods, fitted):
        if not math.isnan(value):
            by_season.setdefault(season_of(period, start_week), [math.nan] * SLOTS)[_slot(period, start_week)] = value
    complete = sorted(s for s, values in by_season.items() if sum(not math.isnan(v) for v in values) >= MIN_SEASON_WEEKS)
    index = {p: i for i, p in enumerate(series.periods)}
    fits: dict[int, tuple[MemFit | None, int]] = {}
    rows, bounds, graded, fitted_weeks = [], [], 0, 0
    for week in weeks:
        season = season_of(week, start_week)
        if season not in fits:
            history = [by_season[s] for s in complete if s < season][-seasons:]
            try:
                fits[season] = (backend.fit_season(history) if history else None, len(history))
            except FitError:
                fits[season] = (None, len(history))
        fit, behind = fits[season]
        thresholds = _graded_bounds(fit.thresholds) if fit else NO_BANDS
        i = index[week]
        value = series.values[i]
        level = None if unmodelled[i] or thresholds is NO_BANDS else level_for(value, thresholds, MEM.levels)
        previous = fitted[i - 1] if i and weeks_between(series.periods[i - 1], week) == 1 else None
        trend = mem_trend(fitted[i], previous, thresholds[0], fit.delta, fit.eta) if level else "not_assessed"
        # MEM's epidemic starts on the week over its threshold, so crossing it is the onset; the season then runs as
        # aedseo's do, across a one-week dip or a reporting gap. A week MEM can't place says nothing about seasons.
        phase = None
        if level is not None:
            phase, state = season_phase(state, week, value, thresholds[0], value >= thresholds[0])
        rows.append({"period": week, "level": level, "provisional": behind < min_seasons, "trend": trend,
                     "growth_rate": None, "growth_lower": None, "growth_upper": None, "phase": phase})
        if thresholds is not NO_BANDS:
            bounds.append((week, thresholds))
            fitted_weeks += 1
        graded += level is not None
    return SeriesResult(rows, bounds, state, graded, fitted_weeks)
