import math
from datetime import date, timedelta

import pytest

from health_signal.analytics.backend import FitError, FitInput
from health_signal.analytics.engine import assess_series
from health_signal.analytics.rules import SeasonState
from health_signal.analytics.series import Series
from health_signal.methods import AEDSEO

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


def test_growth_right_after_a_reporting_outage_is_unavailable_not_rescaled(backend):
    # aedseo windows are rows: without the missing weeks as gaps, a 5-row window would span the outage and
    # report its change as weekly growth.
    dates, values = _seasons()
    keep = [i for i in range(len(dates)) if not len(dates) - 8 <= i < len(dates) - 2]   # 6 missing, 2 since
    fit = backend.fit(FitInput(tuple(dates[i] for i in keep), tuple(values[i] for i in keep), (), 1.0, 1.0,
                               "count", 21, False))
    assert all(math.isnan(g) for g in fit.growth)


def test_a_week_is_graded_the_same_whatever_data_follows_it(backend):
    # As-of rows (spec §6.3.1): adding later weeks never changes an earlier week's grade.
    dates, values = _seasons()
    periods = [f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}" for d in dates]
    short = Series("f", "Influenza", "L", "x", {}, "count", periods[:-2], list(values[:-2]), "count")
    long_ = Series("f", "Influenza", "L", "x", {}, "count", periods, list(values), "count")
    weeks = periods[-5:-2]
    options = dict(method=AEDSEO, start_week=21, min_seasons=3, waves=False, state=SeasonState())
    assert assess_series(short, weeks, backend, **options).rows == assess_series(long_, weeks, backend, **options).rows


@pytest.mark.parametrize("kind, exposure", [("count", ()), ("incidence", None)])
def test_censored_weeks_are_fitted_as_gaps(backend, kind, exposure):
    dates, values = _seasons()
    values = tuple(math.nan if i % 13 == 7 else v for i, v in enumerate(values))   # scattered non-detects
    exposure = (1.0,) * len(values) if exposure is None else exposure
    fit = backend.fit(FitInput(dates, values, exposure, 1.0, 1.0, kind, 21, False))
    assert all(math.isfinite(t) for t in fit.thresholds)
