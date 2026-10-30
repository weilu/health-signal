from dataclasses import dataclass
from datetime import date
from typing import Protocol

from ..config import WaveEnd


class BackendError(RuntimeError):
    """R or aedseo failed, not the data (aedseo reports too little history as an NA threshold, never an error):
    the run stops before publishing rather than grading the week "not graded"."""


class FitError(Exception):
    """aedseo can't fit this series as of this week (too little history): the week is left ungraded."""


@dataclass(frozen=True)
class FitInput:
    dates: tuple[date, ...]       # Mondays of the observed weeks, up to and including the week assessed
    values: tuple[float, ...]
    exposure: tuple[float, ...]   # empty for counts
    per: float
    scale: float                  # values are fitted × scale; thresholds come back in the values' own units
    kind: str                     # "count" or "incidence"
    season_start: int
    waves: WaveEnd | None         # how a wave ends; None for a series phased in seasons


@dataclass(frozen=True)
class WeekFit:
    # aedseo's 'very low', 'low', 'medium', 'high' values: the upper edges of those levels (its own plot draws
    # them so), hence the lower bounds of low..very_high. NaN where aedseo has no bands yet.
    thresholds: tuple[float, float, float, float]
    growth: tuple[float, float, float]   # log-scale rate, lower, upper; NaN where aedseo returns NA
    alarm: bool | None                   # seasonal onset alarm for the week; None if unavailable
    in_wave: bool | None                 # None unless asked for waves, or segmentation failed


class Backend(Protocol):
    version: str

    def fit(self, data: FitInput) -> WeekFit: ...
