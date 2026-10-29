import pytest

from health_signal.analytics import assess
from health_signal.analytics.store import SettingsChanged
from health_signal.assessments import AssessmentSource, PhaseSource, PhaseStreamSource
from health_signal.config import Config
from health_signal.profile import ERVISS
from analytics_support import FakeBackend, FlakyBackend, NeverFitsBackend, RecordingBackend, erviss_rows, write_feed


def _config(tmp_path, streams=True, year_start_week=21, covid_too=False, analytics=None):
    feed = write_feed(tmp_path / "c",
                      erviss_rows("Greece", "ILIconsultationrate", "per_100k", [5, 6, 12, 30, 25, 9])
                      + erviss_rows("Greece", "SARIrate", "per_100k", [4, 5, 11, 20, 22, 21], survtype="SARI syndromic"))
    entry = {"pathogen": "Influenza", "location": "Greece", "streams": {"cases": "clinical/ili", "admissions": "clinical/sari"}}
    pages = [{"id": "clinical", "panels": [
        {"id": "ili", "query": {"feed": "clinical", "indicator": "ILIconsultationrate",
                                "dimensions": {"survtype": "primary care sentinel", "age": "total"}}},
        {"id": "sari", "query": {"feed": "clinical", "indicator": "SARIrate",
                                 "dimensions": {"survtype": "SARI syndromic", "age": "total"}}}]}]
    targets = [{"id": "SARS-CoV-2", "pages": pages}] * covid_too + [{"id": "Influenza", "pages": pages}]
    return Config.model_validate({
        "schema_version": "1", "site": {"title": "T"}, "surveillance": {"year_start_week": year_start_week},
        "data": {"feeds": [{"id": "clinical", "profile": "erviss", "dir": str(feed), "assessments": str(tmp_path / "a")}],
                 "phases": str(tmp_path / "phase.csv"), "phase_streams": str(tmp_path / "streams.csv")},
        "targets": targets,
        "analytics": {"phase_streams": [entry] if streams else [], **(analytics or {})}})


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
    with pytest.raises(RuntimeError, match="no week could be fitted"):
        assess(cfg, backend=FakeBackend)


def test_a_season_starting_in_week_1_fails_before_any_fitting(tmp_path):
    # aedseo's season_end would be week 0, so every fit would fail and the run would publish blank tables.
    cfg = _config(tmp_path, streams=False, year_start_week=1)
    with pytest.raises(RuntimeError, match="year_start_week"):
        assess(cfg, backend=FakeBackend)


def test_a_run_where_aedseo_never_fits_fails_even_if_zeros_are_graded(tmp_path):
    cfg = _config(tmp_path, streams=False)
    feed = tmp_path / "c" / "feed.csv"
    feed.write_text(feed.read_text().replace(",5,per_100k", ",0,per_100k"))   # a reported zero grades without a fit
    with pytest.raises(RuntimeError, match="no week could be fitted"):
        assess(cfg, backend=NeverFitsBackend)


def test_incremental_matches_a_full_rebuild_across_an_unfittable_week(tmp_path):
    cfg = _config(tmp_path, streams=False)
    feed = tmp_path / "c" / "feed.csv"
    full_text = feed.read_text()
    feed.write_text("".join(line for line in full_text.splitlines(keepends=True) if "2021-W06" not in line))
    assess(cfg, backend=FlakyBackend)      # week 5 can't be fitted: its row has no phase
    feed.write_text(full_text)
    assess(cfg, backend=FlakyBackend)
    incremental = (tmp_path / "a" / "assessment.csv").read_bytes()
    assess(cfg, full=True, backend=FlakyBackend)
    assert (tmp_path / "a" / "assessment.csv").read_bytes() == incremental


def test_a_series_shared_with_a_season_pathogen_is_phased_as_a_season(tmp_path):
    # ILI sits on the COVID and the influenza tabs; COVID's waves mustn't decide influenza's chart shading.
    assess(_config(tmp_path, streams=False, covid_too=True), backend=FakeBackend)   # SARS-CoV-2 waves by default
    phases = {r.phase for r in AssessmentSource(tmp_path / "a", ERVISS).assessments()}
    assert "in_season" in phases and not phases & {"in_wave", "between_waves"}


def test_no_series_at_all_fails_before_replacing_good_tables(tmp_path):
    # An emptied or mis-mounted feed dir must not wipe the served assessments on a --full run.
    cfg = _config(tmp_path, streams=False)
    assess(cfg, backend=FakeBackend)
    before = (tmp_path / "a" / "assessment.csv").read_bytes()
    (tmp_path / "c" / "feed.csv").unlink()
    with pytest.raises(RuntimeError, match="no series"):
        assess(cfg, full=True, backend=FakeBackend)
    assert (tmp_path / "a" / "assessment.csv").read_bytes() == before


def test_the_configured_wave_end_reaches_only_wave_series(tmp_path):
    wave_end = {"steps_with_decrease": 3, "burden_level_decrease": "medium"}
    recorder = RecordingBackend()
    assess(_config(tmp_path, streams=False, analytics={"wave_pathogens": ["Influenza"], "aedseo": {"wave_end": wave_end}}),
           backend=lambda: recorder)
    assert {(i.waves.steps_with_decrease, i.waves.burden_level_decrease) for i in recorder.inputs} == {(3, "medium")}
    recorder.inputs.clear()
    assess(_config(tmp_path, streams=False, analytics={"aedseo": {"wave_end": wave_end}}), full=True, backend=lambda: recorder)
    assert {i.waves for i in recorder.inputs} == {None}


def test_a_changed_wave_end_needs_a_full_run(tmp_path):
    assess(_config(tmp_path, streams=False), backend=FakeBackend)
    cfg = _config(tmp_path, streams=False, analytics={"aedseo": {"wave_end": {"steps_with_decrease": 3}}})
    with pytest.raises(SettingsChanged, match="steps_with_decrease"):
        assess(cfg, backend=FakeBackend)
