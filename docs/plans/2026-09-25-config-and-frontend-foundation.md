# Config + Frontend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the config layer end-to-end — the server projects the loaded `dashboard.yaml` into two whitelisted views (a **bootstrap** slice injected into the HTML for pre-login rendering, and a **full view-model** served by a gated `GET /api/config`), and a React/Vite/MUI SPA foundation renders the shell, a login page, and a read-only Configuration view that fetches `/api/config`.

**Architecture:** Config has one source of truth — `dashboard.yaml` (loaded into `Config`). The server exposes it to the client two ways, split on auth: (1) a small **bootstrap** slice (title, branding, locales) injected into `index.html` as `window.__HS_CONFIG__`, so the shell + login render pre-login with no fetch; (2) the **full client view-model** (targets, pages, i18n keys) via the gated `GET /api/config`, which the authenticated SPA fetches. Server-only fields (`public_paths`, data-source, secrets) are in neither. Data (`/api/data`) is deferred to the next stage.

**Tech Stack:** FastAPI (Python 3.11+, existing); React 18 + Vite, plain JavaScript/JSX (no TypeScript); MUI (Material UI) with minimal custom CSS; React Router; react-i18next (`en` + `el`, default `en`); hatchling (Vite build baked into the wheel as `src/health_signal/_ui/**`); uv for the Python dev workflow.

**Spec:** `docs/specs/2026-09-23-reusable-surveillance-dashboard-design.md` (§5 tech stack, §6 config/data contract, §7.4 access policy, §8 routes, §9 frontend & i18n, §10 packaging).

## Global Constraints

- **Frontend language: plain JavaScript (JSX), no TypeScript** (spec §5).
- **UI via canonical MUI components + MUI styling (`theme`, `sx`, `styled`); custom CSS is a last resort** — the prototype's `styles.css` is not carried over (spec §9).
- **Theme is built at runtime from the config branding block** (MUI `ThemeProvider`); a government restyles via `dashboard.yaml` with no rebuild (spec §9).
- **i18n: react-i18next, locales `en` + `el`, default `en`; the library ships the base UI-string catalog** at `src/health_signal/locales/{en,el}.json` (spec §9, §10).
- **Config carries keys, not translations** — `dashboard.yaml` holds structure + i18n keys, never inline `{en, el}` maps. `site.title` (names the app) stays a plain string (spec §9).
- **Packaging:** distribution name `health-signal`, import `health_signal`; `pyproject.toml` `artifacts=["src/health_signal/_ui/**"]`; `frontend/` builds to `src/health_signal/_ui` (spec §10). `_ui/` is gitignored (compiled artifact).
- **Synthetic data only** — this repo is public; no pilot data in fixtures/examples (spec §12).
- **≤800 lines of changed code** per PR (generated bundles + lockfiles excluded). If the frontend foundation overflows, split it: 3a = scaffold + shell + config render; 3b = i18n depth + theming polish.
- **Merge method: regular merge commit** (`gh pr merge --merge`), not squash.
- **Copilot-review loop then user review**, per the established workflow.

## Config delivery model (2026-09-25)

Config reaches the client two ways, split on the auth boundary (this keeps spec §8's gated `/api/config` and adds bootstrap injection for pre-login rendering):

- **Pre-login → bootstrap injected into the served HTML.** The server injects a whitelisted slice (`title`, `branding`, `defaultLocale`, `locales`) into `index.html` as `window.__HS_CONFIG__`, so the shell + login page render synchronously with **no fetch and nothing gated**. The `dashboard.yaml` itself is never exposed.
- **Post-login → SPA fetches gated `GET /api/config`.** Returns the full client view-model (`targets`/`pages`/i18n keys). The read-only Configuration page consumes it, and later so does config-driven rendering.
- **Server-only fields** (`public_paths`, data-source config, secrets) appear in **neither** the bootstrap nor `/api/config`.

`/api/data` (dynamic, queried) is the next stage.

## Review Focus

- **Config value containing `</script>` or `<`/`>`/`&` breaks HTML injection.** Config strings are deployer-controlled, but an unescaped `</script>` in a label still corrupts the page or enables injection. The injected JSON must be HTML-safe (escape `<`, `>`, `&`, and U+2028/U+2029). — pinned in Task 2.
- **The full view-model leaking to an anonymous viewer.** The structure (`targets`/`pages`) must only ever leave via the gated `/api/config` — the HTML injection carries the bootstrap slice only, and `/api/config` must return `401` unauthenticated. — pinned in Task 2 (`test_api_config_requires_auth`, `test_spa_injects_bootstrap_only`).
- **Config with an empty/absent `pages` (or `pathogens`) list.** A deployer may start with a near-empty config; the projection and the SPA shell must render (empty nav, no crash), not throw. — pinned in Task 1 and Task 4.
- **A configured i18n key with no matching entry in the locale files.** react-i18next must fall back (to the key or `en`), not render blank/undefined; the base catalog must exist for `en` and `el`. — pinned in Task 4.
- **SPA served before the frontend is built (`_ui/index.html` absent).** Injection must degrade to the existing placeholder without error (the wheel always has `_ui`, but dev/tests may not). — pinned in Task 2.

---

## File structure

**Backend (Python):**
- `src/health_signal/config.py` (modify) — extend the Pydantic models with the view-model fields (targets/pathogens, pages/nav, i18n keys); add `bootstrap_config()` and `client_config()` projection methods returning plain whitelisted dicts.
- `src/health_signal/app.py` (modify) — add a pure `render_index(html, config_payload)` helper (HTML-safe JSON injection); `_serve_spa` injects only the bootstrap projection into the served HTML, and a gated `GET /api/config` serves the full client view-model.
- `src/health_signal/locales/en.json`, `src/health_signal/locales/el.json` (create) — base UI-string catalog (generic chrome).
- `tests/test_config.py` (create) — projection unit tests.
- `tests/test_app.py` (modify) — injection/tiering integration tests.

**Frontend (`frontend/`, new — JS/JSX):**
- `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`, `frontend/.gitignore`
- `frontend/src/main.jsx` — entry: read `window.__HS_CONFIG__`, mount providers.
- `frontend/src/config.js` — read/validate the injected config object.
- `frontend/src/theme.js` — build the MUI theme from `branding`.
- `frontend/src/i18n.js` — react-i18next init from bundled base locales.
- `frontend/src/App.jsx` — Router + shell (nav from config).
- `frontend/src/pages/LoginPage.jsx` — MUI login form (native POST to `/login`).
- `frontend/src/pages/ConfigView.jsx` — read-only Configuration view.
- `frontend/src/locales/{en,el}.json` — copies of the base catalog for the FE bundle (kept in sync with the Python-side base; see Task 3).

**Packaging / CI:**
- `pyproject.toml` (modify) — confirm/add `artifacts=["src/health_signal/_ui/**"]`.
- `.github/workflows/ci.yml` (modify) — add a Node build step producing `_ui/` before the packaging check (pytest does not require `_ui`).
- `.gitignore` (modify) — ignore `src/health_signal/_ui/` and `frontend/node_modules/`.

---

## Task 1: Config view-model + projections

**Files:**
- Modify: `src/health_signal/config.py`
- Test: `tests/test_config.py` (create)

**Interfaces:**
- Consumes: existing `Config`, `SiteConfig`, `Branding`.
- Produces:
  - `class Target(BaseModel)`: `id: str`, `label_key: str | None = None`, `pages: list[Page] = []`
  - `class Page(BaseModel)`: `id: str`, `path: str`, `label_key: str | None = None`
  - `Config.bootstrap_config(self) -> dict` — `{"title", "branding", "defaultLocale", "locales"}`
  - `Config.client_config(self) -> dict` — bootstrap fields **plus** `{"targets": [...], "pages": [...]}` (never `public_paths`, data-source, or `schema_version`)

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config.py
import pytest
from pydantic import ValidationError
from health_signal.config import Config, SiteConfig, Branding, Target, Page


def _cfg(**site_over):
    site = {"title": "Demo", "default_locale": "en", "locales": ["en", "el"]}
    site.update(site_over)
    return Config(schema_version="0.1", site=SiteConfig(**site))


def test_bootstrap_config_is_whitelisted():
    cfg = _cfg(public_paths=["/about"])
    b = cfg.bootstrap_config()
    assert b == {
        "title": "Demo",
        "branding": {"logo": None, "favicon": None, "theme": {}},
        "defaultLocale": "en",
        "locales": ["en", "el"],
    }
    # server-only fields never leak into the client payload
    assert "public_paths" not in b and "schema_version" not in b


def test_client_config_adds_structure_but_not_server_only():
    cfg = Config(
        schema_version="0.1",
        site=SiteConfig(title="Demo", public_paths=["/about"]),
        targets=[Target(id="covid-19", pages=[Page(id="overview", path="/covid-19/overview")])],
    )
    c = cfg.client_config()
    assert c["title"] == "Demo"
    assert c["targets"][0]["id"] == "covid-19"
    assert c["targets"][0]["pages"][0]["path"] == "/covid-19/overview"
    assert "public_paths" not in c and "schema_version" not in c


def test_empty_targets_projects_cleanly():
    c = _cfg().client_config()
    assert c["targets"] == []


def test_page_requires_path():
    with pytest.raises(ValidationError):
        Page(id="overview")  # no path
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL (`ImportError: cannot import name 'Target'`).

- [ ] **Step 3: Implement**

```python
# add to src/health_signal/config.py (models near SiteConfig)
class Page(BaseModel):
    id: str
    path: str
    label_key: str | None = None  # i18n key; text lives in locale files, not config


class Target(BaseModel):
    # A surveillance target (e.g. a pathogen). label_key -> locale files; id can derive one by convention.
    id: str
    label_key: str | None = None
    pages: list[Page] = Field(default_factory=list)


# add targets to Config (structure the authed UI renders)
class Config(BaseModel):
    schema_version: str
    site: SiteConfig
    branding: Branding = Field(default_factory=Branding)
    targets: list[Target] = Field(default_factory=list)

    def bootstrap_config(self) -> dict:
        # Whitelisted slice injected pre-login: only what the shell + login page need.
        return {
            "title": self.site.title,
            "branding": self.branding.model_dump(),
            "defaultLocale": self.site.default_locale,
            "locales": self.site.locales,
        }

    def client_config(self) -> dict:
        # Full client view-model (authenticated). Superset of bootstrap; still excludes server-only
        # fields (public_paths, schema_version, future data-source config).
        return {
            **self.bootstrap_config(),
            "targets": [t.model_dump() for t in self.targets],
        }
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/health_signal/config.py tests/test_config.py
git commit -m "feat(config): view-model with bootstrap/client projections"
```

---

## Task 2: Config delivery — bootstrap injection + gated `/api/config`

**Files:**
- Modify: `src/health_signal/app.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `Config.bootstrap_config()`, `Config.client_config()` (Task 1); `require_auth` + `_serve_spa` (existing).
- Produces: `render_index(html: str, config_payload: dict) -> str` (module-level, pure); `_serve_spa` injects the **bootstrap** projection into the served HTML; a gated `GET /api/config` returning `client_config()`.

**Design:** the HTML injection carries **only the bootstrap** (safe for anon; enough for shell + login). The full view-model is served by the gated `/api/config`, which the authed SPA fetches. So there's no auth-tiering in the injection — the sensitive structure only ever leaves via the gated endpoint.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_app.py — add
from health_signal.app import render_index
from health_signal.config import Target, Page


def test_render_index_injects_safe_json():
    out = render_index("<html><head></head><body></body></html>", {"title": "A</script><b>"})
    assert "window.__HS_CONFIG__" in out
    assert "</script>" not in out.split("window.__HS_CONFIG__", 1)[1].split("</script>", 1)[0]  # no breakout
    assert "\\u003c" in out  # '<' escaped


def test_spa_injects_bootstrap_only(tmp_path, monkeypatch):
    monkeypatch.setattr("health_signal.app._UI_DIR", _write_ui(tmp_path))  # writes index.html, returns dir
    body = _client(public_paths=["/"]).get("/").text
    assert "__HS_CONFIG__" in body and '"title"' in body
    assert "targets" not in body  # structure is NOT injected; it comes from /api/config


def test_spa_falls_back_to_placeholder_when_ui_missing():
    r = _client(public_paths=["/"]).get("/")  # no _ui/index.html in tests
    assert r.status_code == 200  # placeholder served, no crash


def test_api_config_requires_auth():
    assert _client().get("/api/config").status_code == 401


def test_api_config_returns_view_model_when_authed():
    client = _client(targets=[Target(id="covid-19", pages=[Page(id="ov", path="/covid-19/ov")])])
    client.post("/login", data={"email": _EMAIL, "password": _PASSWORD}, follow_redirects=False)
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert body["targets"][0]["id"] == "covid-19"
    assert "public_paths" not in body  # server-only never exposed
```

Add a `_write_ui(tmp_path)` helper near the other test helpers (writes `index.html` with a `</head>` into `tmp_path/_ui`, returns that dir), and extend `_client(...)` to accept `targets=` and pass it through to `Config`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_app.py -k "render_index or bootstrap_only or api_config or placeholder" -v`
Expected: FAIL (`ImportError: render_index`; `/api/config` 404).

- [ ] **Step 3: Implement**

```python
# src/health_signal/app.py
import json

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
```

Update the catch-all's `_serve_spa()` call sites to `_serve_spa(config)`. Add the gated endpoint next to `GET /api/me`:

```python
    @app.get("/api/config")
    def get_config(user: User = Depends(require_auth)) -> dict:
        return config.client_config()
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_app.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/health_signal/app.py tests/test_app.py
git commit -m "feat(app): inject bootstrap config into SPA HTML; gated GET /api/config"
```

---

## Task 3: Frontend scaffold + build wiring + base locales

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.js`, `frontend/index.html`, `frontend/.gitignore`, `frontend/src/main.jsx`, `frontend/src/App.jsx`
- Create: `src/health_signal/locales/en.json`, `src/health_signal/locales/el.json`
- Modify: `pyproject.toml`, `.github/workflows/ci.yml`, `.gitignore`

**Interfaces:**
- Produces: a `npm run build` in `frontend/` that emits `../src/health_signal/_ui/{index.html,assets/**}`; the wheel includes `_ui/**`.

- [ ] **Step 1: Scaffold files**

`frontend/package.json`:
```json
{
  "name": "health-signal-ui",
  "private": true,
  "type": "module",
  "scripts": { "build": "vite build", "dev": "vite" },
  "dependencies": {
    "react": "^18.3.1", "react-dom": "^18.3.1", "react-router-dom": "^6.26.0",
    "@mui/material": "^5.16.0", "@emotion/react": "^11.13.0", "@emotion/styled": "^11.13.0",
    "i18next": "^23.12.0", "react-i18next": "^15.0.0"
  },
  "devDependencies": { "vite": "^5.4.0", "@vitejs/plugin-react": "^4.3.0" }
}
```

`frontend/vite.config.js`:
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: { outDir: '../src/health_signal/_ui', emptyOutDir: true },
})
```

`frontend/index.html`:
```html
<!doctype html>
<html>
  <head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" /><title>health-signal</title></head>
  <body><div id="root"></div><script type="module" src="/src/main.jsx"></script></body>
</html>
```

`frontend/.gitignore`: `node_modules/` and `dist/`.

`frontend/src/main.jsx` (minimal, expanded in Task 4):
```javascript
import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(<App />)
```

`frontend/src/App.jsx` (minimal placeholder, replaced in Task 4):
```javascript
export default function App() {
  return <div>health-signal</div>
}
```

- [ ] **Step 2: Base locale catalogs**

`src/health_signal/locales/en.json`:
```json
{ "app": { "loading": "Loading…" }, "nav": { "configuration": "Configuration" },
  "login": { "title": "Sign in", "email": "Email", "password": "Password", "submit": "Sign in" },
  "config": { "title": "Configuration", "targets": "Surveillance targets", "locales": "Languages", "error": "Couldn't load configuration" } }
```

`src/health_signal/locales/el.json` (same keys, Greek values):
```json
{ "app": { "loading": "Φόρτωση…" }, "nav": { "configuration": "Διαμόρφωση" },
  "login": { "title": "Σύνδεση", "email": "Email", "password": "Κωδικός", "submit": "Σύνδεση" },
  "config": { "title": "Διαμόρφωση", "targets": "Στόχοι επιτήρησης", "locales": "Γλώσσες", "error": "Αποτυχία φόρτωσης διαμόρφωσης" } }
```

The FE reads these via `frontend/src/locales/*.json`; keep the two copies identical (a follow-up stage can generate one from the other — out of scope here). Copy the same JSON to `frontend/src/locales/en.json` and `frontend/src/locales/el.json`.

- [ ] **Step 3: Packaging + CI + gitignore**

In `pyproject.toml`, ensure the hatch build includes the compiled UI:
```toml
[tool.hatch.build.targets.wheel]
artifacts = ["src/health_signal/_ui/**"]
```
Add to `.gitignore`: `src/health_signal/_ui/` and `frontend/node_modules/`.
In `.github/workflows/ci.yml`, add before the build/package job:
```yaml
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm --prefix frontend ci
      - run: npm --prefix frontend run build
```

- [ ] **Step 4: Verify the build produces `_ui`**

Run:
```bash
npm --prefix frontend install && npm --prefix frontend run build
test -f src/health_signal/_ui/index.html && echo OK
uv run pytest -q
```
Expected: `_ui/index.html` exists; Python tests still pass (the placeholder path is unaffected).

- [ ] **Step 5: Commit**

```bash
git add frontend pyproject.toml .gitignore .github/workflows/ci.yml src/health_signal/locales
git commit -m "build(frontend): Vite/React/MUI scaffold + base locales + CI build step"
```

---

## Task 4: FE foundation — bootstrap reader, theme, i18n, router shell

**Files:**
- Create: `frontend/src/config.js`, `frontend/src/theme.js`, `frontend/src/i18n.js`
- Modify: `frontend/src/main.jsx`, `frontend/src/App.jsx`

**Interfaces:**
- Consumes: `window.__HS_CONFIG__` (Task 2 injects it).
- Produces: `getConfig()` (config.js), `buildTheme(branding)` (theme.js), an initialized i18n instance (i18n.js), and an `<App/>` that renders an MUI shell with nav derived from `config.targets`.

- [ ] **Step 1: config reader**

`frontend/src/config.js`:
```javascript
// Injected bootstrap (pre-login essentials); tolerate absence in dev.
export function getConfig() {
  const c = window.__HS_CONFIG__ || {}
  return {
    title: c.title || 'health-signal',
    branding: c.branding || {},
    defaultLocale: c.defaultLocale || 'en',
    locales: c.locales || ['en'],
  }
}

// Full client view-model (authenticated) from the gated endpoint. 401 -> caller shows login CTA.
export async function fetchConfig() {
  const res = await fetch('/api/config', { credentials: 'same-origin' })
  if (res.status === 401) { const e = new Error('unauthenticated'); e.status = 401; throw e }
  if (!res.ok) throw new Error(`config fetch failed: ${res.status}`)
  return res.json()
}
```

- [ ] **Step 2: theme from branding**

`frontend/src/theme.js`:
```javascript
import { createTheme } from '@mui/material/styles'

export function buildTheme(branding = {}) {
  const t = branding.theme || {}
  return createTheme({
    palette: {
      mode: t.mode || 'light',
      ...(t.primary ? { primary: { main: t.primary } } : {}),
    },
  })
}
```

- [ ] **Step 3: i18n init (base catalog, fallback to en)**

`frontend/src/i18n.js`:
```javascript
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import el from './locales/el.json'

export function initI18n({ defaultLocale = 'en' } = {}) {
  i18n.use(initReactI18next).init({
    resources: { en: { translation: en }, el: { translation: el } },
    lng: defaultLocale, fallbackLng: 'en', interpolation: { escapeValue: false },
  })
  return i18n
}
```

- [ ] **Step 4: App shell + router + providers**

`frontend/src/main.jsx`:
```javascript
import React from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider, CssBaseline } from '@mui/material'
import { I18nextProvider } from 'react-i18next'
import { getConfig } from './config.js'
import { buildTheme } from './theme.js'
import { initI18n } from './i18n.js'
import App from './App.jsx'

const cfg = getConfig()
const i18n = initI18n({ defaultLocale: cfg.defaultLocale })
createRoot(document.getElementById('root')).render(
  <ThemeProvider theme={buildTheme(cfg.branding)}>
    <CssBaseline />
    <I18nextProvider i18n={i18n}><App config={cfg} /></I18nextProvider>
  </ThemeProvider>,
)
```

`frontend/src/App.jsx`:
```javascript
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { AppBar, Toolbar, Typography, Button, Container } from '@mui/material'
import { useTranslation } from 'react-i18next'
import ConfigView from './pages/ConfigView.jsx'
import LoginPage from './pages/LoginPage.jsx'

export default function App({ config }) {
  const { t } = useTranslation()
  return (
    <BrowserRouter>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>{config.title}</Typography>
          <Button color="inherit" component={Link} to="/config">{t('nav.configuration')}</Button>
        </Toolbar>
      </AppBar>
      <Container sx={{ py: 3 }}>
        <Routes>
          <Route path="/login" element={<LoginPage config={config} />} />
          <Route path="/config" element={<ConfigView />} />
          <Route path="*" element={<ConfigView />} />
        </Routes>
      </Container>
    </BrowserRouter>
  )
}
```

- [ ] **Step 5: Build + commit**

```bash
npm --prefix frontend run build && test -f src/health_signal/_ui/index.html && echo OK
git add frontend/src
git commit -m "feat(frontend): bootstrap reader, MUI theme, i18n, router shell"
```

---

## Task 5: FE login page (native POST → server session → authed reload)

**Files:**
- Create: `frontend/src/pages/LoginPage.jsx`

**Interfaces:**
- Consumes: `config` (title/branding), the existing `POST /login` route (form fields `email`, `password`, 303 redirect on success).
- Produces: `<LoginPage config={config} />`.

**Design note:** the page submits a **native HTML form** to `/login` (no `fetch`). On success the server sets the session cookie and 303-redirects to `/`; the browser's full navigation reloads `index.html` (bootstrap injected as always). The now-authenticated SPA then fetches the gated `/api/config` for the full view-model (Task 6) — the redirect establishes the session so that fetch succeeds. i18n strings come from the bundled base catalog, so the login page itself needs no config fetch.

- [ ] **Step 1: Implement the page**

```javascript
import { Box, Paper, TextField, Button, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'

export default function LoginPage({ config }) {
  const { t } = useTranslation()
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', mt: 6 }}>
      <Paper sx={{ p: 4, width: 360 }} elevation={2}>
        <Typography variant="h5" gutterBottom>{config.title}</Typography>
        <Typography variant="subtitle1" gutterBottom>{t('login.title')}</Typography>
        {/* Native POST: server sets the session and 303-redirects to '/', which reloads with the full config. */}
        <form method="post" action="/login">
          <TextField name="email" type="email" label={t('login.email')} fullWidth required margin="normal" />
          <TextField name="password" type="password" label={t('login.password')} fullWidth required margin="normal" />
          <Button type="submit" variant="contained" fullWidth sx={{ mt: 2 }}>{t('login.submit')}</Button>
        </form>
      </Paper>
    </Box>
  )
}
```

- [ ] **Step 2: Build + manual check + commit**

```bash
npm --prefix frontend run build && test -f src/health_signal/_ui/index.html && echo OK
git add frontend/src/pages/LoginPage.jsx
git commit -m "feat(frontend): MUI login page (native POST to /login)"
```

---

## Task 6: FE read-only Configuration view (fetches `/api/config`)

**Files:**
- Create: `frontend/src/pages/ConfigView.jsx`

**Interfaces:**
- Consumes: `fetchConfig()` (Task 4 `config.js`) → the gated `/api/config` view-model (`title`, `locales`, `targets` with `pages`).
- Produces: `<ConfigView />` (no props — it self-fetches).

**Design:** the page fetches the full view-model from the gated endpoint, with three states — loading, `401` → a sign-in CTA, and error. This is also the stage's end-to-end proof: yaml → `client_config()` → `/api/config` → rendered.

- [ ] **Step 1: Implement the page**

```javascript
import { useEffect, useState } from 'react'
import { Typography, List, ListItem, ListItemText, Divider, Chip, Stack, Alert, Button } from '@mui/material'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { fetchConfig } from '../config.js'

export default function ConfigView() {
  const { t } = useTranslation()
  const [state, setState] = useState({ status: 'loading' })

  useEffect(() => {
    let live = true
    fetchConfig()
      .then((cfg) => { if (live) setState({ status: 'ok', cfg }) })
      .catch((e) => { if (live) setState({ status: e.status === 401 ? 'unauth' : 'error' }) })
    return () => { live = false }
  }, [])

  if (state.status === 'loading') return <Typography>{t('app.loading')}</Typography>
  if (state.status === 'unauth') return <Button component={Link} to="/login" variant="contained">{t('login.submit')}</Button>
  if (state.status === 'error') return <Alert severity="error">{t('config.error')}</Alert>

  const { cfg } = state
  return (
    <>
      <Typography variant="h4" gutterBottom>{t('config.title')}</Typography>
      <Typography variant="subtitle2">{t('config.locales')}</Typography>
      <Stack direction="row" spacing={1} sx={{ mb: 2 }}>
        {(cfg.locales || []).map((l) => <Chip key={l} label={l} size="small" />)}
      </Stack>
      <Divider sx={{ my: 2 }} />
      <Typography variant="subtitle2">{t('config.targets')}</Typography>
      <List dense>
        {(cfg.targets || []).map((target) => (
          <ListItem key={target.id} alignItems="flex-start">
            <ListItemText
              primary={target.label_key || target.id}
              secondary={(target.pages || []).map((p) => p.path).join('  ·  ') || '—'}
            />
          </ListItem>
        ))}
      </List>
    </>
  )
}
```

- [ ] **Step 2: Build + commit**

```bash
npm --prefix frontend run build && test -f src/health_signal/_ui/index.html && echo OK
git add frontend/src/pages/ConfigView.jsx
git commit -m "feat(frontend): read-only Configuration view"
```

---

## Self-Review

**1. Spec coverage.** §5 tech stack — React18/Vite/JS/MUI/React Router/react-i18next all in Tasks 3–4 ✅. §6 config structure — `targets`/`pages` in Task 1 (data-feed spine/profile is Stage 4) ✅. §7.4 access — reuses the merged policy; `/api/config` gated via `require_auth` (Task 2) ✅. §8 `/api/config` (required) — Task 2 ✅; injection adds pre-login bootstrap on top. §9 config-driven rendering, MUI theming from branding, layered i18n base catalog, config-carries-keys (`label_key`) — Tasks 1,3,4,6 ✅; methodology view + charts + `/api/locales`/`/api/methodology`/`/api/data` are deferred (Stage 4/later) — noted. §10 packaging (`frontend/` → `_ui`, artifacts, CI Node) — Task 3 ✅.

**2. Placeholder scan.** No TBD/TODO; each code step has concrete content. ✅

**3. Type consistency.** `bootstrap_config`/`client_config` (Task 1) are the exact methods called in Task 2. `getConfig()` shape (`title/branding/defaultLocale/locales/targets`) matches what Task 2 injects and Tasks 4–6 consume. `Target.pages[].path` used consistently in Task 1 tests and Task 6. ✅

**4. Review Focus.** `</script>` escaping → Task 2 `test_render_index_injects_safe_json`. Full-view-model leak → Task 2 `test_api_config_requires_auth` + `test_spa_injects_bootstrap_only`. Empty `targets` → Task 1 `test_empty_targets_projects_cleanly` + Task 6 renders empty list. Missing i18n key → i18n `fallbackLng: 'en'` (Task 4) + base catalog (Task 3). `_ui` absent → Task 2 `test_spa_falls_back_to_placeholder_when_ui_missing`. ✅
