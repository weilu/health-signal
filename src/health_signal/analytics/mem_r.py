"""The Moving Epidemic Method over rpy2: R's mem package, entered only to fit."""
import math

import numpy as np

from .aedseo_r import load_r, package_version
from .backend import BackendError, FitError, MemFit


class RMem:
    def __init__(self):
        self._ro, self._mem, self._base, utils, self._RError = load_r("mem")
        self.version = package_version(utils, "mem")

    def fit_season(self, history: list[list[float]]) -> MemFit:
        ro = self._ro
        # One column per season, as mem lays seasons out; missing weeks NA, never zero.
        columns = {f"season{i + 1}": ro.FloatVector([ro.NA_Real if math.isnan(v) else v for v in season])
                   for i, season in enumerate(history)}
        # memtrend labels its result by the rows' names, and fails on a frame without them.
        frame = ro.r["rownames<-"](ro.DataFrame(columns), ro.StrVector([str(w + 1) for w in range(len(history[0]))]))
        try:
            model = self._mem.memmodel(frame, **{"i.seasons": len(history)})
        except self._RError as e:
            raise BackendError(f"mem's memmodel failed: {e}") from e
        # Too little history isn't an R error to mem: it says so and returns NULL.
        if self._base.is_null(model)[0]:
            raise FitError("mem needs at least two seasons of non-zero values")
        try:
            intensity = np.asarray(self._mem.memintensity(model).rx2("intensity.thresholds"), dtype=float).ravel()
            trend = np.asarray(self._mem.memtrend(model).rx2("trend.thresholds"), dtype=float).ravel()
        except self._RError as e:
            raise FitError(f"mem can't set thresholds from this history: {e}") from e
        if len(intensity) != 4 or len(trend) != 2 or not np.isfinite([*intensity, *trend]).all():
            raise FitError("mem returned no usable thresholds")
        return MemFit(tuple(float(x) for x in intensity), float(trend[0]), float(trend[1]))
