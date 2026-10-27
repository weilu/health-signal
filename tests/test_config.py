import pytest
from pydantic import ValidationError
from health_signal.config import Branding, Config, DataConfig, Filters, Page, Panel, SiteConfig, Target, load_config, page_path
from health_signal.profile import PATHOGENS


def test_load_valid_config(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text(
        "schema_version: '0.1'\n"
        "site:\n"
        "  title: 'X'\n",
        encoding="utf-8",
    )
    cfg = load_config(f)
    assert cfg.schema_version == "0.1"
    assert cfg.site.title == "X"
    assert cfg.site.default_locale == "en"      # default applied


def test_missing_required_field_raises(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("site:\n  title: 'X'\n", encoding="utf-8")   # no schema_version
    with pytest.raises(ValidationError):
        load_config(f)


def _cfg(**site_over):
    site = {"title": "Demo", "default_locale": "en", "locales": ["en", "el"]}
    site.update(site_over)
    return Config(schema_version="0.1", site=SiteConfig(**site))


def test_bootstrap_config_is_whitelisted():
    cfg = _cfg(public_paths=["/about"])
    b = cfg.bootstrap_config()
    assert b == {
        "title": "Demo",
        "branding": {"logo": None, "favicon": None, "theme": {}},
        "defaultLocale": "en",
        "locales": ["en", "el"],
    }
    # server-only fields never leak into the client payload
    assert "public_paths" not in b and "schema_version" not in b


def test_client_config_adds_structure_but_not_server_only():
    cfg = Config(
        schema_version="0.1",
        site=SiteConfig(title="Demo", public_paths=["/about"]),
        targets=[Target(id="SARS-CoV-2", pages=[Page(id="overview")])],
    )
    c = cfg.client_config()
    assert c["title"] == "Demo"
    assert c["targets"][0]["id"] == "SARS-CoV-2"
    assert c["targets"][0]["pages"][0]["path"] == "/sars-cov-2/overview"  # derived, sent as data
    assert "public_paths" not in c and "schema_version" not in c


def test_empty_targets_projects_cleanly():
    c = _cfg().client_config()
    assert c["targets"] == []


def test_default_locale_must_be_in_locales():
    # default_locale must be a configured locale (fallbackLng needs a catalog).
    with pytest.raises(ValidationError):
        SiteConfig(title="D", default_locale="el")  # locales defaults to ["en"]
    SiteConfig(title="D", default_locale="el", locales=["en", "el"])  # offered -> ok


def test_branding_projection_is_json_safe():
    import datetime, json
    cfg = Config(
        schema_version="0.1",
        site=SiteConfig(title="D"),
        branding=Branding(theme={"launched": datetime.date(2026, 1, 1)}),
    )
    # Non-JSON YAML scalars (e.g. an unquoted ISO date) must serialize cleanly downstream.
    json.dumps(cfg.bootstrap_config())
    json.dumps(cfg.client_config())


_PANEL = {"id": "p", "series_by": "survtype",
          "query": {"feed": "clinical", "indicator": "positivity", "dimensions": {"pathogen": "Influenza"}}}
_FEEDS = DataConfig(feeds=[{"id": "clinical", "profile": "erviss", "dir": "d/c"},
                           {"id": "wastewater", "profile": "phes_odm", "dir": "d/w"}])


def _with_panel(panel, data=_FEEDS):
    return Config(schema_version="1", site=SiteConfig(title="T"), data=data,
                  targets=[Target(id="Influenza", pages=[Page(id="o", panels=[Panel(**panel)])])])


def test_panel_parses_and_reaches_client_config():
    panel = _with_panel(_PANEL).client_config()["targets"][0]["pages"][0]["panels"][0]
    assert panel["query"] == {"feed": "clinical", "indicator": "positivity", "dimensions": {"pathogen": "Influenza"}}
    assert panel["series_by"] == "survtype"


def test_a_panel_is_judged_by_its_own_feeds_profile():
    query = {"indicator": "fluA", "dimensions": {"aggregation": "floMean"}}  # ODM terms, not ERVISS ones
    ww = _with_panel({"id": "w", "query": {"feed": "wastewater", **query}})
    assert ww.client_config()["targets"][0]["pages"][0]["panels"][0]["query"] == {"feed": "wastewater", **query}
    with pytest.raises(ValidationError, match="feed 'clinical'"):
        _with_panel({"id": "w", "query": {"feed": "clinical", **query}})


@pytest.mark.parametrize("bad", [
    {"query": {"feed": "clinical", "indicator": "bogus"}},                                       # not an ERVISS indicator
    {"query": {"feed": "clinical", "indicator": "positivity", "dimensions": {"pathogen": "Measles"}}},
    {"query": {"feed": "clinical", "indicator": "positivity", "dimensions": {"agee": "65+"}}},  # not an ERVISS dimension
    {"series_by": "colour"},                                                                     # not an ERVISS dimension
    {"query": {"feed": "sewage", "indicator": "positivity"}},                                    # no such feed
    {"series_by": None, "query": {"feed": "wastewater", "indicator": "fluA", "dimensions": {"survtype": "non-sentinel"}}},  # ERVISS dim on the ODM feed
    {"series_by": None, "query": {"feed": "wastewater", "indicator": "positivity"}},                                # ERVISS indicator on the ODM feed
    {"series_by": None, "query": {"feed": "wastewater", "indicator": "fluA", "dimensions": {"pathogen": "RSV"}}},  # fluA is always Influenza
])
def test_panel_config_typos_fail_at_load(bad):
    with pytest.raises(ValidationError, match="panel 'p'"):
        _with_panel({**_PANEL, **bad})


@pytest.mark.parametrize("bad", [
    {"type": "bar"},                                                                       # only timeseries exists
    {"query": {"indicator": "positivity"}},                                                # feed is required
    {"query": {"feed": "clinical", "indicator": "positivity", "pathogen": "Influenza"}},  # dimensions belong under `dimensions`
])
def test_panel_shape_errors_fail_at_load(bad):
    with pytest.raises(ValidationError):
        Panel(**{**_PANEL, **bad})


def test_panels_need_a_data_block():
    with pytest.raises(ValidationError, match="feed 'clinical'"):
        _with_panel(_PANEL, data=None)


@pytest.mark.parametrize("bad", [
    {"feeds": []},
    {"feeds": [{"id": "c", "profile": "erviss", "dir": "a"}, {"id": "c", "profile": "erviss", "dir": "b"}]},  # duplicate id
    {"feeds": [{"id": "c", "profile": "nwss", "dir": "a"}]},                                                  # unknown profile
    {"feeds": [{"id": "", "profile": "erviss", "dir": "a"}]},                                                 # the client drops empty params
    {"dir": "a"},                                                                                             # the old single-feed form
])
def test_data_config_errors_fail_at_load(bad):
    with pytest.raises(ValidationError):
        DataConfig(**bad)


def test_example_config_loads():
    cfg = load_config("examples/greece.dashboard.yaml")
    assert all(p.panels for t in cfg.targets for p in t.pages)
    assert {f.id for f in cfg.data.feeds} == {"clinical", "wastewater"}
    # Every target pairs clinical and wastewater pages, the way greece-public-health's source tabs do.
    assert all([p.id for p in t.pages] == ["overview", "clinical", "wastewater"] for t in cfg.targets)
    assert all([x.type for x in t.pages[0].panels] == ["phase", "summary"] for t in cfg.targets)


@pytest.mark.parametrize("bad", [
    {"query": {"feed": "clinical", "indicator": "positivity", "dimensiosn": {"age": "65+"}}},  # misspelt key
    {"seriesby": "survtype"},                               # misspelt panel key
])
def test_panel_unknown_keys_fail_at_load(bad):
    with pytest.raises(ValidationError):
        Panel(**{**_PANEL, **bad})


def test_page_unknown_key_fails_at_load():
    with pytest.raises(ValidationError):
        Page(id="o", panel=[_PANEL])  # misspelt `panels`


def _cfg_pages(*pages):
    return dict(schema_version="1", site=SiteConfig(title="T"),
                targets=[Target(id=key, pages=[p]) for key, p in zip(["SARS-CoV-2", "Influenza", "RSV"], pages)])


def test_page_ids_repeat_across_targets_but_not_within_one():
    # An id names a page inside its target's tab row; the derived paths differ by target.
    Config(**_cfg_pages(Page(id="clinical"), Page(id="clinical")))
    with pytest.raises(ValidationError, match="page id"):
        Target(id="Influenza", pages=[Page(id="clinical"), Page(id="clinical")])

def test_duplicate_target_ids_fail_at_load():
    with pytest.raises(ValidationError, match="target ids"):
        Config(schema_version="1", site=SiteConfig(title="T"),
               targets=[Target(id="Influenza", pages=[Page(id="a")]), Target(id="Influenza", pages=[Page(id="b")])])


def test_duplicate_panel_ids_on_a_page_fail_at_load():
    with pytest.raises(ValidationError):
        Page(id="o", panels=[Panel(**_PANEL), Panel(**_PANEL)])


@pytest.mark.parametrize("key", ["location", "week_from", "week_to"])
def test_panel_query_leaves_location_and_dates_to_dashboard_filters(key):
    with pytest.raises(ValidationError):
        Panel(**{**_PANEL, "query": {"feed": "clinical", "indicator": "positivity", key: "x"}})
    with pytest.raises(ValidationError):  # nor can they hide among the dimensions
        _with_panel({**_PANEL, "query": {"feed": "clinical", "indicator": "positivity", "dimensions": {key: "x"}}})


_LOC = {"location": {"default": "Greece", "options": [{"value": "Greece", "label_key": "locations.national"}, {"value": "Attica"}]}}


def test_location_filter_reaches_client_config():
    cfg = Config(schema_version="1", site=SiteConfig(title="T"), filters=Filters(**_LOC))
    loc = cfg.client_config()["filters"]["location"]
    assert loc["default"] == "Greece" and [o["value"] for o in loc["options"]] == ["Greece", "Attica"]


@pytest.mark.parametrize("bad", [
    {"default": "Crete", "options": [{"value": "Greece"}]},                  # default not offered
    {"default": "Greece", "options": [{"value": "Greece"}, {"value": "Greece"}]},  # duplicate option
    {"default": "Greece", "options": []},                                    # nothing to choose
    {"default": "Greece", "options": [{"value": "Greece"}, {"value": ""}]},  # "" would query every region
])
def test_location_filter_typos_fail_at_load(bad):
    with pytest.raises(ValidationError):
        Filters(location=bad)


def test_no_location_filter_is_allowed():
    cfg = Config(schema_version="1", site=SiteConfig(title="T"))
    assert cfg.client_config()["filters"]["location"] is None


def test_date_range_reaches_the_client_even_when_omitted():
    # The frontend reads filters.date_range unguarded, so an omitted block must still arrive.
    omitted = Config(schema_version="1", site=SiteConfig(title="T")).client_config()["filters"]["date_range"]
    assert isinstance(omitted, dict)
    configured = Config(schema_version="1", site=SiteConfig(title="T"),
                        filters=Filters(date_range={"default_weeks": "all", "year_start_week": 21}))
    assert configured.client_config()["filters"]["date_range"] == {"default_weeks": "all", "year_start_week": 21}


@pytest.mark.parametrize("bad", [
    {"default_weeks": 0},          # no weeks to show
    {"default_weeks": "forever"},  # only a count or "all"
    {"year_start_week": 0},
    {"year_start_week": 53},       # most years have no W53 to start on
    {"year_start": 21},            # misspelt key
])
def test_date_range_typos_fail_at_load(bad):
    with pytest.raises(ValidationError):
        Filters(date_range=bad)


def test_label_keys_follow_ids():
    # Spec §9: config carries stable ids; the label key always follows from the id.
    target = Target(id="SARS-CoV-2", pages=[Page(id="clinical")])
    assert (target.label_key, target.pages[0].label_key) == ("targets.SARS-CoV-2", "pages.clinical")
    panel = Panel(id="hospital_admissions", query={"feed": "clinical", "indicator": "deaths"})
    assert panel.label_key == "panels.hospital_admissions"
    assert _with_panel(_PANEL).client_config()["targets"][0]["label_key"] == "targets.Influenza"  # sent to the client


@pytest.mark.parametrize("build", [
    lambda: Target(id="SARS-CoV-2", label_key="targets.other"),
    lambda: Page(id="clinical", label_key="pages.other"),
    lambda: Panel(id="deaths", query={"feed": "clinical", "indicator": "deaths"}, label_key="panels.other"),
])
def test_label_keys_cannot_be_overridden(build):
    with pytest.raises(ValidationError):
        build()


def test_target_ids_are_pathogen_keys():
    with pytest.raises(ValidationError, match="pathogen registry"):
        Target(id="covid")


@pytest.mark.parametrize("page_id", ["Clinical", "clin ical", "a/b", ""])
def test_page_ids_must_be_url_safe(page_id):
    with pytest.raises(ValidationError):
        Page(id=page_id)


def test_page_paths_are_derived_from_ids():
    assert page_path("SARS-CoV-2", "clinical") == "/sars-cov-2/clinical"
    with pytest.raises(ValidationError):
        Page(id="clinical", path="/x/y")  # paths are not configurable


def test_no_pathogen_key_shadows_an_app_route():
    assert not {k.lower() for k in PATHOGENS} & {"login", "logout", "config", "api", "docs", "redoc", "openapi.json", "healthz", "assets"}


def test_a_panel_must_query_its_targets_pathogen():
    with pytest.raises(ValidationError, match="target 'Influenza'"):
        _with_panel({**_PANEL, "query": {"feed": "clinical", "indicator": "positivity", "dimensions": {"pathogen": "RSV"}}})


def test_methods_reach_the_client():
    methods = Config(schema_version="1", site=SiteConfig(title="T")).client_config()["methods"]
    assert methods["aedseo"] == {"levels": ["very_low", "low", "medium", "high", "very_high"],
                                 "phases": ["in_season", "in_wave", "out_of_season"], "trend": True,
                                 "stream_roles": ["cases", "admissions"], "active_phases": ["in_season", "in_wave"]}


def test_feeds_and_phases_take_optional_assessment_dirs():
    data = DataConfig(feeds=[{"id": "c", "profile": "erviss", "dir": "a", "assessments": "a/assessed"}], phases="p")
    assert (data.feeds[0].assessments, data.phases) == ("a/assessed", "p")
    assert DataConfig(feeds=[{"id": "c", "profile": "erviss", "dir": "a"}]).phases is None


def test_a_pmmov_panel_cannot_name_a_pathogen():
    with pytest.raises(ValidationError, match="carries no pathogen"):
        _with_panel({"id": "w", "query": {"feed": "wastewater", "indicator": "ppmv",
                                          "dimensions": {"aggregation": "me", "pathogen": "Influenza"}}})


def test_a_pmmov_panel_sits_under_any_target():
    _with_panel({"id": "w", "query": {"feed": "wastewater", "indicator": "ppmv", "dimensions": {"aggregation": "me"}}})


def test_a_panel_whose_indicator_implies_another_pathogen_fails():
    # cov is always SARS-CoV-2, so under the Influenza target it would show COVID data.
    with pytest.raises(ValidationError, match="target 'Influenza'"):
        _with_panel({"id": "w", "query": {"feed": "wastewater", "indicator": "cov", "dimensions": {"aggregation": "floMean"}}})


def test_overview_panels_take_no_query():
    _with_panel({"id": "phase", "type": "phase"})
    _with_panel({"id": "summary", "type": "summary"})


@pytest.mark.parametrize("bad", [
    {"id": "phase", "type": "phase", "query": {"feed": "clinical", "indicator": "deaths"}},
    {"id": "summary", "type": "summary", "series_by": "age"},
    {"id": "deaths", "type": "timeseries"},  # a time series needs its query
])
def test_panel_kinds_check_their_fields(bad):
    with pytest.raises(ValidationError):
        _with_panel(bad)


def test_client_panel_queries_drop_the_pathogen_their_indicator_implies():
    # The same canonical form as phase streams, so the two compare equal in the summary.
    cfg = Config(schema_version="1", site=SiteConfig(title="T"), data=_FEEDS,
                 targets=[Target(id="SARS-CoV-2", pages=[Page(id="w", panels=[Panel(**{"id": "cov", "query": {
                     "feed": "wastewater", "indicator": "cov", "dimensions": {"aggregation": "floMean", "pathogen": "SARS-CoV-2"}}})])])])
    query = cfg.client_config()["targets"][0]["pages"][0]["panels"][0]["query"]
    assert query["dimensions"] == {"aggregation": "floMean"}
