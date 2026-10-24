from health_signal.analytics.phase import pathogen_phases
from health_signal.config import PhaseStreamsEntry

E = PhaseStreamsEntry(pathogen="Influenza", location="Greece", streams={"cases": "c/ili", "admissions": "c/sari"})


def test_in_season_only_when_every_stream_is_and_no_row_when_one_lags():
    cases = {"2025-W01": "in_season", "2025-W02": "in_season", "2025-W03": "in_season"}
    admissions = {"2025-W01": "out_of_season", "2025-W02": "in_season"}   # W03 not reported yet
    rows = pathogen_phases(E, {"cases": cases, "admissions": admissions}, waves=False)
    assert [(r["period"], r["phase"]) for r in rows] == [("2025-W01", "out_of_season"), ("2025-W02", "in_season")]


def test_a_blank_stream_phase_gives_no_row_and_waves_use_their_pair():
    rows = pathogen_phases(E, {"cases": {"2025-W01": "in_wave", "2025-W02": None},
                               "admissions": {"2025-W01": "between_waves", "2025-W02": "in_wave"}}, waves=True)
    assert [(r["period"], r["phase"]) for r in rows] == [("2025-W01", "between_waves")]
