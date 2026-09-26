import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
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


def render_index(html: str, config_payload: dict) -> str:
    # Embed config as HTML-safe JSON so a config value can't break out of the <script>.
    blob = json.dumps(config_payload).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    tag = f"<script>window.__HS_CONFIG__ = {blob};</script>"
    return html.replace("</head>", tag + "</head>", 1) if "</head>" in html else tag + html


def _serve_spa(config: Config) -> Response:
    index = _UI_DIR / "index.html"
    if not index.is_file():
        return HTMLResponse(_PLACEHOLDER)
    # Only the bootstrap slice is injected (safe for anon). The full view-model is gated behind /api/config.
    return HTMLResponse(render_index(index.read_text(encoding="utf-8"), config.bootstrap_config()))


def create_app(config: Config, auth_provider: AuthProvider | None = None) -> FastAPI:
    app = FastAPI(title=config.site.title)
    provider = auth_provider if auth_provider is not None else _auth.from_env()
    provider.install(app)

    _ALWAYS_PUBLIC = ("/healthz", "/login", "/logout")

    def is_public(path: str) -> bool:
        # Operational endpoints are always public, but only as exact matches -- a subpath such as
        # /login/private must stay gated. Configured public_paths (already validated + normalized by
        # SiteConfig) match by prefix: "/" opts the whole site public; others match at a path boundary.
        if path in _ALWAYS_PUBLIC:
            return True
        return any(
            prefix == "/" or path == prefix or path.startswith(prefix + "/")
            for prefix in config.site.public_paths
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

    @app.get("/api/config")
    def get_config(user: User = Depends(require_auth)) -> dict:
        return config.client_config()

    if (_UI_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_UI_DIR / "assets"), name="assets")

    # Registered last so more specific routes (/api/*, /login, ...) take precedence. Unmatched
    # /api/* is resolved before any page policy, so a public_paths of "/" or "/api" can't turn it
    # into SPA HTML. Then public paths get the SPA; authenticated non-API paths get the SPA; else
    # redirect to /login.
    @app.get("/{path:path}")
    async def spa(path: str, request: Request) -> Response:
        full_path = "/" + path
        is_api = full_path == "/api" or full_path.startswith("/api/")
        if is_api:
            raise HTTPException(status_code=404, detail="Not found")

        if is_public(full_path):
            return _serve_spa(config)
        if await provider.current_user(request) is not None:
            return _serve_spa(config)
        return RedirectResponse(url="/login", status_code=303)

    return app
