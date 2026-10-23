import pytest
from health_signal.assessments import AssessmentSource, PhaseSource
from health_signal.profile import PHES_ODM

_A = "location,period,pathogen,aggregation,indicator,method,level,provisional,trend,growth_rate,growth_lower,growth_upper,phase\n"
_A1 = "Testville,2025-W02,Influenza,floMean,fluA,aedseo,low,false,increasing,0.2,0.1,0.3,in_season\n"
_T = "location,pathogen,aggregation,indicator,method,from,to,level,lower_bound\n"
_T1 = ("Testville,Influenza,floMean,fluA,aedseo,2024-W21,2025-W20,low,10\n"
       "Testville,Influenza,floMean,fluA,aedseo,2024-W21,2025-W20,medium,20\n")
_P = "location,pathogen,period,method,phase\n"


def _src(tmp_path, assessment=None, thresholds=None):
    d = tmp_path / "assessed"
    d.mkdir()
    if assessment is not None:
        (d / "assessment.csv").write_text(_A + assessment, encoding="utf-8")
    if thresholds is not None:
        (d / "thresholds.csv").write_text(_T + thresholds, encoding="utf-8")
    return AssessmentSource(d, PHES_ODM)


def test_assessments_load_and_filter(tmp_path):
    decoys = (_A1.replace("Testville,", "Otherville,")
              + _A1.replace(",fluA,", ",fluB,")
              + _A1.replace(",floMean,", ",pmmovNorm,")
              + _A1.replace("2025-W02", "2025-W09"))
    rows = _src(tmp_path, _A1 + decoys).assessments(location="Testville", indicator="fluA", week_to="2025-W05",
                                                    dimensions={"aggregation": "floMean"})
    assert [(r.period, r.level, r.provisional, r.trend, r.growth_rate, r.phase) for r in rows] == [
        ("2025-W02", "low", False, "increasing", 0.2, "in_season")]


def test_missing_files_are_empty_tables(tmp_path):
    src = _src(tmp_path)
    assert src.assessments() == [] and src.thresholds() == []


@pytest.mark.parametrize("bad, message", [
    (_A1.replace(",low,", ",alert,"), "level"),                    # another method's vocabulary
    (_A1.replace(",aedseo,", ",mem,"), "method"),                  # not in the registry
    (_A1.replace(",increasing,", ",up,"), "trend"),
    (_A1.replace(",false,", ",maybe,"), "provisional"),
    (_A1.replace(",0.2,0.1,0.3,", ",0.5,0.1,0.3,"), "growth"),     # rate outside its interval
    (_A1.replace(",0.2,0.1,0.3,", ",0.2,,0.3,"), "growth"),        # partly blank
    (_A1.replace(",in_season", ",in_bloom"), "phase"),
    (_A1.replace(",Influenza,", ",RSV,"), "implies pathogen"),     # the feed's key rules apply
])
def test_bad_assessment_rows_fail_with_file_and_row(tmp_path, bad, message):
    with pytest.raises(ValueError, match=rf"assessment\.csv row 1: .*{message}"):
        _src(tmp_path, bad)


def test_conflicting_assessments_fail(tmp_path):
    with pytest.raises(ValueError, match="conflicts with"):
        _src(tmp_path, _A1 + _A1.replace(",low,", ",high,"))


def test_thresholds_load(tmp_path):
    rows = _src(tmp_path, thresholds=_T1).thresholds()
    assert [(r.from_, r.to, r.level, r.lower_bound) for r in rows] == [
        ("2024-W21", "2025-W20", "low", 10.0), ("2024-W21", "2025-W20", "medium", 20.0)]
    assert rows[0].model_dump(by_alias=True)["from"] == "2024-W21"


@pytest.mark.parametrize("bad, message", [
    (_T1.replace("medium,20", "medium,5"), "rise"),                                    # bounds must rise in level order
    (_T1.replace("2024-W21,2025-W20,low", "2025-W20,2024-W21,low"), "from"),          # from after to
    (_T1 + "Testville,Influenza,floMean,fluA,aedseo,2025-W10,2026-W09,low,12\n", "overlaps"),  # spans overlap
    (_T1.replace(",low,10", ",alert,10"), "level"),
])
def test_bad_thresholds_fail(tmp_path, bad, message):
    with pytest.raises(ValueError, match=rf"thresholds\.csv row \d+: .*{message}"):
        _src(tmp_path, thresholds=bad)


def test_phases_load_and_validate(tmp_path):
    f = tmp_path / "phase.csv"
    f.write_text(_P + "Testville,Influenza,2025-W02,aedseo,in_season\n", encoding="utf-8")
    assert [(p.pathogen, p.phase) for p in PhaseSource(f).phases(pathogen="Influenza")] == [("Influenza", "in_season")]
    f.write_text(_P + "Testville,Measles,2025-W02,aedseo,in_season\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"phase\.csv row 1: .*pathogen"):
        PhaseSource(f)


def test_a_missing_phases_file_fails_at_load(tmp_path):
    # A configured path that doesn't exist is a typo, not "no phases".
    with pytest.raises(ValueError, match="phases file"):
        PhaseSource(tmp_path / "phase.csv")


def test_header_only_tables_load_empty(tmp_path):
    # A producer may export before the season's first assessment.
    src = _src(tmp_path, "", "")
    assert src.assessments() == [] and src.thresholds() == []
    (tmp_path / "phase.csv").write_text(_P, encoding="utf-8")
    assert PhaseSource(tmp_path / "phase.csv").phases() == []
