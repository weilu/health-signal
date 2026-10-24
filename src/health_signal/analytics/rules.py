import math
from collections import Counter
from dataclasses import dataclass
from datetime import date

# A log-growth rate this large is a degenerate fit or R's NA_integer_ sentinel (-2^31, finite), not a
# rate: real weekly log-growth is O(1), and exp() overflows above ~709.
MAX_ABS_LOG_GROWTH = 700
MIN_SEASON_WEEKS = 30  # a season with fewer observed weeks doesn't count as completed history


def _week(period: str) -> tuple[int, int]:
    year, week = period.split("-W")
    return int(year), int(week)


def season_of(period: str, start_week: int) -> int:
    year, week = _week(period)
    return year if week >= start_week else year - 1


def completed_seasons(periods: list[str], start_week: int) -> int:
    counts = Counter(season_of(p, start_week) for p in periods)
    if not counts:
        return 0
    current = max(counts)
    return sum(1 for season, n in counts.items() if season != current and n >= MIN_SEASON_WEEKS)


def level_for(value: float, thresholds: tuple[float, ...], levels: list[str]) -> str | None:
    if not all(math.isfinite(t) for t in thresholds):
        # aedseo returns NA bands for a series collapsed to zero; a reported zero is still the lowest
        # burden, but a positive value can't be placed without bands.
        return levels[0] if value == 0 else None
    return levels[sum(1 for t in thresholds if value >= t)]


def trend_for(rate: float, lower: float, upper: float) -> tuple[str, tuple[float, float, float] | None]:
    if not all(math.isfinite(x) and abs(x) < MAX_ABS_LOG_GROWTH for x in (rate, lower, upper)):
        return "inconclusive", None
    growth = (math.exp(rate) - 1, math.exp(lower) - 1, math.exp(upper) - 1)
    return ("increasing" if lower > 0 else "decreasing" if upper < 0 else "stable"), growth


def exposure_scale(values: list[float]) -> float:
    # aedseo derives counts as value × exposure and rounds them; too small a constant rounds rates to zero
    # counts, while any constant leaves thresholds unchanged and cancels in the growth model.
    positive = [v for v in values if v > 0]
    if not positive:
        return 1.0
    return float(10 ** max(0, math.ceil(math.log10(100 / min(positive)))))


def weeks_between(a: str, b: str) -> int:
    (year_a, week_a), (year_b, week_b) = _week(a), _week(b)
    return (date.fromisocalendar(year_b, week_b, 1) - date.fromisocalendar(year_a, week_a, 1)).days // 7


MAX_DIP = 1      # below-threshold weeks a season survives: a brief lull, not its end
MAX_MISSING = 8  # missing weeks a season survives: a reporting outage, not its end


@dataclass(frozen=True)
class SeasonState:
    in_season: bool = False
    below: int = 0
    last_period: str | None = None


def season_phase(state: SeasonState, period: str, value: float, floor: float,
                 alarm: bool | None) -> tuple[str | None, SeasonState]:
    # As of `period`, without hindsight: greece-public-health bridges a one-week dip after the fact; here
    # the dip week reads in season and the second week below ends it, so a season ends a week late.
    if not math.isfinite(floor):
        return None, state
    gap = weeks_between(state.last_period, period) - 1 if state.last_period else 0
    in_season = state.in_season and gap <= MAX_MISSING
    if value >= floor:
        if in_season or alarm:
            return "in_season", SeasonState(True, 0, period)
        return "out_of_season", SeasonState(False, 0, period)
    if in_season and state.below < MAX_DIP:
        return "in_season", SeasonState(True, state.below + 1, period)
    return "out_of_season", SeasonState(False, 0, period)


def wave_phase(in_wave: bool | None) -> str | None:
    return None if in_wave is None else "in_wave" if in_wave else "between_waves"
