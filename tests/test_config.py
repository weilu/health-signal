import pytest
from pydantic import ValidationError
from health_signal.config import Branding, Config, Page, SiteConfig, Target, load_config


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


def test_page_requires_path():
    with pytest.raises(ValidationError):
        Page(id="overview")  # no path
