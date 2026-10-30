import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from health_signal import create_app, load_config
from health_signal.config import Config
from auth_stubs import AllowAll, DenyAll


def _config(tmp_path, overlays=None, locales=("en", "el")):
    site = {"title": "T", "default_locale": "en", "locales": list(locales)}
    if overlays is not None:
        directory = tmp_path / "locales"
        directory.mkdir()
        for lang, text in overlays.items():
            (directory / f"{lang}.json").write_text(text if isinstance(text, str) else json.dumps(text),
                                                    encoding="utf-8")
        site["locales_dir"] = str(directory)
    return Config.model_validate({"schema_version": "1", "site": site,
                                  "targets": [{"id": "Influenza", "pages": [{"id": "clinical"}]}]})


def _client(config, auth=None):
    return TestClient(create_app(config, auth_provider=auth or AllowAll()))


def test_a_deployment_serves_its_own_text_per_language(tmp_path):
    cfg = _config(tmp_path, {"en": {"targets": {"Influenza": "Influenza"}},
                             "el": {"targets": {"Influenza": "Γρίπη"}}})
    assert _client(cfg).get("/api/locales/el").json() == {"targets": {"Influenza": "Γρίπη"}}


def test_deployment_text_is_behind_login_like_the_config_it_labels(tmp_path):
    cfg = _config(tmp_path, {"en": {}, "el": {}})
    assert _client(cfg, DenyAll()).get("/api/locales/en").status_code == 401


def test_a_language_the_deployment_does_not_offer_is_not_found(tmp_path):
    cfg = _config(tmp_path, {"en": {}, "el": {}})
    assert _client(cfg).get("/api/locales/fr").status_code == 404


def test_without_a_locales_dir_a_deployment_adds_no_text(tmp_path):
    assert _client(_config(tmp_path)).get("/api/locales/en").json() == {}


def test_an_offered_language_without_its_file_fails_at_startup(tmp_path):
    # Otherwise every label in that language would quietly show its raw id.
    with pytest.raises(ValueError, match="el.json"):
        create_app(_config(tmp_path, {"en": {}}), auth_provider=AllowAll())


@pytest.mark.parametrize("text, message", [("{not json", "el.json"),
                                           (json.dumps({"panels": {"deaths": 3}}), "panels.deaths"),
                                           (json.dumps(["deaths"]), "el.json")])
def test_a_malformed_locale_file_fails_at_startup_naming_the_problem(tmp_path, text, message):
    with pytest.raises(ValueError, match=message):
        create_app(_config(tmp_path, {"en": {}, "el": text}), auth_provider=AllowAll())


def test_the_title_in_each_language_reaches_the_sign_in_page_and_nothing_else_does(tmp_path, monkeypatch):
    # The sign-in page is shown before the gated text loads, so the title travels in the pre-login bootstrap; the
    # rest of the deployment's text (panel names: structure) stays behind login.
    ui = tmp_path / "_ui"
    ui.mkdir()
    (ui / "index.html").write_text("<html><head></head><body></body></html>", encoding="utf-8")
    monkeypatch.setattr("health_signal.app._UI_DIR", ui)
    cfg = _config(tmp_path, {"en": {"site": {"title": "Surveillance"}, "panels": {"deaths": "Deaths"}},
                             "el": {"site": {"title": "Επιτήρηση"}, "panels": {"deaths": "Θάνατοι"}}})
    cfg.site.public_paths = ["/"]
    body = _client(cfg, DenyAll()).get("/").text
    bootstrap = json.loads(re.search(r"window.__HS_CONFIG__ = (.*?);</script>", body).group(1))
    assert bootstrap["titles"] == {"en": "Surveillance", "el": "Επιτήρηση"}
    assert "Deaths" not in body and "Θάνατοι" not in body and "\\u0398" not in body


def test_the_locales_dir_is_not_sent_to_the_browser(tmp_path):
    cfg = _config(tmp_path, {"en": {}, "el": {}})
    assert "locales_dir" not in json.dumps(cfg.client_config())


def test_the_greece_example_labels_everything_it_shows_in_every_language():
    # A panel added to the example without its label would show its raw id; a unit or dimension value its profile
    # extension adds would show its code.
    cfg = load_config("examples/greece.dashboard.yaml")
    keys = {"site.title"} | {t.label_key for t in cfg.targets} | {o.label_key for o in cfg.filters.location.options}
    keys |= {p.label_key for t in cfg.targets for p in t.pages}
    keys |= {x.label_key for t in cfg.targets for p in t.pages for x in p.panels}
    keys |= {f"unit.{u}" for ext in cfg.profiles.values() for u in ext.units}
    keys |= {f"dimensions.{d}.{v}" for ext in cfg.profiles.values() for d, values in ext.dimension_vocab.items()
             for v in values}
    for lang in cfg.site.locales:
        catalog = json.loads((Path("examples") / cfg.site.locales_dir / f"{lang}.json").read_text(encoding="utf-8"))
        missing = sorted(k for k in keys if not _has(catalog, k))
        assert not missing, f"{lang}: {missing}"


def _has(catalog, key):
    for part in key.split("."):
        if not isinstance(catalog, dict) or part not in catalog:
            return False
        catalog = catalog[part]
    return isinstance(catalog, str)
