from health_signal.analytics.engine import assess_series
from health_signal.analytics.rules import SeasonState
from health_signal.analytics.series import Series
from health_signal.methods import AEDSEO
from analytics_support import FakeBackend, weeks


def _series(values):
    p = weeks(2021, len(values))
    return Series("clinical", "Influenza", "Greece", "ILIconsultationrate", {"age": "total"}, "per_100k",
                  p, values, "incidence", [100.0] * len(values), 1.0)


def _run(values, weeks_to_do=None, waves=False, state=SeasonState()):
    s = _series(values)
    return assess_series(s, weeks_to_do or s.periods, FakeBackend(), method=AEDSEO, start_week=21,
                         min_seasons=3, waves=waves, state=state)


def test_each_week_is_graded_from_data_up_to_it():
    res = _run([5, 6, 12, 30, 25])
    assert [r["period"] for r in res.rows] == weeks(2021, 5)[2:]   # first two weeks too thin to fit
    assert [r["level"] for r in res.rows] == ["low", "medium", "medium"]
    assert [r["trend"] for r in res.rows] == ["increasing", "increasing", "decreasing"]
    assert [r["phase"] for r in res.rows] == ["in_season", "in_season", "in_season"]
    assert all(r["provisional"] for r in res.rows) and res.graded == 3
    assert res.bounds[0] == (weeks(2021, 5)[2], FakeBackend.thresholds)


def test_only_the_requested_weeks_are_computed_resuming_the_state():
    full = _run([5, 6, 12, 8, 7])
    tail = _run([5, 6, 12, 8, 7], weeks_to_do=weeks(2021, 5)[3:], state=SeasonState(True, 0, weeks(2021, 5)[2]))
    assert tail.rows == full.rows[1:] and tail.state == full.state


def test_wave_pathogens_use_the_wave_pair():
    assert [r["phase"] for r in _run([5, 6, 12, 8], waves=True).rows] == ["in_wave", "between_waves"]
