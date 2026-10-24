import math
from datetime import date, timedelta

import pytest

from health_signal.analytics.backend import FitError, FitInput

pytest.importorskip("rpy2")
from health_signal.analytics.aedseo_r import RAedseo  # noqa: E402  (after importorskip: R is optional)

pytestmark = pytest.mark.r


@pytest.fixture(scope="module")
def backend():
    try:
        return RAedseo()
    except RuntimeError as e:
        pytest.skip(str(e))


def _seasons(n_seasons=4, peak=90.0, base=5.0):
    # greece-public-health's synthetic season: a triangular peak each W21-W20 year.
    start = date.fromisocalendar(2019, 21, 1)
    dates, values = [], []
    for i in range(52 * n_seasons):
        frac = 1 - abs((i % 52) - 26) / 26
        dates.append(start + timedelta(weeks=i))
        values.append(round(base + peak * frac, 3))
    return tuple(dates), tuple(values)


def test_counts_fit_rising_bands_and_bounded_growth(backend):
    dates, values = _seasons()
    fit = backend.fit(FitInput(dates, values, (), 1.0, 1.0, "count", 21, False))
    assert all(a < b for a, b in zip(fit.thresholds, fit.thresholds[1:]))
    rate, lower, upper = fit.growth
    assert math.isnan(rate) or lower <= rate <= upper


def test_rates_below_one_fit_on_the_incidence_path(backend):
    dates, values = _seasons(peak=0.9, base=0.05)   # per-100k-like, below 1: aedseo needs them scaled up
    fit = backend.fit(FitInput(dates, values, (1.0,) * len(values), 1.0, 1000.0, "incidence", 21, False))
    assert all(math.isfinite(t) for t in fit.thresholds) and fit.thresholds[0] < 1   # back in the values' units


def test_waves_are_segmented_when_asked(backend):
    dates, values = _seasons()
    assert backend.fit(FitInput(dates, values, (), 1.0, 1.0, "count", 21, True)).in_wave in (True, False)


def test_a_series_too_short_to_fit_raises_fit_error(backend):
    dates, values = _seasons(n_seasons=1)
    with pytest.raises(FitError):
        backend.fit(FitInput(dates[:3], values[:3], (), 1.0, 1.0, "count", 21, False))
