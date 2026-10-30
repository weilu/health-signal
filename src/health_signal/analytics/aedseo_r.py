"""SSI's aedseo over rpy2: the only module that touches R, entered only to fit."""
import math
from datetime import date, timedelta

import numpy as np

from ..config import WaveEnd
from .backend import BackendError, FitError, FitInput, WeekFit

# The aedseo paper's validated settings (SSI; medRxiv 2025, doi:10.1101/2025.11.18.25340240): k, the families
# and decay_factor are aedseo's defaults; n_peak=3 and conf_levels=0.975 (Supplement S5) override its 6 and 0.95.
_ONSET = dict(family="quasipoisson", k=5)
_BURDEN = dict(family="lnorm", n_peak=3, decay_factor=0.8, conf_levels=0.975)
# combined_seasonal_output refits the onset and burden levels itself, and a wave ends against those bands, so it
# gets the same settings as the bands we draw and grade by (its `family` is the onset's; the burden's is
# `family_quant`). How a wave ends comes from config (analytics.aedseo.wave_end).
_WAVES = dict(family=_ONSET["family"], k=_ONSET["k"],
              family_quant=_BURDEN["family"], **{k: v for k, v in _BURDEN.items() if k != "family"},
              multiple_waves=True)
_NAN3 = (math.nan,) * 3
_NAN4 = (math.nan,) * 4


def load_r():
    try:
        # Lazy: importing health_signal.analytics must not need R; only fitting does.
        import rpy2.robjects as ro  # noqa: PLC0415
        from rpy2.rinterface_lib.embedded import RRuntimeError  # noqa: PLC0415
        from rpy2.robjects.packages import importr  # noqa: PLC0415
        return ro, importr("aedseo"), importr("base"), importr("utils"), RRuntimeError
    except Exception as e:  # noqa: BLE001 - any R/rpy2 init failure gets the same actionable message
        raise RuntimeError("assess needs R with the aedseo package via rpy2: install R, run "
                           "install.packages('aedseo') in R, `pip install health-signal[analytics]`, "
                           "and set R_HOME") from e


class RAedseo:
    def __init__(self):
        self._ro, self._aedseo, self._base, utils, self._RError = load_r()
        self.version = ".".join(str(int(x)) for x in self._base.unlist(utils.packageVersion("aedseo")))

    def _numbers(self, frame, column) -> np.ndarray:
        # base.as_numeric first: an R integer NA would otherwise cast to INT_MIN, a finite non-value.
        return np.asarray(self._base.as_numeric(frame.rx2(column)), dtype=float)

    def _last_is(self, frame, week: date) -> bool:
        # aedseo trims the leading k-1 weeks, so read by reference_time, never by position.
        times = list(self._base.as_character(self._base.as_Date(frame.rx2("reference_time"))))
        return bool(times) and times[-1] == week.isoformat()

    def fit(self, data: FitInput) -> WeekFit:
        ro, aedseo, base = self._ro, self._aedseo, self._base
        season = dict(season_start=data.season_start, season_end=data.season_start - 1)
        # aedseo's windows are rows, so a reporting gap must be rows of NA (which it skips), not left out: a
        # window spanning an outage would otherwise report the change across it as weekly growth.
        weeks = [data.dates[0] + timedelta(weeks=i) for i in range((data.dates[-1] - data.dates[0]).days // 7 + 1)]
        # A NaN value (censored) is a gap like a missing week.
        observed = {d: v for d, v in zip(data.dates, data.values) if not math.isnan(v)}
        exposure = dict(zip(data.dates, data.exposure))
        time = base.as_Date(ro.StrVector([d.isoformat() for d in weeks]))
        na = ro.NA_Real
        if data.kind == "count":
            cases = [round(observed[d]) if d in observed else na for d in weeks]
            tsd = aedseo.to_time_series(cases=ro.FloatVector(cases), time=time, time_interval="weeks")
        else:
            incidence = [observed[d] * data.scale if d in observed else na for d in weeks]
            # aedseo takes a whole-number population; a derived denominator (e.g. consultations from cases and
            # rate) isn't one, and rounding it moves the rate by well under its reporting precision.
            population = [round(exposure[d]) if d in exposure else na for d in weeks]
            tsd = aedseo.to_time_series(incidence=ro.FloatVector(incidence), population=ro.FloatVector(population),
                                        incidence_denominator=data.per, time=time, time_interval="weeks")
        tdis = self._threshold(tsd, season)
        try:
            bands = tuple(float(x) for x in np.asarray(
                aedseo.seasonal_burden_levels(tsd, disease_threshold=tdis, **season, **_BURDEN).rx2("values"),
                dtype=float))
        except self._RError:
            bands = _NAN4   # burden levels need a complete previous season
        growth, alarm = self._onset(tsd, tdis, season, data.dates[-1])
        in_wave = self._wave(tsd, tdis, season, data.dates[-1], data.waves) if data.waves else None
        bands = tuple(b / data.scale for b in bands) if len(bands) == 4 else _NAN4
        return WeekFit(bands, growth, alarm, in_wave)

    def _threshold(self, tsd, season) -> float:
        try:
            tdis = float(self._numbers(self._aedseo.estimate_disease_threshold(tsd, **season), "disease_threshold")[0])
        except self._RError as e:
            # aedseo returns NA for too little history (checked down to all-NA input); raising means R or the call
            # itself is broken, which a run must not publish as weeks that merely couldn't be graded.
            raise BackendError(f"aedseo's estimate_disease_threshold failed: {e}") from e
        if not math.isfinite(tdis):
            raise FitError("no disease threshold")
        return tdis

    def _onset(self, tsd, tdis, season, week: date) -> tuple[tuple[float, float, float], bool | None]:
        try:
            onset = self._base.as_data_frame(self._aedseo.seasonal_onset(
                tsd, disease_threshold=tdis, only_current_season=True, **season, **_ONSET))
        except self._RError:
            return _NAN3, None   # unavailable, not "no onset"
        if not self._last_is(onset, week):
            return _NAN3, None
        growth = tuple(float(self._numbers(onset, c)[-1])
                       for c in ("growth_rate", "lower_growth_rate", "upper_growth_rate"))
        alarm = self._numbers(onset, "seasonal_onset_alarm")[-1]
        return growth, (bool(alarm) if math.isfinite(alarm) else None)

    def _wave(self, tsd, tdis, season, week: date, end: WaveEnd) -> bool | None:
        try:
            # Whole history, unlike the onset: aedseo tracks a wave row by row, so cut at the season start it
            # would drop a wave still declining across it to "between waves" until a fresh onset.
            onset = self._aedseo.combined_seasonal_output(
                tsd, disease_threshold=tdis, only_current_season=False, **season, **_WAVES,
                steps_with_decrease=end.steps_with_decrease,
                burden_level_decrease=end.burden_level_decrease).rx2("onset_output")
        except self._RError:
            return None   # can't segment: unavailable, not "between waves"
        if not self._last_is(onset, week):
            return None
        return bool(math.isfinite(self._numbers(onset, "wave_number")[-1]))
