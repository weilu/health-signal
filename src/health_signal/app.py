import html
import json
import re
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from . import auth as _auth
from .assessments import (AssessmentRow, AssessmentSource, PhaseRow, PhaseSource, PhaseStreamRow,
                          PhaseStreamSource, ThresholdRow)
from .auth import AuthProvider, User
from .config import Config
from .datasource import DataSource, FileDataSource
from .locales import load_overlays
from .profile import FeedRow

_WEEK = r"^\d{4}-W\d{2}$"  # ISO year-week; a malformed value 422s instead of reaching the source
_FIXED_PARAMS = {"feed", "location", "indicator", "week_from", "week_to"}

_UI_DIR = Path(__file__).resolve().parent / "_ui"
_PLACEHOLDER = (
    "<!doctype html><meta charset='utf-8'>"
    "<title>health-signal</title>"
    "<h1>health-signal</h1>"
    "<p>The compiled frontend (<code>_ui/index.html</code>) was not found. "
    "Build the frontend, or install a release wheel that bundles it.</p>"
)


def render_index(page: str, config_payload: dict, base_href: str = "/") -> str:
    # Embed config as HTML-safe JSON so a config value can't break out of the <script>.
    blob = json.dumps(config_payload).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    tag = f"<script>window.__HS_CONFIG__ = {blob};</script>"
    page = page.replace("</head>", tag + "</head>", 1) if "</head>" in page else tag + page
    # The bundle's asset URLs are relative (so a mount prefix works); the base anchors them at the app
    # root, or /covid/clinical would load ./assets from /covid/assets. It must precede every URL.
    base = f'<base href="{html.escape(base_href)}">'
    return re.sub(r"<head[^>]*>", lambda m: m.group(0) + base, page, count=1) if "<head" in page else base + page


def _serve_spa(config: Config, request: Request, titles: dict[str, str]) -> Response:
    index = _UI_DIR / "index.html"
    if not index.is_file():
        return HTMLResponse(_PLACEHOLDER)
    # Only the bootstrap slice (safe pre-login); the full view-model is gated behind /api/config. The title in each
    # language comes too: the sign-in page shows it before the deployment's gated text can load.
    base_href = request.scope.get("root_path", "").rstrip("/") + "/"
    return HTMLResponse(render_index(index.read_text(encoding="utf-8"), {**config.bootstrap_config(), "titles": titles},
                                     base_href))


def _require_one_location(data_sources: dict, phase_source: PhaseSource | None) -> None:
    # With no location filter nothing selects a region, so every chart, tile and summary row would blend the
    # regions' rows: a dashboard without one shows a single population, or refuses to start.
    held = {f"feed {fid!r}": source.locations() for fid, source in data_sources.items()}
    if phase_source is not None:
        held["data.phases"] = {r.location for r in phase_source.phases()}
    # Across sources too: one region's clinical feed beside another's wastewater would mix them on the overview.
    every = set().union(*held.values())
    if len(every) > 1:
        sources = "; ".join(f"{where}: {', '.join(sorted(locations))}" for where, locations in held.items() if locations)
        raise ValueError(f"the data hold several locations ({', '.join(sorted(every))}) but no filters.location is "
                         f"configured; add one so each view shows one region ({sources})")


def create_app(
    config: Config, auth_provider: AuthProvider | None = None,
    data_sources: dict[str, DataSource] | None = None,
) -> FastAPI:
    app = FastAPI(title=config.site.title)
    overlays = load_overlays(config.site.locales_dir, config.site.locales)
    titles = {lang: text["site"]["title"] for lang, text in overlays.items()
              if isinstance(text.get("site"), dict) and "title" in text["site"]}
    provider = auth_provider if auth_provider is not None else _auth.from_env()
    provider.install(app)
    feeds = config.data.feeds if config.data else []
    if data_sources is None:
        data_sources = {f.id: FileDataSource(f.dir, config.profile(f.profile)) for f in feeds}
    assessment_sources = {f.id: AssessmentSource(f.assessments, config.profile(f.profile)) for f in feeds if f.assessments}
    phase_source = PhaseSource(config.data.phases) if config.data and config.data.phases else None
    stream_source = (PhaseStreamSource(config.data.phase_streams, {f.id: config.profile(f.profile) for f in feeds})
                     if config.data and config.data.phase_streams else None)
    if config.filters.location is None:
        _require_one_location(data_sources, phase_source)

    _ALWAYS_PUBLIC = ("/healthz", "/login", "/logout")

    def is_public(path: str) -> bool:
        # Operational endpoints are public by exact match only (/login/private stays gated);
        # public_paths match by prefix at a path boundary ("/" = whole site).
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

    @app.get("/api/locales/{language}")
    def get_locale(language: str, user: User = Depends(require_auth)) -> dict:
        # Gated like /api/config: this text labels the structure only signed-in users are sent.
        if language not in config.site.locales:
            raise HTTPException(status_code=404, detail=f"{language!r} is not one of this dashboard's languages")
        return overlays.get(language, {})

    def _feed_dimensions(feed: str, request: Request, fixed: set[str] = _FIXED_PARAMS) -> dict[str, str]:
        # Dimension filters come from the feed's profile, so a new profile needs no route change.
        source = data_sources.get(feed)
        if source is None:
            raise HTTPException(status_code=422, detail=f"unknown feed {feed!r}")
        dimensions = {k: v for k, v in request.query_params.items() if k not in fixed}
        unknown = dimensions.keys() - set(source.profile.dimension_keys)
        if unknown:
            # An ignored filter would silently widen the result.
            raise HTTPException(status_code=422, detail=f"unknown filter(s) {', '.join(sorted(unknown))} for feed {feed!r}")
        return dimensions

    @app.get("/api/data", response_model=list[FeedRow])
    def get_data(
        request: Request,
        feed: str,
        user: User = Depends(require_auth),
        location: str | None = None,
        indicator: str | None = None,
        week_from: str | None = Query(default=None, pattern=_WEEK),
        week_to: str | None = Query(default=None, pattern=_WEEK),
    ) -> list[FeedRow]:
        dimensions = _feed_dimensions(feed, request)
        return data_sources[feed].query(location=location, indicator=indicator, week_from=week_from,
                                        week_to=week_to, **dimensions)

    @app.get("/api/assessments", response_model=list[AssessmentRow])
    def get_assessments(
        request: Request,
        feed: str,
        user: User = Depends(require_auth),
        location: str | None = None,
        indicator: str | None = None,
        method: str | None = None,
        week_from: str | None = Query(default=None, pattern=_WEEK),
        week_to: str | None = Query(default=None, pattern=_WEEK),
    ) -> list[AssessmentRow]:
        dimensions = _feed_dimensions(feed, request, _FIXED_PARAMS | {"method"})
        source = assessment_sources.get(feed)  # optional per feed: none means no tiles, not an error
        return source.assessments(location=location, indicator=indicator, week_from=week_from, week_to=week_to,
                                  dimensions=dimensions, method=method) if source else []

    @app.get("/api/thresholds", response_model=list[ThresholdRow])
    def get_thresholds(
        request: Request,
        feed: str,
        user: User = Depends(require_auth),
        location: str | None = None,
        indicator: str | None = None,
        method: str | None = None,
        week_from: str | None = Query(default=None, pattern=_WEEK),
        week_to: str | None = Query(default=None, pattern=_WEEK),
    ) -> list[ThresholdRow]:
        dimensions = _feed_dimensions(feed, request, _FIXED_PARAMS | {"method"})
        source = assessment_sources.get(feed)
        return source.thresholds(location=location, indicator=indicator, week_from=week_from, week_to=week_to,
                                 dimensions=dimensions, method=method) if source else []

    @app.get("/api/phase-streams", response_model=list[PhaseStreamRow])
    def get_phase_streams(
        request: Request,
        user: User = Depends(require_auth),
        location: str | None = None,
        pathogen: str | None = None,
        method: str | None = None,
    ) -> list[PhaseStreamRow]:
        unknown = request.query_params.keys() - {"location", "pathogen", "method"}
        if unknown:
            # An ignored typo would silently return every pathogen's streams.
            raise HTTPException(status_code=422, detail=f"unknown filter(s) {', '.join(sorted(unknown))}")
        return stream_source.streams(location=location, pathogen=pathogen, method=method) if stream_source else []

    @app.get("/api/phases", response_model=list[PhaseRow])
    def get_phases(
        request: Request,
        user: User = Depends(require_auth),
        location: str | None = None,
        pathogen: str | None = None,
        method: str | None = None,
        week_from: str | None = Query(default=None, pattern=_WEEK),
        week_to: str | None = Query(default=None, pattern=_WEEK),
    ) -> list[PhaseRow]:
        unknown = request.query_params.keys() - {"location", "pathogen", "method", "week_from", "week_to"}
        if unknown:
            # An ignored typo (?pathogn=) would silently return every pathogen.
            raise HTTPException(status_code=422, detail=f"unknown filter(s) {', '.join(sorted(unknown))}")
        return phase_source.phases(location=location, pathogen=pathogen, method=method,
                                   week_from=week_from, week_to=week_to) if phase_source else []

    @app.get("/api/periods")
    def get_periods(user: User = Depends(require_auth)) -> dict | None:
        # The date-range control's bounds across every feed; null when there's no data to range over.
        spans = [s for s in (source.periods() for source in data_sources.values()) if s]
        if not spans:
            return None
        return {"first": min(first for first, _ in spans), "last": max(last for _, last in spans)}

    if (_UI_DIR / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=_UI_DIR / "assets"), name="assets")

    # Registered last so specific routes win. Unmatched /api/* 404s before the page policy, so
    # public_paths can't turn it into SPA HTML.
    @app.get("/{path:path}")
    async def spa(path: str, request: Request) -> Response:
        full_path = "/" + path
        is_api = full_path == "/api" or full_path.startswith("/api/")
        if is_api:
            raise HTTPException(status_code=404, detail="Not found")

        if is_public(full_path):
            return _serve_spa(config, request, titles)
        if await provider.current_user(request) is not None:
            return _serve_spa(config, request, titles)
        return RedirectResponse(url="/login", status_code=303)

    return app
