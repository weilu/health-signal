import pytest
from pydantic import ValidationError
from health_signal.config import Branding, Config, Filters, Page, Panel, SiteConfig, Target, load_config


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
    # default_locale defaults alone are consistent ("en" in ["en"]); a default_locale outside the
    # configured locales is rejected so the client's fallbackLng always has a registered catalog.
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


_PANEL = {"id": "p", "type": "timeseries", "query": {"indicator": "positivity", "dimensions": {"pathogen": "Influenza"}}, "series_by": "survtype"}


def test_panel_parses_and_reaches_client_config():
    cfg = Config(schema_version="1", site=SiteConfig(title="T"),
                 targets=[Target(id="flu", pages=[Page(id="o", path="/flu", panels=[Panel(**_PANEL)])])])
    panel = cfg.client_config()["targets"][0]["pages"][0]["panels"][0]
    assert panel["query"] == {"indicator": "positivity", "dimensions": {"pathogen": "Influenza"}}
    assert panel["series_by"] == "survtype"


@pytest.mark.parametrize("bad", [
    {"type": "bar"},                                                 # only timeseries exists
    {"query": {"indicator": "bogus"}},                               # not an ERVISS indicator
    {"query": {"indicator": "positivity", "dimensions": {"pathogen": "Measles"}}},  # not in the ERVISS vocab
    {"query": {"indicator": "positivity", "dimensions": {"agee": "65+"}}},         # not an ERVISS dimension
    {"query": {"indicator": "positivity", "pathogen": "Influenza"}},               # dimensions belong under `dimensions`
    {"series_by": "colour"},                                         # not an ERVISS dimension
])
def test_panel_config_typos_fail_at_load(bad):
    with pytest.raises(ValidationError):
        Panel(**{**_PANEL, **bad})


def test_example_config_loads():
    cfg = load_config("examples/greece.dashboard.yaml")
    assert all(p.panels for t in cfg.targets for p in t.pages)


@pytest.mark.parametrize("bad", [
    {"query": {"indicator": "positivity", "dimensiosn": {"age": "65+"}}},  # misspelt key
    {"seriesby": "survtype"},                               # misspelt panel key
])
def test_panel_unknown_keys_fail_at_load(bad):
    with pytest.raises(ValidationError):
        Panel(**{**_PANEL, **bad})


def test_page_unknown_key_fails_at_load():
    with pytest.raises(ValidationError):
        Page(id="o", path="/flu", panel=[_PANEL])  # misspelt `panels`


@pytest.mark.parametrize("path", ["/", "/login", "/config", "/api/x", "/docs", "/assets/a", "flu", "/flu/:id", "/flu/*"])
def test_page_path_must_not_collide_or_be_a_pattern(path):
    with pytest.raises(ValidationError):
        Page(id="o", path=path)


def _cfg_pages(*pages):
    return dict(schema_version="1", site=SiteConfig(title="T"),
                targets=[Target(id=f"t{i}", pages=[p]) for i, p in enumerate(pages)])


def test_duplicate_page_paths_and_ids_fail_at_load():
    with pytest.raises(ValidationError, match="path"):
        Config(**_cfg_pages(Page(id="a", path="/flu"), Page(id="b", path="/flu")))
    with pytest.raises(ValidationError, match="page id"):
        Config(**_cfg_pages(Page(id="a", path="/flu"), Page(id="a", path="/rsv")))


def test_duplicate_panel_ids_on_a_page_fail_at_load():
    with pytest.raises(ValidationError):
        Page(id="o", path="/flu", panels=[Panel(**_PANEL), Panel(**_PANEL)])


@pytest.mark.parametrize("key", ["location", "week_from", "week_to"])
def test_panel_query_leaves_location_and_dates_to_dashboard_filters(key):
    with pytest.raises(ValidationError):
        Panel(**{**_PANEL, "query": {"indicator": "positivity", key: "x"}})
    with pytest.raises(ValidationError):  # nor can they hide among the dimensions
        Panel(**{**_PANEL, "query": {"indicator": "positivity", "dimensions": {key: "x"}}})


_LOC = {"location": {"default": "Greece", "options": [{"value": "Greece", "label_key": "locations.national"}, {"value": "Attica"}]}}


def test_location_filter_reaches_client_config():
    cfg = Config(schema_version="1", site=SiteConfig(title="T"), filters=Filters(**_LOC))
    loc = cfg.client_config()["filters"]["location"]
    assert loc["default"] == "Greece" and [o["value"] for o in loc["options"]] == ["Greece", "Attica"]


@pytest.mark.parametrize("bad", [
    {"default": "Crete", "options": [{"value": "Greece"}]},                  # default not offered
    {"default": "Greece", "options": [{"value": "Greece"}, {"value": "Greece"}]},  # duplicate option
    {"default": "Greece", "options": []},                                    # nothing to choose
])
def test_location_filter_typos_fail_at_load(bad):
    with pytest.raises(ValidationError):
        Filters(location=bad)


def test_no_location_filter_is_allowed():
    cfg = Config(schema_version="1", site=SiteConfig(title="T"))
    assert cfg.client_config()["filters"] == {"location": None}
