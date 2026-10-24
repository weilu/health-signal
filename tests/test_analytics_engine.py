import math
from datetime import date

from health_signal.analytics.aedseo_r import RAedseo
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


def test_a_failed_onset_or_wave_fit_is_unavailable_not_a_negative():
    # Raising would drop the week's already-computed bands; returning "no alarm" or "between waves" would
    # publish a false phase. Ported from greece-public-health's bridge test.
    class RError(Exception):
        pass

    class Failing:
        def seasonal_onset(self, *args, **kwargs):
            raise RError("fit failed")

        def combined_seasonal_output(self, *args, **kwargs):
            raise RError("can't segment")

    class Base:
        def as_data_frame(self, frame):
            return frame

    backend = RAedseo.__new__(RAedseo)   # no R needed: only the error handling is exercised
    backend._aedseo, backend._base, backend._RError = Failing(), Base(), RError
    growth, alarm = backend._onset(None, 1.0, {}, date(2025, 1, 6))
    assert all(math.isnan(g) for g in growth) and alarm is None
    assert backend._wave(None, 1.0, {}, date(2025, 1, 6)) is None


def test_a_reported_zero_grades_very_low_even_when_aedseo_cannot_fit():
    # greece-public-health grades a zero without bands too: it's the lowest burden by definition. A positive
    # value aedseo can't place stays without a row.
    res = _run([0, 5, 12])   # the fake can't fit the first two weeks
    assert [(r["period"], r["level"], r["trend"], r["phase"]) for r in res.rows][:1] == \
        [(weeks(2021, 3)[0], "very_low", "inconclusive", None)]
    assert [r["period"] for r in res.rows] == [weeks(2021, 3)[0], weeks(2021, 3)[2]] and res.graded == 2
