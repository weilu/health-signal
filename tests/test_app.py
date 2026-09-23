from fastapi.testclient import TestClient
from health_signal import create_app, load_config


def _client(tmp_path):
    f = tmp_path / "dashboard.yaml"
    f.write_text(
        "schema_version: '0.1'\n"
        "site:\n"
        "  title: { en: 'Test Dashboard' }\n"
        "  default_locale: en\n"
        "  locales: [en]\n",
        encoding="utf-8",
    )
    return TestClient(create_app(load_config(f)))


def test_healthz_ok(tmp_path):
    r = _client(tmp_path).get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["schema_version"] == "0.1"


def test_spa_placeholder_when_ui_absent(tmp_path):
    # No compiled _ui/ in a source checkout, so the catch-all serves the placeholder.
    r = _client(tmp_path).get("/")
    assert r.status_code == 200
    assert "health-signal" in r.text
