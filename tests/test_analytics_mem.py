import math

from health_signal.analytics.backend import FitError, MemFit
from health_signal.analytics.mem_engine import assess_mem_series
from health_signal.analytics.series import Series
from analytics_support import weeks


class FakeMem:
    """Records each season's history; thresholds 10/20/40/80, delta 5, eta -5."""
    version = "fake-mem-1"

    def __init__(self, fails=False):
        self.calls, self.fails = [], fails

    def fit_season(self, history):
        self.calls.append(history)
        if self.fails:
            raise FitError("too little history")
        return MemFit((10.0, 20.0, 40.0, 80.0), 5.0, -5.0)


def _series(periods, values, **kw):
    return Series("clinical", {"Influenza"}, "Testville", "ILIconsultationrate", {}, "per_100k", list(periods),
                  [float(v) for v in values], "incidence", **kw)


def _seasons(n, start=2015, value=1.0):
    # n complete seasons from W40 of `start`, each a full year of weeks.
    periods = [p for p in weeks(start, 60 * n) if p >= f"{start}-W40"][: 52 * n]
    return periods, [value] * len(periods)


def _grade(series, weeks_, mem, **kw):
    return assess_mem_series(series, weeks_, mem, **{"start_week": 40, "seasons": 5, "min_seasons": 3, **kw})


def test_a_seasons_thresholds_come_from_the_seasons_before_it_and_hold_all_season():
    periods, values = _seasons(5)
    mem = FakeMem()
    current = [p for p in periods if p >= "2019-W40"]
    result = _grade(_series(periods, values), current, mem)
    assert len(mem.calls) == 1 and len(mem.calls[0]) == 4   # one fit, from the four seasons before
    assert len({b for _, b in result.bounds}) == 1


def test_only_the_last_seasons_setting_many_count():
    periods, values = _seasons(8)
    mem = FakeMem()
    _grade(_series(periods, values), periods[-3:], mem, seasons=5)
    assert len(mem.calls[0]) == 5


def test_levels_and_trends_follow_the_fit():
    periods, values = _seasons(4)
    tail = ["2019-W40", "2019-W41", "2019-W42", "2019-W43", "2019-W44"]
    series = _series(periods + tail, values + [5, 12, 30, 19, 4])
    rows = _grade(series, tail, FakeMem()).rows
    assert [(r["level"], r["trend"]) for r in rows] == [
        ("baseline", "not_assessed"), ("low", "increasing"), ("medium", "increasing"), ("low", "decreasing"),
        ("baseline", "decreasing")]
    assert all(r["phase"] is None and r["growth_rate"] is None for r in rows)


def test_a_gap_before_the_week_leaves_its_trend_unassessed():
    periods, values = _seasons(4)
    series = _series(periods + ["2019-W40", "2019-W42"], values + [30, 50])
    assert _grade(series, ["2019-W42"], FakeMem()).rows[0]["trend"] == "not_assessed"


def test_too_little_history_publishes_the_week_ungraded():
    periods, values = _seasons(1)
    series = _series(periods + ["2016-W40"], values + [30])
    rows = _grade(series, ["2016-W40"], FakeMem(fails=True)).rows
    assert [(r["level"], r["trend"]) for r in rows] == [(None, "not_assessed")]


def test_no_complete_season_asks_nothing_of_mem():
    mem = FakeMem()
    rows = _grade(_series(["2015-W40", "2015-W41"], [3, 4]), ["2015-W41"], mem).rows
    assert mem.calls == [] and rows[0]["level"] is None


def test_a_season_with_week_53_lines_up_with_seasons_without():
    # 2020 has a week 53: in every season's 53 weekly slots, week 1 is the same slot, and week 53 is NaN without one.
    periods = [p for p in weeks(2015, 7 * 53) if "2015-W40" <= p <= "2021-W39"]
    mem = FakeMem()
    _grade(_series(periods + ["2021-W40"], [1.0] * len(periods) + [1.0]), ["2021-W40"], mem)
    history = mem.calls[0]
    assert {len(s) for s in history} == {53}
    with_53 = [s for s in history if not math.isnan(s[13])]
    assert len(with_53) == 1 and all(math.isnan(s[13]) for s in history if s is not with_53[0])


def test_a_grade_is_provisional_below_min_seasons():
    periods, values = _seasons(2)
    series = _series(periods + ["2017-W40"], values + [30])
    assert _grade(series, ["2017-W40"], FakeMem(), min_seasons=3).rows[0]["provisional"] is True
    periods, values = _seasons(3)
    series = _series(periods + ["2018-W40"], values + [30])
    assert _grade(series, ["2018-W40"], FakeMem(), min_seasons=3).rows[0]["provisional"] is False


def test_a_censored_value_is_missing_to_mem_but_its_week_is_graded():
    periods, values = _seasons(4)
    censored = [False] * len(periods) + [False, True]
    series = _series(periods + ["2019-W40", "2019-W41"], values + [30, 0], censored=censored)
    rows = _grade(series, ["2019-W40", "2019-W41"], FakeMem()).rows
    assert rows[1]["level"] == "baseline" and rows[1]["trend"] == "not_assessed"


class CrossedMem(FakeMem):
    # As mem can return after low-peaked seasons: the medium-intensity threshold below the epidemic one.
    def fit_season(self, history):
        self.calls.append(history)
        return MemFit((44.8, 26.8, 253.0, 683.0), 11.0, -11.0)


def test_thresholds_that_dont_rise_still_grade_as_mem_does():
    # Below the epidemic threshold is baseline, whatever the intensity thresholds; above it, the highest reached.
    periods, values = _seasons(4)
    tail = ["2019-W40", "2019-W41"]
    result = _grade(_series(periods + tail, values + [35, 50]), tail, CrossedMem())
    assert [r["level"] for r in result.rows] == ["baseline", "medium"]
    assert result.bounds[0][1] == (44.8, 44.8, 253.0, 683.0)   # drawn as MEM grades: no low band left
