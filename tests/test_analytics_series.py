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
    assert (greece.kind, greece.exposure, greece.scale) == ("incidence", [1.0] * 3, 100.0)   # 1.5 lifted to >= 100
    assert greece.dimensions == {"survtype": "primary care sentinel", "age": "total"} and not warnings


def test_a_query_matching_several_rows_per_week_is_skipped_with_a_warning(tmp_path):
    body = (erviss_rows("Greece", "ILIconsultationrate", "per_100k", [1, 2, 3], age="0-4")
            + erviss_rows("Greece", "ILIconsultationrate", "per_100k", [4, 5, 6], age="65+"))
    cfg, sources = _setup(tmp_path, body, [_panel("ili", "ILIconsultationrate", survtype="primary care sentinel")])
    series, _, warnings = assessed_series(cfg, sources)
    assert series == [] and "clinical/ili" in warnings[0] and "Greece" in warnings[0]


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


def test_a_denominator_matching_several_rows_or_none_is_skipped_with_a_warning(tmp_path):
    p = weeks(2021, 3)
    positivity = erviss_rows("Greece", "positivity", "percent", [10, 20, 30], survtype="non-sentinel",
                             pathogen="Influenza", periods=p)
    # tests split by a dimension the rate doesn't pin (type A and B), so two rows match each week
    split_tests = "".join(f"Greece,{w},non-sentinel,Influenza,Influenza {t},,total,tests,100,count\n"
                          for w in p for t in ("A", "B"))
    panel = [{"id": "pos", "query": {"feed": "clinical", "indicator": "positivity",
                                     "dimensions": {"survtype": "non-sentinel", "pathogen": "Influenza"}}}]
    for body, message in ((positivity + split_tests, "several"), (positivity, "no tests")):
        cfg, sources = _setup(tmp_path / message, body, panel)
        series, _, warnings = assessed_series(cfg, sources)
        assert series == [] and "clinical/pos" in warnings[0] and message in warnings[0]
