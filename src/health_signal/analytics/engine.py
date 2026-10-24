import math
from dataclasses import dataclass
from datetime import date

from ..methods import Method
from .backend import Backend, FitError, FitInput
from .rules import SeasonState, completed_seasons, level_for, season_phase, trend_for, wave_phase
from .series import Series


@dataclass
class SeriesResult:
    rows: list[dict]
    bounds: list[tuple[str, tuple[float, ...]]]   # (week, lower bounds of the levels above the lowest)
    state: SeasonState
    graded: int


def _monday(period: str) -> date:
    year, week = period.split("-W")
    return date.fromisocalendar(int(year), int(week), 1)


def assess_series(series: Series, weeks: list[str], backend: Backend, *, method: Method, start_week: int,
                  min_seasons: int, waves: bool, state: SeasonState) -> SeriesResult:
    """Grade `weeks` of one series, each from its data up to and including that week (spec §6.3.1)."""
    index = {p: i for i, p in enumerate(series.periods)}
    rows, bounds, graded = [], [], 0
    for week in weeks:
        n = index[week] + 1
        data = FitInput(tuple(_monday(p) for p in series.periods[:n]), tuple(series.values[:n]),
                        tuple(series.exposure[:n]), series.per, series.scale, series.kind, start_week, waves)
        value = series.values[n - 1]
        provisional = completed_seasons(series.periods[:n], start_week) < min_seasons
        try:
            fit = backend.fit(data)
        except FitError:
            if value == 0:
                # A reported zero is the lowest burden even where aedseo can't fit (greece-public-health
                # grades it so); a positive value it can't place gets no row.
                rows.append({"period": week, "level": method.levels[0], "provisional": provisional,
                             "trend": "inconclusive", "growth_rate": None, "growth_lower": None,
                             "growth_upper": None, "phase": None})
                graded += 1
            continue
        level = level_for(value, fit.thresholds, method.levels)
        trend, growth = trend_for(*fit.growth)
        if waves:
            phase = wave_phase(fit.in_wave)
        else:
            phase, state = season_phase(state, week, value, fit.thresholds[0], fit.alarm)
        rows.append({"period": week, "level": level,
                     "provisional": provisional,
                     "trend": trend, "growth_rate": growth[0] if growth else None,
                     "growth_lower": growth[1] if growth else None, "growth_upper": growth[2] if growth else None,
                     "phase": phase})
        if all(math.isfinite(t) for t in fit.thresholds):
            bounds.append((week, fit.thresholds))
        graded += level is not None
    return SeriesResult(rows, bounds, state, graded)
