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
    # Built-in OpenAPI docs are unauthenticated by default; disable them here. The API-docs stage
    # will re-enable them behind auth.
    app = FastAPI(title=config.site.title, docs_url=None, redoc_url=None, openapi_url=None)
    provider = auth_provider if auth_provider is not None else _auth.from_env()
    provider.install(app)

    _ALWAYS_PUBLIC = ("/healthz", "/login", "/logout")
    # Normalize each configured public path to a leading-slash, no-trailing-slash prefix ("" -> "/").
    public_prefixes = list(_ALWAYS_PUBLIC) + ["/" + p.strip("/") for p in config.site.public_paths]

    def is_public(path: str) -> bool:
        # "/" opts the whole site public; otherwise match at a path boundary.
        return any(
            prefix == "/" or path == prefix or path.startswith(prefix + "/")
            for prefix in public_prefixes
        )

    # docs_url/redoc_url/openapi_url=None above only stops FastAPI from registering these routes;
    # the SPA catch-all below would otherwise still swallow them (redirect/200), not 404 them.
    _DISABLED_DOCS_PATHS = ("/openapi.json", "/docs", "/redoc")

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

    # Registered last so more specific routes (/api/*, /login, ...) take precedence. The API
    # contract (401 unauth / 404 authed) applies to /api/* before any page policy, so a public_paths
    # of "/" or "/api" can't turn an unmatched /api/* into SPA HTML. Then public paths get the SPA;
    # authenticated non-API paths get the SPA; else redirect to /login.
    @app.get("/{path:path}")
    async def spa(path: str, request: Request) -> Response:
        full_path = "/" + path
        if full_path in _DISABLED_DOCS_PATHS:
            raise HTTPException(status_code=404, detail="Not found")
        is_api = full_path == "/api" or full_path.startswith("/api/")
        if is_api:
            user = await provider.current_user(request)
            if user is None:
                raise HTTPException(status_code=401, detail="Not authenticated")
            raise HTTPException(status_code=404, detail="Not found")
        if is_public(full_path):
            return _serve_spa()
        if await provider.current_user(request) is not None:
            return _serve_spa()
        return RedirectResponse(url="/login", status_code=303)

    # Non-GET requests bypass the GET-only catch-all above and would otherwise hit FastAPI's
    # default 405 before any auth check runs; the API contract precedes page policy here too.
    @app.api_route("/{path:path}", methods=["POST", "PUT", "PATCH", "DELETE"])
    async def gated_fallback(path: str, request: Request) -> Response:
        full_path = "/" + path
        if full_path in _DISABLED_DOCS_PATHS:
            raise HTTPException(status_code=404, detail="Not found")
        is_api = full_path == "/api" or full_path.startswith("/api/")
        if is_api:
            user = await provider.current_user(request)
            if user is None:
                raise HTTPException(status_code=401, detail="Not authenticated")
            raise HTTPException(status_code=404, detail="Not found")
        if is_public(full_path):
            raise HTTPException(status_code=405, detail="Method not allowed")
        if await provider.current_user(request) is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        raise HTTPException(status_code=404, detail="Not found")

    return app
