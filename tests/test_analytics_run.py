import math

import pytest

from health_signal.analytics import assess
from health_signal.analytics.backend import BackendError
from health_signal.analytics.store import SettingsChanged
from health_signal.assessments import AssessmentSource, PhaseSource, PhaseStreamSource
from health_signal.config import Config
from health_signal.profile import ERVISS
from analytics_support import (ERVISS_HEADER, FakeBackend, FlakyBackend, NeverFitsBackend, RecordingBackend,
                               erviss_rows, write_feed)


def _config(tmp_path, streams=True, year_start_week=21, covid_too=False, analytics=None, only_ili=False):
    feed = write_feed(tmp_path / "c",
                      erviss_rows("Greece", "ILIconsultationrate", "per_100k", [5, 6, 12, 30, 25, 9])
                      + erviss_rows("Greece", "SARIrate", "per_100k", [4, 5, 11, 20, 22, 21], survtype="SARI syndromic"))
    entry = {"pathogen": "Influenza", "location": "Greece", "streams": {"cases": "clinical/ili", "admissions": "clinical/sari"}}
    pages = [{"id": "clinical", "panels": [
        {"id": "ili", "query": {"feed": "clinical", "indicator": "ILIconsultationrate",
                                "dimensions": {"survtype": "primary care sentinel", "age": "total"}}},
        {"id": "sari", "query": {"feed": "clinical", "indicator": "SARIrate",
                                 "dimensions": {"survtype": "SARI syndromic", "age": "total"}}}][:1 if only_ili else 2]}]
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


def test_a_stream_panel_that_leaves_a_dimension_implicit_still_publishes(tmp_path):
    # The ILI query omits age, which the data pins to "total": the descriptor must carry what the series is.
    cfg = _config(tmp_path)
    cfg.targets[0].pages[0].panels[0].query.dimensions.pop("age")
    assess(cfg, backend=FakeBackend)
    streams = {s.role: s for s in PhaseStreamSource(tmp_path / "streams.csv", {"clinical": ERVISS}).streams()}
    assert streams["cases"].series == {"indicator": "ILIconsultationrate", "survtype": "primary care sentinel",
                                       "age": "total"}


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


class CrashesOnSari(FakeBackend):
    """Dies partway through a run, after the ILI series is graded: a killed process, not a week aedseo can't fit."""

    def fit(self, data):
        if data.values[0] == 4:   # the SARI series' first value
            raise RuntimeError("killed")
        return super().fit(data)


def test_a_run_that_dies_partway_leaves_the_served_tables_and_resumes(tmp_path):
    cfg = _config(tmp_path)
    assess(cfg, backend=FakeBackend)
    files = [tmp_path / "a" / "assessment.csv", tmp_path / "a" / "thresholds.csv", tmp_path / "phase.csv"]
    served = [f.read_bytes() for f in files]
    with pytest.raises(RuntimeError, match="killed"):
        assess(cfg, full=True, backend=CrashesOnSari)
    # The dashboard keeps serving the last complete run; what the dead one graded waits in its checkpoint.
    assert [f.read_bytes() for f in files] == served
    checkpoint = AssessmentSource(tmp_path / "a" / ".assess-checkpoint", ERVISS).assessments()
    assert {r.indicator for r in checkpoint} == {"ILIconsultationrate"}
    assert assess(cfg, backend=FakeBackend).weeks == 6   # resumes: only SARI's weeks are left
    resumed = [f.read_bytes() for f in files]
    assert not (tmp_path / "a" / ".assess-checkpoint").exists()
    assess(cfg, full=True, backend=FakeBackend)
    assert [f.read_bytes() for f in files] == resumed


def _two_feeds(tmp_path, sari_values=(4, 5, 11, 20, 22, 21)):
    ili = write_feed(tmp_path / "c", erviss_rows("Greece", "ILIconsultationrate", "per_100k", [5, 6, 12, 30, 25, 9]))
    sari = write_feed(tmp_path / "d", erviss_rows("Greece", "SARIrate", "per_100k", list(sari_values),
                                                  survtype="SARI syndromic"))
    panels = [{"id": "ili", "query": {"feed": "ili", "indicator": "ILIconsultationrate",
                                      "dimensions": {"survtype": "primary care sentinel", "age": "total"}}},
              {"id": "sari", "query": {"feed": "sari", "indicator": "SARIrate",
                                       "dimensions": {"survtype": "SARI syndromic", "age": "total"}}}]
    return Config.model_validate({
        "schema_version": "1", "site": {"title": "T"}, "surveillance": {"year_start_week": 21},
        "data": {"feeds": [{"id": "ili", "profile": "erviss", "dir": str(ili), "assessments": str(tmp_path / "a")},
                           {"id": "sari", "profile": "erviss", "dir": str(sari), "assessments": str(tmp_path / "b")}]},
        "targets": [{"id": "Influenza", "pages": [{"id": "clinical", "panels": panels}]}]})


def test_a_feed_whose_inputs_vanish_stops_the_run_before_any_table_changes(tmp_path):
    # Two assessed feeds: one emptied directory mustn't publish empty tables while the other still has series.
    cfg = _two_feeds(tmp_path)
    assess(cfg, backend=FakeBackend)
    before = (tmp_path / "b" / "assessment.csv").read_bytes()
    (tmp_path / "d" / "feed.csv").write_text(ERVISS_HEADER)
    with pytest.raises(RuntimeError, match="sari"):
        assess(cfg, full=True, backend=FakeBackend)
    assert (tmp_path / "b" / "assessment.csv").read_bytes() == before


def test_a_full_rebuild_that_dies_resumes_as_a_full_rebuild_of_every_feed(tmp_path):
    # The SARI feed revised a past week, which only a full run picks up. If the rebuild dies before reaching
    # that feed, the resume must still rebuild it, not carry on from its old served rows.
    assess(_two_feeds(tmp_path), backend=FakeBackend)
    cfg = _two_feeds(tmp_path, sari_values=(4, 5, 13, 20, 22, 21))
    with pytest.raises(RuntimeError, match="killed"):
        assess(cfg, full=True, backend=CrashesOnSari)
    assess(cfg, backend=FakeBackend)
    resumed = (tmp_path / "b" / "assessment.csv").read_bytes()
    assess(cfg, full=True, backend=FakeBackend)
    assert (tmp_path / "b" / "assessment.csv").read_bytes() == resumed


def test_a_series_moving_from_waves_to_seasons_needs_a_full_run(tmp_path):
    # ILI phased in waves while only influenza (a wave pathogen here) shows it; adding it to the COVID tab makes
    # it seasonal. Its stored rows were phased in waves, so an incremental run would mix the two.
    waves = {"wave_pathogens": ["Influenza"]}
    assess(_config(tmp_path, streams=False, analytics=waves), backend=FakeBackend)
    with pytest.raises(SettingsChanged, match="wave_series"):
        assess(_config(tmp_path, streams=False, covid_too=True, analytics=waves), backend=FakeBackend)


def test_a_new_wave_series_backfills_without_a_full_run(tmp_path):
    # Only a series that already has rows can have changed mode; a new one just starts in its own.
    waves = {"wave_pathogens": ["Influenza"]}
    assess(_config(tmp_path, streams=False, analytics=waves, only_ili=True), backend=FakeBackend)
    assert assess(_config(tmp_path, streams=False, analytics=waves), backend=FakeBackend).weeks == 6


def test_a_new_week_that_cannot_be_fitted_is_published_ungraded(tmp_path):
    # Stored history fitted fine, so one unfittable new week is the data, not a broken R: publish it as not
    # graded rather than leave the tiles on an older week.
    cfg = _config(tmp_path, streams=False)
    feed = tmp_path / "c" / "feed.csv"
    full_text = feed.read_text()
    feed.write_text("".join(line for line in full_text.splitlines(keepends=True)
                            if "2021-W05" not in line and "2021-W06" not in line))
    assess(cfg, backend=FlakyBackend)
    feed.write_text("".join(line for line in full_text.splitlines(keepends=True) if "2021-W06" not in line))
    summary = assess(cfg, backend=FlakyBackend)
    assert summary.weeks == 2 and any("no new week could be fitted" in w for w in summary.warnings)
    rows = AssessmentSource(tmp_path / "a", ERVISS).assessments(indicator="ILIconsultationrate")
    assert [(r.period, r.level) for r in rows][-1] == ("2021-W05", None)


def test_weeks_published_ungraded_are_refitted_by_the_next_run(tmp_path):
    # An outage (or a week the backend couldn't place) mustn't freeze those weeks as not graded: the next run
    # starts after the last week that was really fitted.
    cfg = _config(tmp_path, streams=False)
    feed = tmp_path / "c" / "feed.csv"
    feed.write_text("".join(line for line in feed.read_text().splitlines(keepends=True) if "2021-W06" not in line))
    assess(cfg, full=True, backend=FakeBackend)
    graded = (tmp_path / "a" / "assessment.csv").read_bytes()
    assess(cfg, full=True, backend=FlakyBackend)   # W05, the last week, can't be fitted this time
    assert assess(cfg, backend=FakeBackend).weeks == 2   # each series' W05, refitted
    assert (tmp_path / "a" / "assessment.csv").read_bytes() == graded


class BrokenR(FakeBackend):
    def fit(self, data):
        raise BackendError("Error in estimate_disease_threshold: could not find function")


def test_a_broken_backend_stops_even_an_incremental_run_before_anything_changes(tmp_path):
    # Unlike a week the data can't support, a broken R must not be published as "not graded".
    cfg = _config(tmp_path)
    feed = tmp_path / "c" / "feed.csv"
    full_text = feed.read_text()
    feed.write_text("".join(line for line in full_text.splitlines(keepends=True) if "2021-W06" not in line))
    assess(cfg, backend=FakeBackend)
    files = [tmp_path / "a" / "assessment.csv", tmp_path / "a" / "thresholds.csv", tmp_path / "phase.csv"]
    before = [f.read_bytes() for f in files]
    feed.write_text(full_text)
    with pytest.raises(BackendError, match="could not find function"):
        assess(cfg, backend=BrokenR)
    assert [f.read_bytes() for f in files] == before


def test_a_phase_that_cannot_be_written_leaves_every_table_as_it_was(tmp_path):
    assess(_config(tmp_path), backend=FakeBackend)
    before = (tmp_path / "a" / "assessment.csv").read_bytes()
    broken = {"pathogen": "Influenza", "location": "Cyprus", "streams": {"cases": "clinical/ili",
                                                                          "admissions": "clinical/sari"}}
    cfg = _config(tmp_path, streams=False, analytics={"phase_streams": [broken]})   # (re)writes the feed
    feed = tmp_path / "c" / "feed.csv"
    feed.write_text(feed.read_text() + erviss_rows("Greece", "ILIconsultationrate", "per_100k", [7],
                                                   periods=["2021-W07"]))   # a new week the run would publish
    with pytest.raises(ValueError, match="Cyprus"):
        assess(cfg, backend=FakeBackend)
    assert (tmp_path / "a" / "assessment.csv").read_bytes() == before


def test_parallel_jobs_match_a_serial_run(tmp_path):
    cfg = _config(tmp_path, streams=False)
    assess(cfg, backend=FakeBackend)
    serial = (tmp_path / "a" / "assessment.csv").read_bytes()
    assess(cfg, full=True, jobs=2, backend=FakeBackend)
    assert (tmp_path / "a" / "assessment.csv").read_bytes() == serial


def test_nothing_gradeable_fails_the_run(tmp_path):
    cfg = _config(tmp_path, streams=False)
    write_feed(tmp_path / "c", erviss_rows("Greece", "ILIconsultationrate", "per_100k", [5]))
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


def test_a_full_run_where_aedseo_never_fits_leaves_the_served_tables(tmp_path):
    # A broken R install on a --full run must not checkpoint ungraded rows over good tables.
    cfg = _config(tmp_path, streams=False)
    assess(cfg, backend=FakeBackend)
    before = (tmp_path / "a" / "assessment.csv").read_bytes()
    with pytest.raises(RuntimeError, match="no week could be fitted"):
        assess(cfg, full=True, backend=NeverFitsBackend)
    assert (tmp_path / "a" / "assessment.csv").read_bytes() == before


class NoBandsBackend(FakeBackend):
    """Returns every week, but never with usable bands: as broken as never fitting, though no fit raises."""
    thresholds = (math.nan,) * 4


def test_a_full_run_where_no_week_gets_bands_leaves_the_served_tables(tmp_path):
    cfg = _config(tmp_path, streams=False)
    assess(cfg, backend=FakeBackend)
    before = (tmp_path / "a" / "assessment.csv").read_bytes()
    with pytest.raises(RuntimeError, match="no week could be fitted"):
        assess(cfg, full=True, backend=NoBandsBackend)
    assert (tmp_path / "a" / "assessment.csv").read_bytes() == before


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
