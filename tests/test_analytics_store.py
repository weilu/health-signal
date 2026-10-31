import pandas as pd
import pytest

from health_signal.analytics.engine import SeriesResult
from health_signal.analytics.rules import SeasonState
from health_signal.analytics.series import Series
from health_signal.analytics.store import FeedStore, SettingsChanged, write_validated
from health_signal.profile import ERVISS
from analytics_support import weeks

SETTINGS = [("aedseo", "year_start_week", "21"), ("aedseo", "min_seasons", "3"), ("aedseo", "package_version", "fake-1")]
P = weeks(2021, 4)
S = Series("clinical", {"Influenza"}, "Greece", "ILIconsultationrate", {"survtype": "primary care sentinel", "age": "total"},
           "per_100k", P, [12, 30, 8, 7], "incidence", [1.0] * 4, 1.0)
B = (10.0, 20.0, 40.0, 80.0)


def _row(period, phase="in_season"):
    return {"period": period, "level": "low", "provisional": True, "trend": "stable", "growth_rate": 0.0,
            "growth_lower": -0.1, "growth_upper": 0.1, "phase": phase}


def _write(tmp_path, rows, bounds, full=False):
    store = FeedStore(tmp_path, ERVISS, full=full)
    store.check_settings(SETTINGS)
    store.add(S, "aedseo", SeriesResult(rows, bounds, SeasonState(), len(rows)))
    write_validated(store.files(SETTINGS), store.validate)   # as a run publishes
    return FeedStore(tmp_path, ERVISS, full=False)


def test_new_weeks_append_and_equal_bounds_extend_the_span(tmp_path):
    _write(tmp_path, [_row(P[0]), _row(P[1])], [(P[0], B), (P[1], B)])
    store = _write(tmp_path, [_row(P[2])], [(P[2], (11.0, 20.0, 40.0, 80.0))])
    assert store.last_week(S, "aedseo") == P[2]
    t = pd.read_csv(tmp_path / "thresholds.csv")
    assert sorted(set(zip(t["from"], t["to"]))) == [(P[0], P[1]), (P[2], P[2])]
    assert sorted(t.loc[t["from"] == P[2], "lower_bound"]) == [11.0, 20.0, 40.0, 80.0]


def test_equal_bounds_do_not_span_a_week_without_them(tmp_path):
    # P[1] was observed but had no usable bands: the chart mustn't draw bands across it.
    _write(tmp_path, [_row(P[0]), _row(P[1]), _row(P[2])], [(P[0], B), (P[2], B)])
    t = pd.read_csv(tmp_path / "thresholds.csv")
    assert sorted(set(zip(t["from"], t["to"]))) == [(P[0], P[0]), (P[2], P[2])]


def test_resume_carries_a_dip_week(tmp_path):
    store = _write(tmp_path, [_row(P[0]), _row(P[2])], [(P[0], B), (P[2], B)])   # P[2]'s value 8 < 10: a dip
    assert store.resume(S, "aedseo") == SeasonState(True, 1, P[2])
    store = _write(tmp_path, [_row(P[3], phase="out_of_season")], [(P[3], B)])
    assert store.resume(S, "aedseo") == SeasonState(last_period=P[3])


def test_changed_settings_stop_the_run_and_leave_files_alone(tmp_path):
    _write(tmp_path, [_row(P[0])], [(P[0], B)])
    before = (tmp_path / "assessment.csv").read_bytes()
    store = FeedStore(tmp_path, ERVISS, full=False)
    with pytest.raises(SettingsChanged, match="year_start_week"):
        store.check_settings([("aedseo", "year_start_week", "1"), *SETTINGS[1:]])
    assert (tmp_path / "assessment.csv").read_bytes() == before


def test_rows_written_by_another_producer_need_a_full_run(tmp_path):
    _write(tmp_path, [_row(P[0])], [])
    (tmp_path / "assessed_with.csv").unlink()
    with pytest.raises(SettingsChanged, match="assessed_with.csv"):
        FeedStore(tmp_path, ERVISS, full=False).check_settings(SETTINGS)


def test_full_rebuild_ignores_old_rows_and_settings(tmp_path):
    _write(tmp_path, [_row(P[0]), _row(P[1])], [])
    store = FeedStore(tmp_path, ERVISS, full=True)
    store.check_settings([("aedseo", "year_start_week", "1")])
    assert store.last_week(S, "aedseo") is None


def test_an_invalid_table_is_never_written(tmp_path):
    _write(tmp_path, [_row(P[0])], [])
    before = (tmp_path / "assessment.csv").read_bytes()
    with pytest.raises(ValueError):
        _write(tmp_path, [{**_row(P[1]), "phase": "in_bloom"}], [])   # the app's loader rejects it
    assert (tmp_path / "assessment.csv").read_bytes() == before and not (tmp_path / ".assess-tmp").exists()
