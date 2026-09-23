# health-signal — Stage 1 (PR #2): Package skeleton & FastAPI app factory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the installable `health-signal` Python package with a `create_app(config)` FastAPI factory, YAML config loading, a health endpoint, a graceful SPA-serving seam, and a pytest CI workflow — the foundation every later stage builds on.

**Architecture:** A `hatchling`-built package exposing `create_app(config) -> FastAPI` and `load_config(path) -> Config`. The app serves `/healthz` and a catch-all that returns the compiled SPA (`src/health_signal/_ui/`) when present, else a placeholder (the real UI arrives in a later stage; auth gating arrives in PR #3). Config is a Pydantic model validated on load.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, Pydantic v2, PyYAML, hatchling; pytest + Starlette `TestClient` (httpx) for tests.

**Spec:** `docs/specs/2026-09-23-reusable-surveillance-dashboard-design.md` (read §3–§8, §10, §12).

## Global Constraints

- **Python** `>=3.11`.
- **Package:** distribution name `health-signal`, import name `health_signal`; layout `src/health_signal/`.
- **Build:** `hatchling`; the Vite build lands in `src/health_signal/_ui/` and ships as wheel package data via `[tool.hatch.build.targets.wheel] artifacts = ["src/health_signal/_ui/**"]`. `_ui/` is gitignored (build output) — never commit into it.
- **No TypeScript** (frontend stages); Python is typed via Pydantic.
- **Testing:** outside-in — integration/E2E through real seams first (here: `TestClient` against the assembled app), unit tests for focused logic (config validation).
- **Data governance:** public repo — synthetic dummy data only in tests/fixtures; **no Greece pilot data**.
- **Delivery:** this stage is one PR, ≤800 LOC; Copilot review → iterate → user review → merge; the compliance CI (already on `main`) must stay green.

---

## Stage roadmap (context — each is its own future plan + PR)

- **PR #2 (this plan):** package skeleton + FastAPI `create_app` + config + `/healthz` + SPA seam + pytest CI.
- **PR #3:** `AuthProvider` + `LocalAccountsProvider` (Connect secrets, argon2 hashing, signed-cookie sessions) + `require_auth` dependency + `/login`,`/logout`,`/api/me`; gate all routes.
- **PR #4:** `DataSource` + `FileDataSource` + ERVISS schema profile (Pydantic) + contract validation + `/api/config`,`/api/data`,`/api/locales/{lang}` (+ layered locale merge).
- **PR #5:** React+Vite+JS+MUI frontend scaffold — config-driven shell, React Router pages, login screen, react-i18next (en/el), runtime theme from config; wheel packaging of the build.
- **PR #6:** pathogen panels — Status/Trend tiles, charts, season/wave band, range selector, methodology view, `/api/methodology/{lang}`, OpenAPI polish.
- **PR #7+:** Greek migration (consumer repo): ETL → ERVISS feed, `dashboard.yaml`, locales, branding, Posit Connect deploy.

---

## File structure (PR #2)

- Create `pyproject.toml` — build config, deps, package/wheel/test settings.
- Create `src/health_signal/__init__.py` — public API re-exports (`create_app`, `load_config`).
- Create `src/health_signal/config.py` — Pydantic `Config` model + `load_config`.
- Create `src/health_signal/app.py` — `create_app` factory, `/healthz`, SPA serving seam.
- Create `tests/test_config.py` — config load/validation (unit).
- Create `tests/test_app.py` — health + SPA-seam integration via `TestClient`.
- Create `.github/workflows/test.yml` — pytest CI on push + PR.

---

### Task 1: Package skeleton + build config

**Files:**
- Create: `pyproject.toml`
- Create: `src/health_signal/__init__.py`
- Test: `tests/test_import.py`

**Interfaces:**
- Produces: importable package `health_signal` exposing names `create_app` and `load_config` (defined in Tasks 2–3; re-exported here).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_import.py
def test_package_exposes_public_api():
    import health_signal
    assert hasattr(health_signal, "create_app")
    assert hasattr(health_signal, "load_config")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pip install -e ".[dev]" && pytest tests/test_import.py -v`
Expected: FAIL — `pyproject.toml` / package does not exist yet (install or import error).

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "health-signal"
version = "0.1.0"
description = "Reusable, configuration-driven respiratory-surveillance dashboard library"
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
authors = [{ name = "Wei Lu", email = "wlu4@worldbank.org" }]
dependencies = [
  "fastapi>=0.110",
  "uvicorn>=0.29",
  "pydantic>=2.6",
  "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "httpx>=0.27"]

[tool.hatch.build.targets.wheel]
packages = ["src/health_signal"]
artifacts = ["src/health_signal/_ui/**"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 4: Write `src/health_signal/__init__.py`**

```python
from .app import create_app
from .config import Config, load_config

__all__ = ["create_app", "load_config", "Config"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pip install -e ".[dev]" && pytest tests/test_import.py -v`
Expected: PASS. (Tasks 2–3 supply the imported symbols; do Task 1 alongside them if importing early fails.)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/health_signal/__init__.py tests/test_import.py
git commit -m "feat: package skeleton (hatchling) exposing create_app/load_config"
```

---

### Task 2: Config model + loader

**Files:**
- Create: `src/health_signal/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `class Config(BaseModel)` with fields `schema_version: str`, `site: SiteConfig`, `branding: Branding`.
  - `class SiteConfig(BaseModel)` with `title: dict[str, str]`, `default_locale: str = "en"`, `locales: list[str] = ["en"]`.
  - `class Branding(BaseModel)` with `logo: str | None`, `favicon: str | None`, `theme: dict`.
  - `def load_config(path: str | Path) -> Config` — reads YAML, validates, returns `Config`; raises `pydantic.ValidationError` on bad input.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import pytest
from pydantic import ValidationError
from health_signal.config import load_config


def test_load_valid_config(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text(
        "schema_version: '0.1'\n"
        "site:\n"
        "  title: { en: 'X' }\n",
        encoding="utf-8",
    )
    cfg = load_config(f)
    assert cfg.schema_version == "0.1"
    assert cfg.site.title["en"] == "X"
    assert cfg.site.default_locale == "en"      # default applied


def test_missing_required_field_raises(tmp_path):
    f = tmp_path / "c.yaml"
    f.write_text("site:\n  title: { en: 'X' }\n", encoding="utf-8")   # no schema_version
    with pytest.raises(ValidationError):
        load_config(f)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `health_signal.config` / `load_config` not defined.

- [ ] **Step 3: Write `src/health_signal/config.py`**

```python
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Branding(BaseModel):
    logo: str | None = None
    favicon: str | None = None
    theme: dict = Field(default_factory=dict)


class SiteConfig(BaseModel):
    title: dict[str, str]                 # locale code -> display title
    default_locale: str = "en"
    locales: list[str] = Field(default_factory=lambda: ["en"])


class Config(BaseModel):
    schema_version: str
    site: SiteConfig
    branding: Branding = Field(default_factory=Branding)


def load_config(path: str | Path) -> Config:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return Config.model_validate(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add src/health_signal/config.py tests/test_config.py
git commit -m "feat: Pydantic Config model + YAML load_config"
```

---

### Task 3: `create_app` factory + `/healthz` + SPA-serving seam

**Files:**
- Create: `src/health_signal/app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `Config`, `load_config` (Task 2).
- Produces: `def create_app(config: Config) -> FastAPI`. Registers `GET /healthz` → `{"status": "ok", "schema_version": <config.schema_version>}`. Registers a catch-all `GET /{path:path}` that returns the compiled SPA `index.html` from `src/health_signal/_ui/` when present, else an HTML placeholder containing the text `health-signal`. When `_ui/assets/` exists it is mounted at `/assets`.

- [ ] **Step 1: Write the failing tests (integration, outside-in)**

```python
# tests/test_app.py
from fastapi.testclient import TestClient
from health_signal import create_app, load_config


def _client(tmp_path):
    f = tmp_path / "dashboard.yaml"
    f.write_text(
        "schema_version: '0.1'\n"
        "site:\n"
        "  title: { en: 'Test Dashboard' }\n"
        "  default_locale: en\n"
        "  locales: [en]\n",
        encoding="utf-8",
    )
    return TestClient(create_app(load_config(f)))


def test_healthz_ok(tmp_path):
    r = _client(tmp_path).get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["schema_version"] == "0.1"


def test_spa_placeholder_when_ui_absent(tmp_path):
    # No compiled _ui/ in a source checkout, so the catch-all serves the placeholder.
    r = _client(tmp_path).get("/")
    assert r.status_code == 200
    assert "health-signal" in r.text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_app.py -v`
Expected: FAIL — `health_signal.app` / `create_app` not defined.

- [ ] **Step 3: Write `src/health_signal/app.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_app.py -v`
Expected: PASS (both).

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: all tests pass (import, config, app).

- [ ] **Step 6: Commit**

```bash
git add src/health_signal/app.py tests/test_app.py
git commit -m "feat: create_app factory with /healthz and SPA-serving seam"
```

---

### Task 4: pytest CI workflow

**Files:**
- Create: `.github/workflows/test.yml`

**Interfaces:**
- Produces: a GitHub Actions workflow running `pytest` on push + pull_request, so later PRs are test-gated alongside the existing compliance workflow.

- [ ] **Step 1: Write `.github/workflows/test.yml`**

```yaml
---
name: Tests
on:
  push:
  pull_request:
permissions:
  contents: read
jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install
        run: pip install -e ".[dev]"
      - name: Test
        run: pytest -q
```

- [ ] **Step 2: Verify YAML is well-formed locally**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/test.yml')); print('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "ci: run pytest on push and pull_request"
```

---

## Self-review

**Spec coverage (PR #2 slice):** app factory (§4/§8) ✓ Task 3; config loading (§10 consumer `create_app(load_config(...))`) ✓ Task 2; SPA-serving seam + catch-all-last (§8) ✓ Task 3; hatchling `_ui` package-data wiring (§10) ✓ Task 1; outside-in tests (§12) ✓ Tasks 2–3; pytest CI ✓ Task 4. Auth (§7.2), data/profiles (§6/§7.1), frontend/i18n/theming (§5/§9), methodology + API docs (§7.3/§8/§9) are **out of scope for PR #2** — assigned to PRs #3–#6 in the roadmap.

**Placeholder scan:** none — every step carries real code/commands.

**Type consistency:** `create_app(config: Config)` and `load_config(path) -> Config` match across `__init__.py`, `app.py`, `config.py`, and both test modules; `Config.schema_version` / `SiteConfig.title`/`default_locale` used consistently in tests and implementation.

**Note:** PR #2's app is **not yet auth-gated** (gating lands in PR #3) — do not deploy it publicly until then; local/CI use only.
