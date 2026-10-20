import pytest
from pydantic import ValidationError
from health_signal.config import Branding, Config, DataConfig, Filters, Page, Panel, SiteConfig, Target, load_config


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
        targets=[Target(id="covid-19", pages=[Page(id="overview", path="/covid-19/overview")])],
    )
    c = cfg.client_config()
    assert c["title"] == "Demo"
    assert c["targets"][0]["id"] == "covid-19"
    assert c["targets"][0]["pages"][0]["path"] == "/covid-19/overview"
    assert "public_paths" not in c and "schema_version" not in c


def test_empty_targets_projects_cleanly():
    c = _cfg().client_config()
    assert c["targets"] == []


def test_default_locale_must_be_in_locales():
    # default_locale must be a configured locale (fallbackLng needs a catalog).
    with pytest.raises(ValidationError):
        SiteConfig(title="D", default_locale="el")  # locales defaults to ["en"]
    SiteConfig(title="D", default_locale="el", locales=["en", "el"])  # offered -> ok


def test_page_requires_path():
    with pytest.raises(ValidationError):
        Page(id="overview")  # no path


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


_PANEL = {"id": "p", "type": "timeseries", "series_by": "survtype",
          "query": {"feed": "clinical", "indicator": "positivity", "dimensions": {"pathogen": "Influenza"}}}
_FEEDS = DataConfig(feeds=[{"id": "clinical", "profile": "erviss", "dir": "d/c"},
                           {"id": "wastewater", "profile": "phes_odm", "dir": "d/w"}])


def _with_panel(panel, data=_FEEDS):
    return Config(schema_version="1", site=SiteConfig(title="T"), data=data,
                  targets=[Target(id="flu", pages=[Page(id="o", path="/flu", panels=[Panel(**panel)])])])


def test_panel_parses_and_reaches_client_config():
    panel = _with_panel(_PANEL).client_config()["targets"][0]["pages"][0]["panels"][0]
    assert panel["query"] == {"feed": "clinical", "indicator": "positivity", "dimensions": {"pathogen": "Influenza"}}
    assert panel["series_by"] == "survtype"


def test_a_wastewater_panel_validates_against_its_feed():
    ww = {"id": "w", "type": "timeseries",
          "query": {"feed": "wastewater", "indicator": "fluA", "dimensions": {"aggregation": "floMean"}}}
    _with_panel(ww)


@pytest.mark.parametrize("bad", [
    {"query": {"feed": "clinical", "indicator": "bogus"}},                                       # not an ERVISS indicator
    {"query": {"feed": "clinical", "indicator": "positivity", "dimensions": {"pathogen": "Measles"}}},
    {"query": {"feed": "clinical", "indicator": "positivity", "dimensions": {"agee": "65+"}}},  # not an ERVISS dimension
    {"series_by": "colour"},                                                                     # not an ERVISS dimension
    {"query": {"feed": "sewage", "indicator": "positivity"}},                                    # no such feed
    {"query": {"feed": "wastewater", "indicator": "fluA", "dimensions": {"survtype": "non-sentinel"}}},  # ERVISS dim on the ODM feed
    {"query": {"feed": "wastewater", "indicator": "positivity"}},                                # ERVISS indicator on the ODM feed
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
    {"dir": "a"},                                                                                             # the old single-feed form
])
def test_data_config_errors_fail_at_load(bad):
    with pytest.raises(ValidationError):
        DataConfig(**bad)


def test_example_config_loads():
    cfg = load_config("examples/greece.dashboard.yaml")
    assert all(p.panels for t in cfg.targets for p in t.pages)


@pytest.mark.parametrize("bad", [
    {"query": {"feed": "clinical", "indicator": "positivity", "dimensiosn": {"age": "65+"}}},  # misspelt key
    {"seriesby": "survtype"},                               # misspelt panel key
])
def test_panel_unknown_keys_fail_at_load(bad):
    with pytest.raises(ValidationError):
        Panel(**{**_PANEL, **bad})


def test_page_unknown_key_fails_at_load():
    with pytest.raises(ValidationError):
        Page(id="o", path="/flu", panel=[_PANEL])  # misspelt `panels`


@pytest.mark.parametrize("path", ["/", "/login", "/config", "/CONFIG", "/api/x", "/docs", "/assets/a", "flu", "/flu/", "/flu/:id", "/flu/*", "/flu?x", "/flu#x",
                                  "/flu/../config", "/flu/%2e%2e/config", "//other.example/flu", "/flu\\x", "/flu.x"])
def test_page_path_must_not_collide_or_be_a_pattern(path):
    with pytest.raises(ValidationError):
        Page(id="o", path=path)


def _cfg_pages(*pages):
    return dict(schema_version="1", site=SiteConfig(title="T"),
                targets=[Target(id=f"t{i}", pages=[p]) for i, p in enumerate(pages)])


def test_duplicate_page_paths_and_ids_fail_at_load():
    with pytest.raises(ValidationError, match="path"):
        Config(**_cfg_pages(Page(id="a", path="/flu"), Page(id="b", path="/flu")))
    with pytest.raises(ValidationError, match="path"):
        Config(**_cfg_pages(Page(id="a", path="/flu"), Page(id="b", path="/FLU")))
    with pytest.raises(ValidationError, match="page id"):
        Config(**_cfg_pages(Page(id="a", path="/flu"), Page(id="a", path="/rsv")))


def test_duplicate_target_ids_fail_at_load():
    with pytest.raises(ValidationError, match="target ids"):
        Config(schema_version="1", site=SiteConfig(title="T"),
               targets=[Target(id="flu", pages=[Page(id="a", path="/a")]), Target(id="flu", pages=[Page(id="b", path="/b")])])


def test_duplicate_panel_ids_on_a_page_fail_at_load():
    with pytest.raises(ValidationError):
        Page(id="o", path="/flu", panels=[Panel(**_PANEL), Panel(**_PANEL)])


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
