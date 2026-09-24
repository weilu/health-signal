from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import Config

_UI_DIR = Path(__file__).resolve().parent / "_ui"
_PLACEHOLDER = (
    "<!doctype html><meta charset='utf-8'>"
    "<title>health-signal</title>"
    "<h1>health-signal</h1>"
    "<p>The compiled frontend (<code>_ui/index.html</code>) was not found. "
    "Build the frontend, or install a release wheel that bundles it.</p>"
)


def create_app(config: Config) -> FastAPI:
    app = FastAPI(title=config.site.title)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "schema_version": config.schema_version}

    if (_UI_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_UI_DIR / "assets"), name="assets")

    # Registered last so more specific routes (e.g. /api/*, /docs) take precedence. Serves the
    # compiled SPA when built, else a placeholder.
    @app.get("/{path:path}", response_class=HTMLResponse)
    def spa(path: str) -> HTMLResponse:
        index = _UI_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)  # type: ignore[return-value]
        return HTMLResponse(_PLACEHOLDER)

    return app
