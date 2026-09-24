import json
import os
from datetime import timedelta
from typing import Protocol
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi_login import LoginManager
from pydantic import BaseModel

_ph = PasswordHasher()
# Always verified against on an unknown email so authenticate() takes the same
# time whether the email exists or not (no timing-based account enumeration).
_DUMMY_HASH = _ph.hash("hs-auth-dummy-password-do-not-use")

_LOGIN_FORM_HTML = (
    "<!doctype html><meta charset='utf-8'><title>Sign in</title>"
    "<form method='post' action='/login'>"
    "<label>Email <input name='email' type='email' required></label>"
    "<label>Password <input name='password' type='password' required></label>"
    "<button type='submit'>Sign in</button>"
    "</form>"
)


class User(BaseModel):
    email: str


class AuthProvider(Protocol):
    def install(self, app: FastAPI) -> None: ...

    async def current_user(self, request: Request) -> User | None: ...


def hash_password(password: str) -> str:
    return _ph.hash(password)


def _reject_cross_origin(request: Request) -> None:
    # Cookie-based sessions still need login-CSRF defense: a cross-site POST
    # riding the browser's ambient cookie must not be able to drive /login or
    # /logout. Requests with neither header (curl, some same-origin fetches)
    # are let through -- the attack is specifically the cross-site browser POST.
    source = request.headers.get("origin") or request.headers.get("referer")
    if source is None:
        return  # no Origin/Referer (non-browser client) — allowed
    # A present Origin/Referer MUST match our host. "null" (sandboxed iframe) parses to netloc ""
    # which != host, so it is rejected — closing the Origin: null CSRF bypass.
    if urlsplit(source).netloc != request.headers.get("host"):
        raise HTTPException(status_code=403, detail="Cross-origin request rejected")


class LocalAccountsProvider:
    """DB-free AuthProvider: accounts are an in-memory email -> argon2-hash map.

    Session token/cookie handling is delegated to fastapi-login's LoginManager
    (JWT signing + cookie read/write); we only supply argon2 password checks
    and the account lookup.
    """

    def __init__(self, accounts: dict[str, str], secret_key: str, max_age_s: int = 43200):
        self.accounts = accounts
        self.max_age_s = max_age_s
        self.manager = LoginManager(
            secret_key,
            token_url="/login",
            use_cookie=True,
            use_header=False,
            cookie_name="hs_session",
            default_expiry=timedelta(seconds=max_age_s),
        )

        @self.manager.user_loader()
        def _load_user(email: str) -> User | None:
            return User(email=email) if email in self.accounts else None

    def authenticate(self, email: str, password: str) -> User | None:
        stored_hash = self.accounts.get(email)
        try:
            _ph.verify(stored_hash if stored_hash is not None else _DUMMY_HASH, password)
        except (VerifyMismatchError, InvalidHashError):
            return None
        return User(email=email) if stored_hash is not None else None

    async def current_user(self, request: Request) -> User | None:
        # manager.optional() swallows missing/invalid/expired-token errors and
        # returns None instead of raising, which is what a gate dependency needs.
        return await self.manager.optional(request)

    def _issue_session(self, response: Response, user: User) -> None:
        token = self.manager.create_access_token(data={"sub": user.email})
        # manager.set_cookie() only sets HttpOnly; Secure + SameSite are required
        # by the security constraints and must be set explicitly on this version.
        response.set_cookie(
            key=self.manager.cookie_name,
            value=token,
            max_age=self.max_age_s,
            httponly=True,
            secure=True,
            samesite="lax",
        )

    def install(self, app: FastAPI) -> None:
        @app.get("/login", response_class=HTMLResponse)
        def login_form() -> HTMLResponse:
            return HTMLResponse(_LOGIN_FORM_HTML)

        @app.post("/login", dependencies=[Depends(_reject_cross_origin)])
        def login(email: str = Form(...), password: str = Form(...)) -> Response:
            user = self.authenticate(email, password)
            if user is None:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            response = RedirectResponse(url="/", status_code=303)
            self._issue_session(response, user)
            return response

        @app.post("/logout", dependencies=[Depends(_reject_cross_origin)])
        def logout() -> Response:
            response = RedirectResponse(url="/login", status_code=303)
            response.delete_cookie(key=self.manager.cookie_name)
            return response


def from_env(max_age_s: int = 43200) -> LocalAccountsProvider:
    secret_key = os.environ.get("HEALTH_SIGNAL_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("HEALTH_SIGNAL_SECRET_KEY is required to build an auth provider")
    raw = json.loads(os.environ.get("HEALTH_SIGNAL_ACCOUNTS", "{}"))
    if not isinstance(raw, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in raw.items()):
        raise RuntimeError("HEALTH_SIGNAL_ACCOUNTS must be a JSON object mapping email strings to hash strings.")
    return LocalAccountsProvider(raw, secret_key, max_age_s=max_age_s)
