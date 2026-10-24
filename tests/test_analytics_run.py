import pytest

from health_signal.analytics import assess
from health_signal.assessments import AssessmentSource, PhaseSource, PhaseStreamSource
from health_signal.config import Config
from health_signal.profile import ERVISS
from analytics_support import FakeBackend, erviss_rows, write_feed


def _config(tmp_path, streams=True):
    feed = write_feed(tmp_path / "c",
                      erviss_rows("Greece", "ILIconsultationrate", "per_100k", [5, 6, 12, 30, 25, 9])
                      + erviss_rows("Greece", "SARIrate", "per_100k", [4, 5, 11, 20, 22, 21], survtype="SARI syndromic"))
    entry = {"pathogen": "Influenza", "location": "Greece", "streams": {"cases": "clinical/ili", "admissions": "clinical/sari"}}
    return Config.model_validate({
        "schema_version": "1", "site": {"title": "T"}, "surveillance": {"year_start_week": 21},
        "data": {"feeds": [{"id": "clinical", "profile": "erviss", "dir": str(feed), "assessments": str(tmp_path / "a")}],
                 "phases": str(tmp_path / "phase.csv"), "phase_streams": str(tmp_path / "streams.csv")},
        "targets": [{"id": "Influenza", "pages": [{"id": "clinical", "panels": [
            {"id": "ili", "query": {"feed": "clinical", "indicator": "ILIconsultationrate",
                                    "dimensions": {"survtype": "primary care sentinel", "age": "total"}}},
            {"id": "sari", "query": {"feed": "clinical", "indicator": "SARIrate",
                                     "dimensions": {"survtype": "SARI syndromic", "age": "total"}}}]}]}],
        "analytics": {"phase_streams": [entry] if streams else []}})


def test_assess_writes_tables_the_app_loads(tmp_path):
    summary = assess(_config(tmp_path), backend=FakeBackend)
    assert (summary.series, summary.weeks, summary.graded) == (2, 12, 8)   # 4 fittable weeks each
    assert len(AssessmentSource(tmp_path / "a", ERVISS).assessments(indicator="SARIrate")) == 6   # every week
    phases = PhaseSource(tmp_path / "phase.csv").phases()
    assert len(phases) == 4 and {p.phase for p in phases} <= {"in_season", "out_of_season"}
    streams = sorted(PhaseStreamSource(tmp_path / "streams.csv", {"clinical": ERVISS}).streams(), key=lambda s: s.role)
    assert [s.role for s in streams] == ["admissions", "cases"]
    assert streams[0].series == {"indicator": "SARIrate", "survtype": "SARI syndromic", "age": "total"}


def test_a_rerun_without_new_data_changes_nothing(tmp_path):
    cfg = _config(tmp_path)
    assess(cfg, backend=FakeBackend)
    files = [tmp_path / "a" / "assessment.csv", tmp_path / "a" / "thresholds.csv", tmp_path / "phase.csv"]
    before = [f.read_bytes() for f in files]
    assert assess(cfg, backend=FakeBackend).weeks == 0
    assert [f.read_bytes() for f in files] == before


def test_incremental_matches_a_full_rebuild(tmp_path):
    cfg = _config(tmp_path)
    feed = tmp_path / "c" / "feed.csv"
    full_text = feed.read_text()
    lines = full_text.splitlines(keepends=True)
    feed.write_text("".join(line for line in lines if "2021-W05" not in line and "2021-W06" not in line))
    assess(cfg, backend=FakeBackend)
    feed.write_text(full_text)
    assert assess(cfg, backend=FakeBackend).weeks == 4
    incremental = [(tmp_path / "a" / n).read_bytes() for n in ("assessment.csv", "thresholds.csv")]
    assess(cfg, full=True, backend=FakeBackend)
    assert [(tmp_path / "a" / n).read_bytes() for n in ("assessment.csv", "thresholds.csv")] == incremental


def test_parallel_jobs_match_a_serial_run(tmp_path):
    cfg = _config(tmp_path, streams=False)
    assess(cfg, backend=FakeBackend)
    serial = (tmp_path / "a" / "assessment.csv").read_bytes()
    assess(cfg, full=True, jobs=2, backend=FakeBackend)
    assert (tmp_path / "a" / "assessment.csv").read_bytes() == serial


def test_nothing_gradeable_fails_the_run(tmp_path):
    cfg = _config(tmp_path, streams=False)
    (tmp_path / "c" / "feed.csv").write_text(
        "location,period,survtype,pathogen,pathogentype,pathogensubtype,age,indicator,value,unit\n"
        "Greece,2021-W01,primary care sentinel,,,,total,ILIconsultationrate,5,per_100k\n")
    with pytest.raises(RuntimeError, match="nothing could be graded"):
        assess(cfg, backend=FakeBackend)
