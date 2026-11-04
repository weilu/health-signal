import math

import pytest

from health_signal.analytics.rules import (SeasonState, completed_seasons, mem_trend, value_scale, level_for, season_of,
                                          season_phase, trend_for, wave_phase, weeks_between)

LEVELS = ["very_low", "low", "medium", "high", "very_high"]
THR = (10.0, 20.0, 40.0, 80.0)


def test_season_of_uses_the_configured_start():
    assert season_of("2024-W40", 21) == 2024 and season_of("2025-W20", 21) == 2024
    assert season_of("2025-W21", 21) == 2025 and season_of("2024-W01", 21) == 2023
    assert season_of("2024-W01", 1) == 2024 and season_of("2024-W52", 1) == 2024


def test_completed_seasons_count_only_full_past_seasons():
    weeks = [f"{y}-W{w:02d}" for y in (2021, 2022, 2023) for w in range(1, 53)]
    # 2021 and 2022 (52 weeks each) complete; 2023 is the current season; a 10-week 2020 stub doesn't count
    assert completed_seasons([f"2020-W{w:02d}" for w in range(43, 53)] + weeks, 1) == 2


def test_level_for_grades_against_lower_bounds():
    assert [level_for(v, THR, LEVELS) for v in (5, 10, 30, 60, 90)] == LEVELS


@pytest.mark.parametrize("thr", [(math.nan,) * 4, (10.0, math.nan, 40.0, 80.0)])
def test_unfit_thresholds_grade_only_a_reported_zero(thr):
    # greece: a reported zero is definitionally the lowest burden; an unplaceable positive stays ungraded
    assert level_for(0.0, thr, LEVELS) == "very_low"
    assert level_for(5.0, thr, LEVELS) is None


def test_trend_for_reads_the_interval():
    assert trend_for(0.15, 0.05, 0.25)[0] == "increasing"
    assert trend_for(-0.15, -0.25, -0.05)[0] == "decreasing"
    trend, growth = trend_for(0.0, -0.1, 0.1)
    assert trend == "stable" and growth == (0.0, pytest.approx(math.exp(-0.1) - 1), pytest.approx(math.exp(0.1) - 1))


@pytest.mark.parametrize("rate, lower, upper", [
    (math.nan, 0.0, 0.1),                                  # partial NA
    (-2147483648.0, -2147483648.0, -2147483648.0),         # R's NA_integer_ sentinel: finite but not a rate
    (710.0, 710.0, 710.0),                                 # above exp() overflow
])
def test_unestimable_growth_is_inconclusive(rate, lower, upper):
    assert trend_for(rate, lower, upper) == ("inconclusive", None)


def test_value_scale_lifts_the_smallest_positive_value_to_100():
    assert value_scale([0.0, 0.42, 3.0]) == 1000.0
    assert value_scale([150.0, 1e11]) == 1.0
    assert value_scale([0.0, 0.0]) == 1.0


def test_weeks_between_crosses_years_and_w53():
    assert weeks_between("2020-W52", "2021-W02") == 3   # 2020 has a W53


def _walk(weeks):  # [(period, value, alarm)], floor 10
    state, out = SeasonState(), []
    for period, value, alarm in weeks:
        phase, state = season_phase(state, period, value, 10.0, alarm)
        out.append(phase)
    return out


def test_a_season_starts_at_the_onset_alarm_not_the_threshold_crossing():
    # above the floor at W02 but no alarm until W03: the season isn't backdated
    assert _walk([("2025-W01", 5, False), ("2025-W02", 12, False), ("2025-W03", 15, True), ("2025-W04", 20, False)]) == \
        ["out_of_season", "out_of_season", "in_season", "in_season"]


def test_one_week_below_holds_the_season_two_end_it():
    weeks = [("2025-W01", 15, True), ("2025-W02", 8, False), ("2025-W03", 12, False),
             ("2025-W04", 8, False), ("2025-W05", 7, False)]
    assert _walk(weeks) == ["in_season", "in_season", "in_season", "in_season", "out_of_season"]


def test_a_long_reporting_gap_ends_the_season_a_short_one_does_not():
    assert _walk([("2025-W01", 15, True), ("2025-W10", 15, False)]) == ["in_season", "in_season"]       # 8 missing
    assert _walk([("2025-W01", 15, True), ("2025-W11", 15, False)]) == ["in_season", "out_of_season"]   # 9 missing


def test_an_unfit_week_has_no_phase_and_keeps_the_state():
    state = SeasonState(in_season=True, last_period="2025-W01")
    phase, after = season_phase(state, "2025-W02", 15, float("nan"), None)
    assert phase is None and after == state


def test_a_wave_starts_only_on_its_own_weeks_alarm():
    # aedseo replays the whole history with this week's threshold, so it can place a wave's start in the past
    # where no week, as of itself, flagged one (ICU, Greece, 2024-W21): that week is still between waves.
    assert wave_phase(SeasonState(last_period="2024-W20"), "2024-W21", True, False)[0] == "between_waves"
    assert wave_phase(SeasonState(last_period="2024-W20"), "2024-W21", True, True)[0] == "in_wave"


def test_a_wave_continues_while_aedseo_keeps_it_and_ends_when_it_does():
    wave = SeasonState(True, 0, "2025-W01")
    assert wave_phase(wave, "2025-W02", True, False) == ("in_wave", SeasonState(True, 0, "2025-W02"))
    assert wave_phase(wave, "2025-W02", False, False) == ("between_waves", SeasonState(False, 0, "2025-W02"))


def test_a_wave_carries_across_a_reporting_gap_but_not_a_long_silence():
    wave = SeasonState(True, 0, "2025-W37")
    assert wave_phase(wave, "2025-W44", True, False)[0] == "in_wave"     # the 2025 admissions outage
    assert wave_phase(wave, "2025-W48", True, False)[0] == "between_waves"


def test_an_unknown_wave_state_is_no_phase_and_keeps_the_state():
    state = SeasonState(True, 0, "2025-W01")
    assert wave_phase(state, "2025-W02", None, True) == (None, state)
    # Whether a wave started can't be told without the onset alarm.
    idle = SeasonState(last_period="2025-W01")
    assert wave_phase(idle, "2025-W02", True, None) == (None, idle)


def test_an_unavailable_onset_alarm_is_no_phase_not_out_of_season():
    # No phase when the onset fit is unavailable, rather than calling it out of season
    state = SeasonState(last_period="2025-W01")
    assert season_phase(state, "2025-W02", 15, 10.0, None) == (None, state)
    in_season = SeasonState(True, 0, "2025-W01")
    assert season_phase(in_season, "2025-W02", 15, 10.0, None)[0] == "in_season"   # a running season needs no alarm


@pytest.mark.parametrize("value,previous,expected", [
    (12, 8, "increasing"),       # first week over the epidemic threshold of 10
    (30, 20, "increasing"),      # +10 > delta 5
    (20, 30, "decreasing"),      # -10 < eta -5
    (22, 20, "stable"),
    (8, 12, "decreasing"),       # first week back below
    (8, 6, "not_assessed"),      # below: MEM doesn't assess
    (20, None, "not_assessed"),  # a gap before the week
    (20, math.nan, "not_assessed"),
    (math.nan, 20, "not_assessed"),
])
def test_mem_trend(value, previous, expected):
    assert mem_trend(value, previous, epidemic=10, delta=5, eta=-5) == expected
