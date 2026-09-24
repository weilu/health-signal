import asyncio

from fastapi import Response
from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest

from health_signal.app import create_app
from health_signal.auth import LocalAccountsProvider, hash_password
from health_signal.config import Config, SiteConfig

# Synthetic, throwaway test-only account -- never a real credential.
_EMAIL = "a@x.org"
_PASSWORD = "pw123"


def _provider() -> LocalAccountsProvider:
    return LocalAccountsProvider({_EMAIL: hash_password(_PASSWORD)}, "test-secret")


def _request(cookie_header: str | None) -> StarletteRequest:
    headers = [(b"cookie", cookie_header.encode())] if cookie_header else []
    scope = {"type": "http", "headers": headers, "method": "GET", "path": "/"}
    return StarletteRequest(scope)


def _client(public_paths: list[str] | None = None) -> TestClient:
    config = Config(
        schema_version="0.1",
        site=SiteConfig(title="Test", public_paths=public_paths or []),
    )
    app = create_app(config, auth_provider=_provider())
    # Secure cookies are only ever replayed by an http client over https, so the
    # TestClient must use an https base_url for the login-then-access flow to work.
    return TestClient(app, base_url="https://testserver")


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


def test_unknown_api_path_returns_401_unauthenticated():
    r = _client().get("/api/does-not-exist")
    assert r.status_code == 401


def test_spa_redirects_to_login_when_unauthenticated():
    r = _client().get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login"


def test_public_path_bypasses_auth():
    r = _client(public_paths=["/about"]).get("/about", follow_redirects=False)
    assert r.status_code == 200


def test_login_wrong_password_returns_401():
    r = _client().post("/login", data={"email": _EMAIL, "password": "wrong"})
    assert r.status_code == 401


def test_login_rejects_cross_origin():
    r = _client().post(
        "/login",
        data={"email": _EMAIL, "password": _PASSWORD},
        headers={"origin": "https://evil.example"},
    )
    assert r.status_code == 403


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
