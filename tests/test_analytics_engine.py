import math
from datetime import date

import pytest

from health_signal.analytics.aedseo_r import RAedseo
from health_signal.analytics.engine import assess_series
from health_signal.analytics.rules import SeasonState
from health_signal.analytics.series import Series
from health_signal.config import WaveEnd
from health_signal.methods import AEDSEO
from analytics_support import BandsBackend, FakeBackend, RecordingBackend, weeks


def _series(values):
    p = weeks(2021, len(values))
    return Series("clinical", "Influenza", "Greece", "ILIconsultationrate", {"age": "total"}, "per_100k",
                  p, values, "incidence", [100.0] * len(values), 1.0)


def _run(values, weeks_to_do=None, waves=None, state=SeasonState()):
    s = _series(values)
    return assess_series(s, weeks_to_do or s.periods, FakeBackend(), method=AEDSEO, start_week=21,
                         min_seasons=3, waves=waves, state=state)


def test_each_week_is_graded_from_data_up_to_it():
    res = _run([5, 6, 12, 30, 25])
    assert [r["period"] for r in res.rows] == weeks(2021, 5)
    # the first two weeks are too thin to fit: rows saying so, so a tile never shows an older week instead
    assert [r["level"] for r in res.rows] == [None, None, "low", "medium", "medium"]
    assert [r["trend"] for r in res.rows] == ["inconclusive", "inconclusive", "increasing", "increasing", "decreasing"]
    assert [r["phase"] for r in res.rows] == [None, None, "in_season", "in_season", "in_season"]
    assert all(r["provisional"] for r in res.rows) and res.graded == 3
    assert res.bounds[0] == (weeks(2021, 5)[2], FakeBackend.thresholds)


def test_only_the_requested_weeks_are_computed_resuming_the_state():
    full = _run([5, 6, 12, 8, 7])
    tail = _run([5, 6, 12, 8, 7], weeks_to_do=weeks(2021, 5)[3:], state=SeasonState(True, 0, weeks(2021, 5)[2]))
    assert tail.rows == full.rows[3:] and tail.state == full.state


def test_wave_pathogens_use_the_wave_pair():
    assert [r["phase"] for r in _run([5, 6, 12, 8], waves=WaveEnd()).rows][2:] == ["in_wave", "between_waves"]


def test_a_failed_onset_or_wave_fit_is_unavailable_not_a_negative():
    # Raising would drop the week's already-computed bands; returning "no alarm" or "between waves" would
    # publish a false phase.
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
    assert backend._wave(None, 1.0, {}, date(2025, 1, 6), WaveEnd()) is None


def test_a_week_aedseo_cannot_fit_grades_only_a_reported_zero():
    # A zero grades without bands: it's the lowest burden by definition. A positive value aedseo can't place
    # is "not graded", never left to an older week's grade.
    res = _run([0, 5, 12])   # the fake can't fit the first two weeks
    assert [(r["level"], r["trend"], r["phase"]) for r in res.rows[:2]] == \
        [("very_low", "inconclusive", None), (None, "inconclusive", None)]
    assert res.graded == 2


@pytest.mark.parametrize("bands", [(10.0, math.nan, math.nan, math.nan),   # a disease threshold but no burden levels
                                   (10.0, 10.0, 40.0, 80.0)])              # bands that don't rise
@pytest.mark.parametrize("waves", [None, WaveEnd()])
def test_unusable_bands_give_no_grade_phase_or_threshold_rows(bands, waves):
    # Waves too: a week with no level mustn't still tell the pathogen overview it is in a wave or between waves.
    s = _series([5, 6, 12, 30])
    res = assess_series(s, s.periods, BandsBackend(bands), method=AEDSEO, start_week=21, min_seasons=3,
                        waves=waves, state=SeasonState())
    assert [(r["level"], r["phase"]) for r in res.rows] == [(None, None)] * 4 and res.bounds == []


def test_a_censored_week_reaches_aedseo_as_a_gap_but_is_still_graded():
    # A non-detect isn't a measured 0: fitted as one it reads as a -100% fall and unbounded regrowth. Its own
    # week is still very low and below the season threshold.
    s = _series([12, 30, 0, 25])
    s.censored = [False, False, True, False]
    backend = RecordingBackend()
    res = assess_series(s, s.periods, backend, method=AEDSEO, start_week=21, min_seasons=3, waves=None,
                        state=SeasonState())
    assert math.isnan(backend.inputs[-1].values[2]) and backend.inputs[-1].values[3] == 25
    assert [r["level"] for r in res.rows[2:]] == ["very_low", "medium"]


def test_a_week_is_scaled_from_its_own_history_not_later_values():
    # A later, smaller value mustn't change how earlier weeks were fitted, or a rebuild would differ from the
    # incremental runs that graded them.
    s = _series([150.0, 200.0, 120.0, 0.5])
    s.scaled = True
    backend = RecordingBackend()
    assess_series(s, s.periods, backend, method=AEDSEO, start_week=21, min_seasons=3, waves=None, state=SeasonState())
    assert [i.scale for i in backend.inputs] == [1.0, 1.0, 1.0, 1000.0]
