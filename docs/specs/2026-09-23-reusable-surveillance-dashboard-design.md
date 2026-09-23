# Reusable Respiratory-Surveillance Dashboard — Design

**Date:** 2026-09-23
**Status:** Design (approved for planning)
**Author:** Wei Lu + Claude Code

## 1. Purpose & context

The Greek WBE pilot ships a working dashboard prototype: vanilla JS + Chart.js reading a
bespoke `data.json`, produced by a Python/`rpy2` ETL (aedseo Status/Trend), deployed as static
HTML to Posit Connect. We now want an **MVP** that is:

- **Modular** — surveillance targets/pathogens can be added, removed, and configured.
- **Internationalised** — English + Greek at launch, default English.
- **Authenticated** — app-managed accounts (not Posit Connect's own auth) so we can create
  logins for counterparts to review while keeping content off public eyes; SSO-ready for later
  federation with country government identity systems.
- **Reusable by other countries** — the generic dashboard lives in its own repo; the Greek repo
  consumes it as a library and supplies only country specifics.
- **Standards-based input** — the data feed adheres to an existing surveillance standard.
- **Deployable on Posit Connect.**

## 2. Goals & non-goals

### Goals (MVP)
- One generic, config-driven dashboard reusable across countries.
- App-managed authentication gating all content, no dependency beyond Posit Connect.
- A documented, versioned ETL→app data contract based on the EU/WHO ERVISS model.
- A pluggable data connector (files first; Postgres later) and a pluggable auth provider
  (local accounts first; OIDC/SAML later).
- Migrate the Greek dashboard onto the library.

### Non-goals (explicitly deferred)
- Postgres connector, **DHIS2 connector**, OIDC/SAML SSO, in-app aedseo analytics, roles/permissions
  beyond authenticated-or-not, data write-back, single-deployment multi-tenancy.
- **Non-respiratory schema profiles** (HIV, polio, AMR, Ebola, yellow fever, …). MVP ships only the
  ERVISS respiratory profile; the profile mechanism (§6) is designed so these add without a fork,
  but none are built now.

## 3. The Posit Connect constraint (why this shape)

Content must be **gated** but **not** via Posit Connect's own access control (counterparts have no
Connect accounts). Connect therefore serves the app as "anyone can access", and the app must
enforce login itself. A static bundle cannot: client-side-only auth leaves `data.json` and JS
directly fetchable. **Real gating needs a server that checks auth before serving data.** Posit
Connect runs **Python or R** app processes (Flask/FastAPI/Dash/Shiny/plumber) but **not Node**, so
the server is Python — a good fit with the existing Python/`rpy2` ETL. Hence: a **FastAPI app that
serves the compiled React SPA and a gated JSON API**, deployed as one Python content bundle.

## 4. Architecture

```
                         Posit Connect ("anyone can access")
   ┌──────────────────────────────────────────────────────────────────┐
   │  FastAPI app  (single Python content bundle)                       │
   │   Browser ──► [ AuthProvider ] ──► gated routes                     │
   │        ┌───────────┴───────────┬──────────────────┐                │
   │        ▼                       ▼                  ▼                │
   │   /login /me            /api/config /api/data   /  (SPA, _ui/)     │
   │   (sessions)            /api/locales                              │
   │                              │                                     │
   │                        [ DataSource ]  ◄── FileDataSource (MVP)    │
   │                              │              PostgresDataSource (later)│
   └──────────────────────────────┼─────────────────────────────────────┘
                                   ▼
                     ERVISS-shaped feed (+ extensions)  ◄── country ETL
                     files/  or  postgres table
```

The **generic library** ships the FastAPI app and the compiled React UI in one pip wheel. The
**country repo** supplies config + locales + data + branding + its ETL, and owns the deploy.

## 5. Tech stack

| Layer | Choice |
|---|---|
| Server | FastAPI (Python), deployed to Posit Connect as a Python app |
| Frontend | React 18 + Vite, **plain JavaScript (JSX)**, no TypeScript |
| i18n | react-i18next; `en` + `el`; default `en` |
| Charts | Chart.js (reused from the prototype) |
| Contract validation | Pydantic models in the server (single source of truth) |
| Packaging | hatchling; Vite build baked into the wheel as package data |
| Auth (MVP) | Local accounts via Connect secrets + signed-cookie sessions |
| Data (MVP) | Files in ERVISS format via `FileDataSource` |

## 6. Data contract (ETL ↔ app boundary)

The contract is a **domain-agnostic tidy long-format spine** plus a pluggable **schema profile**.
The spine is the same for every surveillance domain; a profile defines the domain-specific
dimensions, controlled vocabularies, indicators, and units. **ERVISS (respiratory) is the first
profile and the MVP** — other domains (HIV, polio, AMR, Ebola, yellow fever, …) register as
additional profiles later **without changing the core** (see §6.4). The app consumes only this
contract and never knows how the ETL produced it.

### 6.1 Generic spine (every profile shares)

| Field | Type | Notes |
|---|---|---|
| `location` | string | country/region (e.g. `Greece`, `Attica`) |
| `period` | string | ISO `YYYY-Www` (weekly) or ISO date; granularity declared by the profile |
| `dimensions` | object | profile-defined key/values (the domain's stratifiers) |
| `indicator` | string | from the profile's indicator vocabulary |
| `value` | number | semantics fixed by `indicator` + `unit` |
| `unit` | string | `per_100k` \| `count` \| `percent` \| … |
| `datasource` | string, optional | provenance (e.g. `GISAID`) |

A profile is a Pydantic-backed declaration: `dimensions` (names + controlled vocabularies),
`indicators`, `units`, `period` granularity, and validation rules. New rows — not schema changes —
add pathogens/strata/indicators within a profile.

### 6.2 ERVISS profile (respiratory — MVP)

The ECDC/WHO-Europe *European Respiratory Virus Surveillance Summary* public data model (repo
`EU-ECDC/Respiratory_viruses_weekly_data`, EUPL-1.2). Its `dimensions` and indicator vocabulary:

| Field | Type | Notes / allowed values |
|---|---|---|
| `survtype` | enum | `primary care sentinel` \| `primary care syndromic` \| `non-sentinel` \| `SARI syndromic` \| `SARI virological` (+ extensions in §6.3) |
| `pathogen` | enum, nullable | `Influenza` \| `RSV` \| `SARS-CoV-2` (null for pure ILI/ARI syndromic) |
| `pathogentype` | enum, nullable | `Influenza A/B`, `RSV-A/B`, `SARS-CoV-2`, … |
| `pathogensubtype` | enum, nullable | `A(H1)pdm09`, `A(H3)`, `B/Vic`, `B/Yam`, `total`, … |
| `age` | enum | `0-4` \| `5-14` \| `15-64` \| `65+` \| `total` \| `unk` |
| `indicator` | enum | `ILIconsultationrate`, `ARIconsultationrate`, `SARIrate`, `tests`, `detections`, `positivity`, `hospitaladmissions`, `ICUadmissions`, `ICUinpatients`, `deaths` |

### 6.3 ERVISS-profile extensions (documented, namespaced)

- **Wastewater** — `survtype = "wastewater"`, `indicator = "viral_load"` (unit `per_100k`), etc.
  ERVISS has no wastewater indicator; this is our WBE signal.
- **Derived analytics** — the aedseo outputs carried as data so the app stays presentation-only:
  `indicator = "status_level"` (0–4 / "very low"…"very high"), `"trend"` (increasing/stable/
  decreasing/inconclusive), `"band"`/`"phase"` (season/wave shading + since-week). Computed by the
  **country ETL**, not the app.

### 6.4 Future profiles (post-MVP)

Other surveillance domains register the same way — each is its own profile (dimensions + vocab +
indicators + validation) and, optionally, its own default panels/config: **HIV** (e.g. cascade /
case-based), **polio** (AFP surveillance), **AMR** (pathogen × antibiotic resistance), **Ebola /
VHF**, **yellow fever**, etc. The generic core, `DataSource`, auth, i18n, and config-driven UI are
unchanged; a new domain is a new profile module (and its data), not a fork. WHO/other standards
(e.g. GLASS for AMR, WHO AFP for polio) become the target vocabularies for those profiles, the way
ERVISS is for respiratory.

### 6.5 Versioning
- `schema_version` (semver) on the feed, plus the active `profile` name/version; for ERVISS, the
  pinned snapshot date is recorded in the contract doc.
- Long/tidy shape means new dimensions/indicators are new **rows**, not schema changes.

## 7. Interfaces (the load-bearing seams)

### 7.1 `DataSource`
```python
class DataSource(Protocol):
    def config_data(self) -> ConfigData: ...
    def query(self, *, pathogen=None, indicator=None, location=None,
              age=None, week_range=None) -> list[FeedRow]: ...
```
- `FileDataSource(data_dir)` — reads profile-format CSV/parquet/JSON; validates via Pydantic. **MVP.**
- `PostgresDataSource(dsn)` — same schema as a table/view. **Deferred.**
- `DHIS2DataSource(base_url, token)` — pulls aggregate/analytics data via the DHIS2 Web API and maps
  it into the active schema profile, for countries that run DHIS2 as their HMIS. **Deferred.**
- Selected by config; the API and UI are agnostic to which is behind it. Every source returns rows
  validated against the active schema profile (§6).

### 7.2 `AuthProvider`
```python
class AuthProvider(Protocol):
    def authenticate(self, credentials) -> Session | None: ...
    def current_user(self, request) -> User | None: ...
```
- `LocalAccountsProvider` — accounts from Connect env/secrets (email + argon2/bcrypt hash),
  signed-cookie sessions (itsdangerous/JWT, HTTP-only, Secure). No DB. **MVP.**
- `OIDCProvider` — Authorization Code + PKCE against a configured IdP; country gov SSO. **Deferred.**
- A `require_auth` dependency gates the SPA route and every `/api/*` route.

## 8. Server (FastAPI) — routes

| Route | Auth | Purpose |
|---|---|---|
| `GET /login`, `POST /login`, `POST /logout` | public / session | account login, session cookie |
| `GET /api/me` | required | current user (name/role for the UI) |
| `GET /api/config` | required | which pathogens/indicators/layout/branding/locales |
| `GET /api/data?…` | required | filtered feed rows (active schema profile) |
| `GET /api/locales/{lang}` | required | translation bundle |
| `GET /` and `/{path}` | required | serves the compiled SPA (`_ui/index.html` + assets) |

App factory: `create_app(config) -> FastAPI`, wiring the configured `DataSource` + `AuthProvider`.

## 9. Frontend — modularity & i18n

- **Config-driven rendering.** The SPA fetches `/api/config` and builds pathogen tabs, panels, and
  indicator charts from it. Adding/removing/reconfiguring a surveillance target = config + data,
  no code. Prototype panels/logic (Status/Trend tiles, range selector, season/wave band, EuroMOMO
  strip, Methods view) port into config-driven React components.
- **i18n.** react-i18next; `en` + `el`, default `en`; language switcher. UI strings in locale
  files; data-driven labels (pathogen names, source subtitles) and the methodology note are
  per-locale content supplied by the country.
- **Charts.** Chart.js, reused.

## 10. Packaging & reuse

```
health-signal/                     # generic library repo (monorepo) — /Users/wlu4/workspace/health-signal
├── frontend/                      # React + Vite (JS); vite build → ../src/health_signal/_ui
├── src/health_signal/
│   ├── app.py                     # create_app(config) -> FastAPI
│   ├── auth/  data/  api/         # AuthProvider, DataSource, routes
│   └── _ui/                       # compiled React bundle (package data, gitignored)
└── pyproject.toml                 # dist name "health-signal"; hatchling artifacts=["src/health_signal/_ui/**"]
```

Package: distribution name `health-signal`, import name `health_signal`.
- CI (Node present): `npm ci && npm run build` → `_ui/`, then `python -m build` → wheel with UI baked in.
- Consumers `pip install` the **wheel** (Node-free), `create_app(config)`, deploy to Connect. The
  same generic UI serves any country via runtime `/api/config` + `/api/data`.

```
greece-dashboard/                  # consumer repo (this repo's successor role)
├── pyproject.toml                 # depends on health-signal==X.Y.Z
├── app.py                         # from health_signal import create_app; create_app(load_config("dashboard.yaml"))
├── dashboard.yaml                 # pathogens, indicators, layout, branding, locales
├── locales/{en,el}.json
├── data/                          # ERVISS-shaped feed produced by the ETL
└── manifest / requirements        # rsconnect deploy to Posit Connect
```

## 11. Repos & branches

- **Generic repo** `health-signal` at `/Users/wlu4/workspace/health-signal` — the library; this spec
  lives here.
- **Greek repo** (`greece-public-health`): branch `feat/reusable-dashboard` (off `fix/source-label`)
  holds the migration — reshape the ETL output to the ERVISS contract, add `dashboard.yaml` +
  `locales/` + branding, depend on the library, update the Connect deploy.

## 12. Testing

- **Backend (pytest):** auth flows, `DataSource` implementations, API gating, and **contract
  validation** against a sample ERVISS feed.
- **Frontend (Vitest + React Testing Library):** config-driven rendering, i18n, panels.
- **ETL:** existing suite stays; add a test that the Greek ETL output validates against the contract.

## 13. Open questions / assumptions

- Whether the aedseo derivation should later be factored into a shared optional Python package the
  ETLs call (post-MVP).
- Exact per-country config schema (`dashboard.yaml`) fields — to be pinned in the implementation plan.
- Whether the generic repo is a true monorepo (frontend + package together) or split — assume
  monorepo for MVP.
