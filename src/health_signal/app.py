from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import Config

_UI_DIR = Path(__file__).resolve().parent / "_ui"
_PLACEHOLDER = (
    "<!doctype html><meta charset='utf-8'>"
    "<title>health-signal</title>"
    "<h1>health-signal</h1><p>UI not built in this deployment yet.</p>"
)


def create_app(config: Config) -> FastAPI:
    title = config.site.title.get(config.site.default_locale, "health-signal")
    app = FastAPI(title=title)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok", "schema_version": config.schema_version}

    has_ui = (_UI_DIR / "index.html").is_file()
    if has_ui and (_UI_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_UI_DIR / "assets"), name="assets")

    # Catch-all is registered LAST so future /api/* and /docs routes take precedence
    # (see spec §8). Serves the compiled SPA when present, else a placeholder.
    @app.get("/{path:path}", response_class=HTMLResponse)
    def spa(path: str) -> HTMLResponse:
        index = _UI_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)  # type: ignore[return-value]
        return HTMLResponse(_PLACEHOLDER)

    return app
