import math
from dataclasses import dataclass
from datetime import date

from ..methods import Method
from .backend import Backend, FitError, FitInput
from .rules import SeasonState, completed_seasons, level_for, season_phase, trend_for, wave_phase
from .series import Series


_NO_BANDS = (math.nan,) * 4


@dataclass
class SeriesResult:
    rows: list[dict]
    bounds: list[tuple[str, tuple[float, ...]]]   # (week, lower bounds of the levels above the lowest)
    state: SeasonState
    graded: int
    fitted: int = 0   # weeks aedseo could fit at all; zero across a run means a systemic failure


def _usable(thresholds: tuple[float, ...]) -> tuple[float, ...]:
    # Bands that are partly missing or don't rise can't grade, phase or draw consistently: treat them as none,
    # so the grade, the phase and the stored bounds always agree (and an incremental resume finds its floor).
    finite = all(math.isfinite(t) for t in thresholds)
    return thresholds if finite and all(a < b for a, b in zip(thresholds, thresholds[1:])) else _NO_BANDS


def _monday(period: str) -> date:
    year, week = period.split("-W")
    return date.fromisocalendar(int(year), int(week), 1)


def assess_series(series: Series, weeks: list[str], backend: Backend, *, method: Method, start_week: int,
                  min_seasons: int, waves: bool, state: SeasonState) -> SeriesResult:
    """Grade `weeks` of one series, each from its data up to and including that week (spec §6.3.1)."""
    index = {p: i for i, p in enumerate(series.periods)}
    fitted_values = [math.nan if c else v
                     for v, c in zip(series.values, series.censored or [False] * len(series.values))]
    rows, bounds, graded, fitted = [], [], 0, 0
    for week in weeks:
        n = index[week] + 1
        data = FitInput(tuple(_monday(p) for p in series.periods[:n]), tuple(fitted_values[:n]),
                        tuple(series.exposure[:n]), series.per, series.scale, series.kind, start_week, waves)
        value = series.values[n - 1]
        provisional = completed_seasons(series.periods[:n], start_week) < min_seasons
        try:
            fit = backend.fit(data)
        except FitError:
            # Still a row, so a tile describes this week rather than an older graded one. A reported zero is
            # the lowest burden even where aedseo can't fit; a positive value it can't place is left ungraded.
            level = method.levels[0] if value == 0 else None
            rows.append({"period": week, "level": level, "provisional": provisional, "trend": "inconclusive",
                         "growth_rate": None, "growth_lower": None, "growth_upper": None, "phase": None})
            graded += level is not None
            continue
        fitted += 1
        thresholds = _usable(fit.thresholds)
        level = level_for(value, thresholds, method.levels)
        trend, growth = trend_for(*fit.growth)
        if waves:
            phase = wave_phase(fit.in_wave)
        else:
            phase, state = season_phase(state, week, value, thresholds[0], fit.alarm)
        rows.append({"period": week, "level": level,
                     "provisional": provisional,
                     "trend": trend, "growth_rate": growth[0] if growth else None,
                     "growth_lower": growth[1] if growth else None, "growth_upper": growth[2] if growth else None,
                     "phase": phase})
        if thresholds is not _NO_BANDS:
            bounds.append((week, thresholds))
        graded += level is not None
    return SeriesResult(rows, bounds, state, graded, fitted)
