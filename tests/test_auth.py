import asyncio

from fastapi import Response
from starlette.requests import Request as StarletteRequest

from health_signal.auth import LocalAccountsProvider, hash_password

# Synthetic, throwaway test-only account -- never a real credential.
_EMAIL = "a@x.org"
_PASSWORD = "pw123"


def _provider() -> LocalAccountsProvider:
    return LocalAccountsProvider({_EMAIL: hash_password(_PASSWORD)}, "test-secret")


def _request(cookie_header: str | None) -> StarletteRequest:
    headers = [(b"cookie", cookie_header.encode())] if cookie_header else []
    scope = {"type": "http", "headers": headers, "method": "GET", "path": "/"}
    return StarletteRequest(scope)


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
