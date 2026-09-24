from fastapi.testclient import TestClient
from health_signal import create_app, load_config
from health_signal.auth import LocalAccountsProvider


def _client(tmp_path):
    f = tmp_path / "dashboard.yaml"
    f.write_text(
        "schema_version: '0.1'\n"
        "site:\n"
        "  title: 'Test Dashboard'\n"
        "  default_locale: en\n"
        "  locales: [en]\n",
        encoding="utf-8",
    )
    config = load_config(f)
    # Stage-1 tests don't exercise login; an empty accounts map is enough to
    # build a DB-free provider without touching HEALTH_SIGNAL_SECRET_KEY.
    provider = LocalAccountsProvider(accounts={}, secret_key="test-secret")
    app = create_app(config, auth_provider=provider)
    # Secure cookies are only replayed by an http client over https.
    return TestClient(app, base_url="https://testserver")


def test_healthz_ok(tmp_path):
    r = _client(tmp_path).get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["schema_version"] == "0.1"


def test_root_redirects_to_login_when_unauthenticated(tmp_path):
    # Default access policy is all-locked (no public_paths), so an
    # unauthenticated request to any page now redirects to /login.
    r = _client(tmp_path).get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"
