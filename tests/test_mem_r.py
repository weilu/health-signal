import math
import os
import random

import pytest

from health_signal.analytics import assess
from health_signal.analytics.backend import FitError
from health_signal.assessments import AssessmentSource
from health_signal.config import Config
from health_signal.profile import ERVISS
from analytics_support import erviss_rows, weeks, write_feed

if not os.environ.get("HS_REQUIRE_R"):
    pytest.importorskip("rpy2")
from health_signal.analytics.mem_r import RMem  # noqa: E402  (after importorskip: R is optional)

pytestmark = pytest.mark.r


@pytest.fixture(scope="module")
def backend():
    try:
        return RMem()
    except RuntimeError as e:
        # The dedicated CI job sets HS_REQUIRE_R, so a broken R there fails rather than skipping to green.
        if os.environ.get("HS_REQUIRE_R"):
            raise
        pytest.skip(str(e))


def _bell_seasons(n, seed=7):
    # A winter epidemic peaking mid-season, of a different height each year, over a low baseline.
    rng = random.Random(seed)
    seasons = []
    for _ in range(n):
        peak = rng.uniform(150, 400)
        seasons.append([10 + peak * math.exp(-((w - 18) / 4) ** 2) + rng.uniform(0, 3) for w in range(53)])
    return seasons


def test_mem_finds_thresholds_that_rise_within_the_seasons_range(backend):
    seasons = _bell_seasons(5)
    fit = backend.fit_season(seasons)
    assert all(a < b for a, b in zip(fit.thresholds, fit.thresholds[1:]))
    assert 10 < fit.thresholds[0] < max(max(s) for s in seasons)
    assert fit.delta > 0 > fit.eta


def test_missing_weeks_are_left_out_not_zero(backend):
    seasons = _bell_seasons(5)
    gappy = [list(s) for s in seasons]
    gappy[2][30:36] = [math.nan] * 6
    assert backend.fit_season(gappy).thresholds[0] == pytest.approx(backend.fit_season(seasons).thresholds[0], rel=0.2)


def test_mem_cant_fit_a_single_season(backend):
    with pytest.raises(FitError):
        backend.fit_season(_bell_seasons(1))


def test_the_build_is_recorded(backend):
    assert backend.version


def test_assess_grades_a_feed_with_mem(backend, tmp_path):
    periods = weeks(2015, 4 * 53)
    values = [v for season in _bell_seasons(5) for v in season][: len(periods)]
    feed = write_feed(tmp_path / "c", erviss_rows("Greece", "ILIconsultationrate", "per_100k", values, periods=periods))
    query = {"feed": "clinical", "indicator": "ILIconsultationrate",
             "dimensions": {"survtype": "primary care sentinel", "age": "total"}}
    config = Config.model_validate({
        "schema_version": "1", "site": {"title": "T"},
        "data": {"feeds": [{"id": "clinical", "profile": "erviss", "dir": str(feed), "assessments": str(tmp_path / "a")}]},
        "targets": [{"id": "Influenza", "pages": [{"id": "c", "panels": [{"id": "ili", "query": query}]}]}],
        "analytics": {"methods": ["mem"], "mem": {"season_start_week": 1}}})
    assess(config)
    rows = AssessmentSource(tmp_path / "a", ERVISS).assessments()
    graded = [r for r in rows if r.level]
    assert graded and {r.method for r in rows} == {"mem"}
    assert {r.level for r in graded} <= {"baseline", "low", "medium", "high", "very_high"}
    assert {r.level for r in graded} > {"baseline"}   # the epidemics rise above it
