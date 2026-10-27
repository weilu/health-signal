"""SSI's aedseo over rpy2: the only module that touches R, entered only to fit (generalised from
greece-public-health's aedseo_bridge)."""
import math
from datetime import date, timedelta

import numpy as np

from .backend import FitError, FitInput, WeekFit

# SSI's defaults as greece-public-health ran them (spec §6.3.1); not configurable until a country needs it.
_ONSET = dict(family="quasipoisson", k=5)
_BURDEN = dict(family="lnorm", n_peak=3, decay_factor=0.8, conf_levels=0.975)
# Tuned on the Greek COVID series to separate back-to-back waves without single-week noise.
_WAVES = dict(family="quasipoisson", family_quant="lnorm", multiple_waves=True, steps_with_decrease=3,
              burden_level_decrease="medium", n_peak=3, conf_levels=0.975, decay_factor=0.8)
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
            population = [exposure[d] if d in exposure else na for d in weeks]
            tsd = aedseo.to_time_series(incidence=ro.FloatVector(incidence), population=ro.FloatVector(population),
                                        incidence_denominator=data.per, time=time, time_interval="weeks")
        try:
            tdis = float(self._numbers(aedseo.estimate_disease_threshold(tsd, **season), "disease_threshold")[0])
        except self._RError as e:
            raise FitError(str(e)) from e
        if not math.isfinite(tdis):
            raise FitError("no disease threshold")
        try:
            bands = tuple(float(x) for x in np.asarray(
                aedseo.seasonal_burden_levels(tsd, disease_threshold=tdis, **season, **_BURDEN).rx2("values"),
                dtype=float))
        except self._RError:
            bands = _NAN4   # burden levels need a complete previous season
        growth, alarm = self._onset(tsd, tdis, season, data.dates[-1])
        in_wave = self._wave(tsd, tdis, season, data.dates[-1]) if data.waves else None
        bands = tuple(b / data.scale for b in bands) if len(bands) == 4 else _NAN4
        return WeekFit(bands, growth, alarm, in_wave)

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

    def _wave(self, tsd, tdis, season, week: date) -> bool | None:
        try:
            onset = self._aedseo.combined_seasonal_output(
                tsd, disease_threshold=tdis, only_current_season=True, **season, **_WAVES).rx2("onset_output")
        except self._RError:
            return None   # can't segment: unavailable, not "between waves"
        if not self._last_is(onset, week):
            return None
        return bool(math.isfinite(self._numbers(onset, "wave_number")[-1]))
