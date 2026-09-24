from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from . import auth as _auth
from .auth import AuthProvider, User
from .config import Config

_UI_DIR = Path(__file__).resolve().parent / "_ui"
_PLACEHOLDER = (
    "<!doctype html><meta charset='utf-8'>"
    "<title>health-signal</title>"
    "<h1>health-signal</h1>"
    "<p>The compiled frontend (<code>_ui/index.html</code>) was not found. "
    "Build the frontend, or install a release wheel that bundles it.</p>"
)


def _serve_spa() -> Response:
    index = _UI_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return HTMLResponse(_PLACEHOLDER)


def create_app(config: Config, auth_provider: AuthProvider | None = None) -> FastAPI:
    app = FastAPI(title=config.site.title)
    provider = auth_provider if auth_provider is not None else _auth.from_env()
    provider.install(app)

    public_prefixes = [p.rstrip("/") or "/" for p in config.site.public_paths]

    def is_public(path: str) -> bool:
        if path in ("/login", "/logout", "/healthz"):
            return True
        return any(
            path == prefix or path.startswith(prefix + "/") for prefix in public_prefixes
        )

    async def require_auth(request: Request) -> User:
        user = await provider.current_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "schema_version": config.schema_version}

    @app.get("/api/me")
    def get_me(user: User = Depends(require_auth)) -> dict:
        return {"email": user.email}

    if (_UI_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_UI_DIR / "assets"), name="assets")

    # Registered last so more specific routes (e.g. /api/*, /login, /docs) take
    # precedence. Applies the per-page access policy: public paths get the
    # SPA/placeholder unconditionally; otherwise an authenticated user gets the
    # SPA for non-API paths but a 404 (JSON contract) for an unmatched /api/*
    # path -- it fell through to this catch-all only because no real API route
    # matched, so it must not silently serve HTML. An unauthenticated user gets
    # a 401 for /api/* (JSON contract for API clients) or a redirect to /login.
    @app.get("/{path:path}")
    async def spa(path: str, request: Request) -> Response:
        full_path = "/" + path
        is_api = full_path == "/api" or full_path.startswith("/api/")
        if is_public(full_path):
            return _serve_spa()
        if await provider.current_user(request) is not None:
            if is_api:
                raise HTTPException(status_code=404, detail="Not found")
            return _serve_spa()
        if is_api:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return RedirectResponse(url="/login", status_code=303)

    return app
