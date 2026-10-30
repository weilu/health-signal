from health_signal.analytics.series import assessed_series
from health_signal.config import Config, SiteConfig
from health_signal.datasource import FileDataSource
from health_signal.profile import PROFILES
from analytics_support import erviss_rows, weeks, write_feed


def _setup(tmp_path, body, panels, filters=None):
    feed = write_feed(tmp_path / "c", body)
    cfg = Config(schema_version="1", site=SiteConfig(title="T"), filters=filters or {},
                 data={"feeds": [{"id": "clinical", "profile": "erviss", "dir": str(feed),
                                  "assessments": str(tmp_path / "a")}]},
                 targets=[{"id": "Influenza", "pages": [{"id": "clinical", "panels": panels}]}])
    return cfg, {"clinical": FileDataSource(feed, PROFILES["erviss"])}


def _panel(pid, indicator, **dims):
    return {"id": pid, "query": {"feed": "clinical", "indicator": indicator, "dimensions": dims}}


def test_each_single_series_panel_is_assessed_at_every_location(tmp_path):
    body = (erviss_rows("Greece", "ILIconsultationrate", "per_100k", [1.5, 2.5, 3.5])
            + erviss_rows("Cyprus", "ILIconsultationrate", "per_100k", [4.0, 5.0, 6.0]))
    split = {**_panel("split", "ILIconsultationrate", survtype="primary care sentinel"), "series_by": "age"}
    cfg, sources = _setup(tmp_path, body, [_panel("ili", "ILIconsultationrate", survtype="primary care sentinel",
                                                  age="total"), split])
    series, refs, warnings = assessed_series(cfg, sources)
    assert sorted(s.location for s in series) == ["Cyprus", "Greece"]          # the series_by panel adds nothing
    greece = refs[("Influenza", "Greece", "clinical/ili")]
    assert (greece.kind, greece.exposure, greece.scaled) == ("incidence", [1.0] * 3, True)
    assert greece.dimensions == {"survtype": "primary care sentinel", "age": "total"} and not warnings


def test_a_query_matching_several_rows_per_week_is_skipped_with_a_warning(tmp_path):
    body = (erviss_rows("Greece", "ILIconsultationrate", "per_100k", [1, 2, 3], age="0-4")
            + erviss_rows("Greece", "ILIconsultationrate", "per_100k", [4, 5, 6], age="65+"))
    cfg, sources = _setup(tmp_path, body, [_panel("ili", "ILIconsultationrate", survtype="primary care sentinel")])
    series, _, warnings = assessed_series(cfg, sources)
    assert series == [] and "clinical/ili" in warnings[0] and "Greece" in warnings[0]


def test_a_query_matching_different_series_in_different_weeks_is_skipped_with_a_warning(tmp_path):
    # One row a week, but 0-4 for two weeks then 65+: grading them as one series would mix two populations.
    p = weeks(2021, 4)
    body = (erviss_rows("Greece", "ILIconsultationrate", "per_100k", [1, 2], age="0-4", periods=p[:2])
            + erviss_rows("Greece", "ILIconsultationrate", "per_100k", [4, 5], age="65+", periods=p[2:]))
    cfg, sources = _setup(tmp_path, body, [_panel("ili", "ILIconsultationrate", survtype="primary care sentinel")])
    series, _, warnings = assessed_series(cfg, sources)
    assert series == [] and "clinical/ili" in warnings[0] and "age" in warnings[0]


def test_a_query_whose_unit_changes_is_skipped_with_a_warning(tmp_path):
    p = weeks(2021, 4)
    body = (erviss_rows("Greece", "ILIconsultationrate", "per_100k", [1, 2], periods=p[:2])
            + erviss_rows("Greece", "ILIconsultationrate", "per_100_consultations", [4, 5], periods=p[2:]))
    cfg, sources = _setup(tmp_path, body, [_panel("ili", "ILIconsultationrate", survtype="primary care sentinel",
                                                  age="total")])
    series, _, warnings = assessed_series(cfg, sources)
    assert series == [] and "unit" in warnings[0]


def test_a_log_scale_reading_is_skipped_with_a_warning(tmp_path):
    # log10 copies/L can't be graded as a linear rate: a rise from 3 to 4 is tenfold, not a third.
    feed = tmp_path / "w"
    feed.mkdir()
    (feed / "feed.csv").write_text("location,period,pathogen,aggregation,indicator,value,unit,quality\n"
                                   + "".join(f"Attica,2021-W0{i},Influenza,floMean,fluA,{v},log10cpL,\n"
                                             for i, v in enumerate([3.1, 3.4, 4.0], start=1)), encoding="utf-8")
    cfg = Config(schema_version="1", site=SiteConfig(title="T"),
                 data={"feeds": [{"id": "ww", "profile": "phes_odm", "dir": str(feed), "assessments": str(tmp_path / "a")}]},
                 targets=[{"id": "Influenza", "pages": [{"id": "ww", "panels": [
                     {"id": "flu", "query": {"feed": "ww", "indicator": "fluA", "dimensions": {"aggregation": "floMean"}}}]}]}])
    series, _, warnings = assessed_series(cfg, {"ww": FileDataSource(feed, PROFILES["phes_odm"])})
    assert series == [] and "log10cpL" in warnings[0]


def test_a_rate_only_takes_the_denominator_of_its_own_series(tmp_path):
    # Positivity for all influenza (no type) mustn't borrow the tests of influenza A alone as its exposure.
    rows = "".join(f"Greece,2021-W0{i},primary care sentinel,Influenza,{ptype},,total,{ind},{v},{unit}\n"
                   for i in (1, 2, 3)
                   for ptype, ind, v, unit in (("", "positivity", 10 + i, "percent"),
                                               ("Influenza A", "tests", 100, "count")))
    cfg, sources = _setup(tmp_path, rows, [_panel("pos", "positivity", survtype="primary care sentinel",
                                                  pathogen="Influenza", age="total")])
    series, _, warnings = assessed_series(cfg, sources)
    assert series == [] and "tests" in warnings[0]


def test_counts_use_the_cases_path(tmp_path):
    body = erviss_rows("Greece", "hospitaladmissions", "count", [3, 4, 5], survtype="non-sentinel", pathogen="Influenza")
    cfg, sources = _setup(tmp_path, body, [_panel("hosp", "hospitaladmissions", survtype="non-sentinel",
                                                  pathogen="Influenza", age="total")])
    [s], _, _ = assessed_series(cfg, sources)
    assert (s.kind, s.exposure) == ("count", [])


def test_positivity_uses_tests_as_exposure_and_skips_weeks_without_them(tmp_path):
    p = weeks(2021, 4)
    body = (erviss_rows("Greece", "positivity", "percent", [10, 20, 30, 40], survtype="non-sentinel",
                        pathogen="Influenza", periods=p)
            + erviss_rows("Greece", "tests", "count", [100, None, 0, 400], survtype="non-sentinel",
                          pathogen="Influenza", periods=p))
    cfg, sources = _setup(tmp_path, body, [_panel("pos", "positivity", survtype="non-sentinel", pathogen="Influenza",
                                                  age="total")])
    [s], _, _ = assessed_series(cfg, sources)
    assert (s.periods, s.exposure, s.per) == ([p[0], p[3]], [100.0, 400.0], 100.0)   # missing and zero tests dropped


def test_a_series_shown_on_two_panels_is_assessed_once(tmp_path):
    body = erviss_rows("Greece", "ILIconsultationrate", "per_100k", [1, 2, 3])
    query = dict(survtype="primary care sentinel", age="total")
    cfg, sources = _setup(tmp_path, body, [_panel("a", "ILIconsultationrate", **query),
                                           _panel("b", "ILIconsultationrate", **query)])
    series, refs, _ = assessed_series(cfg, sources)
    assert len(series) == 1 and refs[("Influenza", "Greece", "clinical/a")] is refs[("Influenza", "Greece", "clinical/b")]


def test_only_the_selectable_locations_are_assessed_when_the_filter_lists_them(tmp_path):
    # A feed covering every EU country shouldn't cost aedseo time on regions the dashboard can't show.
    body = (erviss_rows("Greece", "ILIconsultationrate", "per_100k", [1, 2, 3])
            + erviss_rows("Cyprus", "ILIconsultationrate", "per_100k", [4, 5, 6]))
    location = {"location": {"default": "Greece", "options": [{"value": "Greece"}, {"value": "Attica"}]}}
    cfg, sources = _setup(tmp_path, body, [_panel("ili", "ILIconsultationrate", survtype="primary care sentinel",
                                                  age="total")], filters=location)
    series, _, _ = assessed_series(cfg, sources)
    assert [s.location for s in series] == ["Greece"]


def test_a_rate_without_a_denominator_of_its_own_is_skipped_with_a_warning(tmp_path):
    p = weeks(2021, 3)
    positivity = erviss_rows("Greece", "positivity", "percent", [10, 20, 30], survtype="non-sentinel",
                             pathogen="Influenza", periods=p)
    # tests split by a dimension the rate leaves blank (type A and B): neither is the untyped rate's denominator
    split_tests = "".join(f"Greece,{w},non-sentinel,Influenza,Influenza {t},,total,tests,100,count\n"
                          for w in p for t in ("A", "B"))
    panel = [{"id": "pos", "query": {"feed": "clinical", "indicator": "positivity",
                                     "dimensions": {"survtype": "non-sentinel", "pathogen": "Influenza"}}}]
    for name, body in (("split", positivity + split_tests), ("none", positivity)):
        cfg, sources = _setup(tmp_path / name, body, panel)
        series, _, warnings = assessed_series(cfg, sources)
        assert series == [] and "clinical/pos" in warnings[0] and "no tests" in warnings[0]


def test_below_detection_rows_are_marked_censored(tmp_path):
    feed = tmp_path / "w"
    feed.mkdir()
    (feed / "feed.csv").write_text("location,period,pathogen,aggregation,indicator,value,unit,quality\n"
                                   "Attica,2021-W01,Influenza,floMean,fluA,1200,gcDay100k,\n"
                                   "Attica,2021-W02,Influenza,floMean,fluA,0,gcDay100k,beLOD\n"
                                   "Attica,2021-W03,Influenza,floMean,fluA,900,gcDay100k,\n", encoding="utf-8")
    cfg = Config(schema_version="1", site=SiteConfig(title="T"),
                 data={"feeds": [{"id": "ww", "profile": "phes_odm", "dir": str(feed), "assessments": str(tmp_path / "a")}]},
                 targets=[{"id": "Influenza", "pages": [{"id": "ww", "panels": [
                     {"id": "flu", "query": {"feed": "ww", "indicator": "fluA", "dimensions": {"aggregation": "floMean"}}}]}]}])
    [s], _, _ = assessed_series(cfg, {"ww": FileDataSource(feed, PROFILES["phes_odm"])})
    assert s.censored == [False, True, False] and s.values == [1200.0, 0.0, 900.0]
