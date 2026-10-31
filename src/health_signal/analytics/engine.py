import math
from dataclasses import dataclass

from ..assessments import GROWTH
from ..config import WaveEnd
from ..methods import Method
from .backend import NO_BANDS, Backend, FitError, FitInput, WeekFit
from .rules import SeasonState, completed_seasons, level_for, monday, season_phase, trend_for, value_scale, wave_phase
from .series import Series


# A week aedseo can't fit is graded like one it fits without bands: still a row, so a tile describes this week
# rather than an older one (a reported zero is the lowest burden either way).
_NO_FIT = WeekFit(NO_BANDS, (math.nan,) * 3, None, None)


@dataclass
class SeriesResult:
    rows: list[dict]
    bounds: list[tuple[str, tuple[float, ...]]]   # (week, lower bounds of the levels above the lowest)
    state: SeasonState
    graded: int
    fitted: int = 0   # weeks aedseo fitted with usable bands; zero across a run means a systemic failure


def _usable(thresholds: tuple[float, ...]) -> tuple[float, ...]:
    # Bands that are partly missing or don't rise can't grade, phase or draw consistently: treat them as none,
    # so the grade, the phase and the stored bounds always agree (and an incremental resume finds its floor).
    finite = all(math.isfinite(t) for t in thresholds)
    return thresholds if finite and all(a < b for a, b in zip(thresholds, thresholds[1:])) else NO_BANDS


def assess_series(series: Series, weeks: list[str], backend: Backend, *, method: Method, start_week: int,
                  min_seasons: int, waves: WaveEnd | None, state: SeasonState) -> SeriesResult:
    """Grade `weeks` of one series, each from its data up to and including that week (spec §6.3.1)."""
    index = {p: i for i, p in enumerate(series.periods)}
    fitted_values = [math.nan if c else v
                     for v, c in zip(series.values, series.censored or [False] * len(series.values))]
    rows, bounds, graded, fitted = [], [], 0, 0
    for week in weeks:
        n = index[week] + 1
        # From this week's history only, so a later, smaller value can't change how this week was fitted.
        scale = value_scale(fitted_values[:n]) if series.scaled else 1.0
        data = FitInput(tuple(monday(p) for p in series.periods[:n]), tuple(fitted_values[:n]),
                        tuple(series.exposure[:n]), series.per, scale, series.kind, start_week, waves)
        value = series.values[n - 1]
        try:
            fit = backend.fit(data)
        except FitError:
            fit = _NO_FIT
        thresholds = _usable(fit.thresholds)
        has_bands = thresholds is not NO_BANDS
        level = level_for(value, thresholds, method.levels)
        trend, growth = trend_for(*fit.growth)
        if waves is not None:
            # As for seasons: a week without usable bands has no level, so it says nothing about waves either.
            phase = wave_phase(fit.in_wave) if has_bands else None
        else:
            phase, state = season_phase(state, week, value, thresholds[0], fit.alarm)
        rows.append({"period": week, "level": level,
                     "provisional": completed_seasons(series.periods[:n], start_week) < min_seasons,
                     "trend": trend, **dict(zip(GROWTH, growth or (None,) * 3)), "phase": phase})
        if has_bands:
            bounds.append((week, thresholds))
        fitted += has_bands
        graded += level is not None
    return SeriesResult(rows, bounds, state, graded, fitted)
