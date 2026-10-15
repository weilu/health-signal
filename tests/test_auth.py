import asyncio

import pytest
from pydantic import ValidationError
from fastapi import Response
from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest

from health_signal.app import create_app, render_index
from health_signal.auth import LocalAccountsProvider, from_env, hash_password
from health_signal.config import Config, SiteConfig, Target, Page

# Synthetic, throwaway test-only account -- never a real credential.
_EMAIL = "a@x.org"
_PASSWORD = "pw123"


def _provider() -> LocalAccountsProvider:
    return LocalAccountsProvider({_EMAIL: hash_password(_PASSWORD)}, "test-secret")


def _request(cookie_header: str | None) -> StarletteRequest:
    headers = [(b"cookie", cookie_header.encode())] if cookie_header else []
    scope = {"type": "http", "headers": headers, "method": "GET", "path": "/"}
    return StarletteRequest(scope)


def _client(public_paths: list[str] | None = None, targets: list[Target] | None = None) -> TestClient:
    config = Config(
        schema_version="0.1",
        site=SiteConfig(title="Test", public_paths=public_paths or []),
        targets=targets or [],
    )
    app = create_app(config, auth_provider=_provider())
    # Secure cookies are only ever replayed by an http client over https, so the
    # TestClient must use an https base_url for the login-then-access flow to work.
    return TestClient(app, base_url="https://testserver")


def _write_ui(tmp_path):
    ui_dir = tmp_path / "_ui"
    ui_dir.mkdir()
    (ui_dir / "index.html").write_text(
        "<html><head></head><body></body></html>", encoding="utf-8"
    )
    return ui_dir


def test_authenticate_valid_credentials():
    user = _provider().authenticate(_EMAIL, _PASSWORD)
    assert user is not None
    assert user.email == _EMAIL


def test_authenticate_wrong_password():
    assert _provider().authenticate(_EMAIL, "wrong-password") is None


def test_authenticate_unknown_email():
    assert _provider().authenticate("nobody@x.org", _PASSWORD) is None


def test_authenticate_malformed_hash_returns_none():
    provider = LocalAccountsProvider({_EMAIL: "not-a-valid-argon2-hash"}, "test-secret")
    assert provider.authenticate(_EMAIL, _PASSWORD) is None


def test_session_round_trip():
    provider = _provider()
    response = Response()
    provider._issue_session(response, provider.authenticate(_EMAIL, _PASSWORD))
    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie

    token = response.headers["set-cookie"].split(f"{provider.manager.cookie_name}=")[1].split(";")[0]
    user = asyncio.run(provider.current_user(_request(f"{provider.manager.cookie_name}={token}")))
    assert user is not None
    assert user.email == _EMAIL


def test_current_user_rejects_tampered_token():
    provider = _provider()
    tampered = _request(f"{provider.manager.cookie_name}=not-a-real-token")
    assert asyncio.run(provider.current_user(tampered)) is None


def test_current_user_rejects_absent_cookie():
    provider = _provider()
    assert asyncio.run(provider.current_user(_request(None))) is None


def test_healthz_public_without_auth():
    r = _client().get("/healthz")
    assert r.status_code == 200


def test_api_me_requires_auth():
    r = _client().get("/api/me")
    assert r.status_code == 401


def test_unknown_api_path_returns_404():
    # Unknown /api routes are an auth-independent 404 -- never SPA HTML, and no 401 that would let
    # anonymous probes distinguish real endpoints (the surface is public via /openapi.json anyway).
    client = _client()
    assert client.get("/api/does-not-exist").status_code == 404  # unauthenticated
    login = client.post(
        "/login", data={"email": _EMAIL, "password": _PASSWORD}, follow_redirects=False
    )
    assert login.status_code == 303
    assert client.get("/api/does-not-exist").status_code == 404  # authenticated


def test_spa_redirects_to_login_when_unauthenticated():
    r = _client().get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_login_wrong_password_returns_401():
    r = _client().post("/login", data={"email": _EMAIL, "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",  # different host
        "null",  # sandboxed iframe / opaque origin
        "http://testserver",  # same host, wrong scheme -- must not ride the Secure cookie to https
    ],
)
def test_login_rejects_cross_origin(origin):
    r = _client().post(
        "/login",
        data={"email": _EMAIL, "password": _PASSWORD},
        headers={"Origin": origin},
    )
    assert r.status_code == 403


def test_login_rejects_cross_origin_referer():
    # No Origin header -> the CSRF check falls back to Referer; a cross-origin Referer is rejected.
    r = _client().post(
        "/login",
        data={"email": _EMAIL, "password": _PASSWORD},
        headers={"Referer": "https://evil.example/page"},
    )
    assert r.status_code == 403


def test_login_accepts_same_origin_referer():
    # No Origin, same-origin Referer -> CSRF check passes, so a valid login proceeds (303), not 403.
    r = _client().post(
        "/login",
        data={"email": _EMAIL, "password": _PASSWORD},
        headers={"Referer": "https://testserver/some/page"},
        follow_redirects=False,
    )
    assert r.status_code == 303


def test_public_root_still_gates_api():
    # public_paths=["/"] makes pages public, but /api/* is still resolved first:
    # an unmatched API path is 404, never SPA HTML.
    r = _client(public_paths=["/"]).get("/api/unknown", follow_redirects=False)
    assert r.status_code == 404


def test_login_then_access_then_logout():
    client = _client()
    login = client.post(
        "/login", data={"email": _EMAIL, "password": _PASSWORD}, follow_redirects=False
    )
    assert login.status_code == 303
    set_cookie = login.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Secure" in set_cookie
    assert "samesite=lax" in set_cookie.lower()

    me = client.get("/api/me")
    assert me.status_code == 200
    assert me.json() == {"email": _EMAIL}

    client.post("/logout", follow_redirects=False)
    assert client.get("/api/me").status_code == 401


@pytest.mark.parametrize(
    "public_paths,path",
    [
        (["/about"], "/about"),  # exact match
        (["/about"], "/about/team"),  # subpath under the prefix
        (["/"], "/anything"),  # "/" opens the whole site
    ],
)
def test_public_paths_serve_pages(public_paths, path):
    r = _client(public_paths=public_paths).get(path, follow_redirects=False)
    assert r.status_code == 200


def test_docs_public_without_auth():
    # API docs are intentionally public -- the structure isn't sensitive; only /api/* data is gated.
    client = _client()
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200


@pytest.mark.parametrize("bad", ["", "//", "   ", "/ /"])
def test_match_all_public_path_footguns_rejected(bad):
    # These all normalize to "/" (match-all) but aren't a literal "/"; must not silently open the site.
    with pytest.raises(ValidationError):
        SiteConfig(title="Test", public_paths=[bad])


@pytest.mark.parametrize("path", ["/login/private", "/logout/x", "/healthz/secret"])
def test_operational_endpoint_subpaths_stay_gated(path):
    # Built-in routes are exact-match public; their subpaths must not inherit that.
    r = _client().get(path, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_public_paths_normalized_at_parse():
    site = SiteConfig(title="Test", public_paths=["about", "/data/", "/"])
    assert site.public_paths == ["/about", "/data", "/"]


def test_from_env_rejects_short_secret(monkeypatch):
    monkeypatch.setenv("HEALTH_SIGNAL_SECRET_KEY", "x")
    with pytest.raises(RuntimeError):
        from_env()


def test_from_env_rejects_non_string_account_values(monkeypatch):
    monkeypatch.setenv("HEALTH_SIGNAL_SECRET_KEY", "s" * 32)
    monkeypatch.setenv("HEALTH_SIGNAL_ACCOUNTS", '{"a@x.org": 123}')
    with pytest.raises(RuntimeError):
        from_env()


def test_render_index_injects_safe_json():
    out = render_index("<html><head></head><body></body></html>", {"t": "</script> < > &"})
    assert "window.__HS_CONFIG__" in out
    # Only the real tag-closer remains; the payload's </script> was escaped (would be 2 if it broke out).
    assert out.count("</script>") == 1
    # <, >, & in the payload are all escaped, not emitted literally inside the script.
    assert "\\u003c" in out and "\\u003e" in out and "\\u0026" in out


def test_spa_injects_bootstrap_only(tmp_path, monkeypatch):
    monkeypatch.setattr("health_signal.app._UI_DIR", _write_ui(tmp_path))  # writes index.html, returns dir
    body = _client(public_paths=["/"]).get("/").text
    assert "__HS_CONFIG__" in body and '"title"' in body
    assert "targets" not in body  # structure is NOT injected; it comes from /api/config


def test_login_path_serves_spa_under_locked_policy(tmp_path, monkeypatch):
    # GET /login must reach the SPA (it's always-public), even under the default locked policy —
    # guards against reintroducing a server-owned /login HTML route or breaking its public handling.
    monkeypatch.setattr("health_signal.app._UI_DIR", _write_ui(tmp_path))
    r = _client().get("/login", follow_redirects=False)  # default: everything locked
    assert r.status_code == 200
    assert "__HS_CONFIG__" in r.text  # the SPA (bootstrap-injected), not a redirect or server form


def test_spa_falls_back_to_placeholder_when_ui_missing(tmp_path, monkeypatch):
    # Point _UI_DIR at an empty dir so the missing-index path is exercised deterministically,
    # regardless of whether the frontend happens to be built in this environment.
    monkeypatch.setattr("health_signal.app._UI_DIR", tmp_path)
    r = _client(public_paths=["/"]).get("/")
    assert r.status_code == 200
    assert "not found" in r.text.lower()  # the placeholder, not a real SPA build


def test_api_config_requires_auth():
    assert _client().get("/api/config").status_code == 401


def test_api_config_returns_view_model_when_authed():
    client = _client(targets=[Target(id="covid-19", pages=[Page(id="ov", path="/covid-19/ov")])])
    client.post("/login", data={"email": _EMAIL, "password": _PASSWORD}, follow_redirects=False)
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert body["targets"][0]["id"] == "covid-19"
    assert "public_paths" not in body  # server-only never exposed
    assert "schema_version" not in body  # server-only never exposed
