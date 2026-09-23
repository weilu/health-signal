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
| UI components & theming | **MUI (Material UI)** — canonical components + MUI styling APIs, **minimal custom CSS** (see §9); theme built at runtime from config (design tokens → `ThemeProvider` + CSS variables) for **per-government white-label** — no rebuild |
| Routing | **React Router** — every page has its own URL path (deep-linkable, shareable) |
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

- **Wastewater (WBE)** — ERVISS has no wastewater indicator, so this is an extension, but it is
  **anchored on the mature US CDC NWSS standard** re-projected into the tidy grid: wastewater viral
  load is simply another `indicator` on the same *location × period × pathogen* grain, differing
  from a clinical row only in `indicator`/`unit`. Indicators: `viral_load`, `viral_load_flowpop_norm`,
  `viral_load_mic_norm` (e.g. per-PMMoV), `wval`; units from the NWSS vocab (`copies/L wastewater`,
  `log10 copies/L`, `copies/g dry sludge`, or `index`/`z-score` for derived metrics); WW-specific
  fields (`location_level` sewershed/city/region, `population_served`, `normalization`, `lod`,
  `below_lod`, `flow_rate`, `quality_flag`) plus a **separate method/QC side-table** (PCR type,
  concentration/extraction method, recovery efficiency) so the tidy feed stays one-value-per-row.
  `pathogen` spelling matches ERVISS so WW and clinical feeds join on *location × yearweek ×
  pathogen*. (EU note: the recast UWWTD 2024/3019 mandates WBS + AMR reporting but publishes no open
  field schema yet — provisions apply from 2027 — so NWSS is the defensible anchor today.)
- **Derived analytics** — the Status/Trend outputs carried as data so the app stays presentation-only:
  `indicator = "status_level"` (0–4 / "very low"…"very high"), `"trend"` (increasing/stable/
  decreasing/inconclusive), `"band"`/`"phase"` (season/wave shading + since-week). Computed by the
  **country ETL**, not the app. Each derived row carries a **`method` field** (`aedseo` \| `mem` \| …)
  plus method-specific metadata (aedseo burden bands + disease threshold; MEM epidemic + intensity
  thresholds — which need not nest). **Methods can coexist**: the same indicator may have `aedseo`
  and `mem` rows, and config decides whether the UI shows one, the other, or a comparison toggle.
  This makes MEM-vs-aedseo configurable at the app **without any app logic** — it is a producer
  choice plus a display toggle. *(Producing MEM and a shared `StatusTrendEstimator` abstraction with
  pluggable aedseo/MEM estimators is an ETL / future-shared-analytics concern — see §13, post-MVP.)*

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
- **Routing (per-page URLs).** React Router gives every page its own path — e.g.
  `/covid-19/overview`, `/covid-19/clinical`, `/covid-19/wastewater`, `/methods` — so pages are
  deep-linkable and shareable. Paths are derived from config (pathogen × section). The FastAPI
  catch-all (`GET /{path}`, auth-gated) serves `index.html` for all of them; React Router takes over
  client-side.
- **Styling discipline — minimize custom CSS.** Use **canonical MUI components** and MUI's own
  styling configs (the `theme` object, `sx` prop, `styled()`, component `variants`/`defaultProps`)
  rather than bespoke stylesheets. The prototype's hand-rolled `styles.css` is **not** carried over —
  its look is reproduced through MUI's system. Custom CSS is a last resort (a genuinely un-MUI layout
  need), kept minimal and justified. This keeps the library consistent, themeable, and low-maintenance.
- **Theming (per-government white-label).** MUI `ThemeProvider` + CSS variables built at runtime
  from the config branding block (palette, logo, favicon, typography, light/dark). A government
  restyles via `dashboard.yaml` + assets — no rebuild, same UI bundle. Because styling flows through
  the theme (not ad-hoc CSS), a theme swap restyles the whole app coherently.
- **Method display.** When a config panel has multiple analytic methods in the feed (e.g. aedseo +
  MEM), the UI can show a method toggle / side-by-side comparison; labels and level vocabulary come
  from the method metadata + locales.
- **i18n (layered locales).** react-i18next; `en` + `el`, default `en`; language switcher. The
  **library ships the base UI-string catalog** (generic chrome: nav, Status/Trend, "as of", login,
  buttons — en/el, extensible to more languages). The **consumer supplies only country-specific and
  data-driven strings** (pathogen display names, source subtitles, methodology text) and may override
  library defaults. `/api/locales/{lang}` **deep-merges** library base + country overrides (country
  wins) so no country re-translates the generic chrome.
- **Charts.** Chart.js, reused.

## 10. Packaging & reuse

```
health-signal/                     # generic library repo (monorepo) — /Users/wlu4/workspace/health-signal
├── frontend/                      # React + Vite (JS); vite build → ../src/health_signal/_ui
├── src/health_signal/
│   ├── app.py                     # create_app(config) -> FastAPI
│   ├── auth/  data/  api/         # AuthProvider, DataSource, routes
│   ├── locales/{en,el}.json       # BASE UI-string catalog (generic chrome); extensible
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
├── locales/{en,el}.json           # country OVERRIDES + data-driven strings (merged over library base)
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

**Strategy — favor end-to-end and integration tests first (outside-in TDD).** Because the app is
mostly config-driven presentation plus a few boundaries (auth, data source), the highest-confidence
tests exercise whole flows through real seams; write those first and drop to unit tests for focused
logic (schema validation, merge rules, parsing). Concrete per-phase test lists live in the
implementation plan; this section sets the shape.

**Data governance — synthetic fixtures only (public repo).** `health-signal` is **public**, so all
test fixtures, sample feeds, example configs, and docs use **synthetic dummy data only**. **No
confidential or pre-publication Greece pilot data** (EODY clinical figures, Psyttalia wastewater,
unpublished analyses, real facility rosters) may appear in this repo — that data lives only in the
private consumer repo. Fixtures are hand-crafted synthetic ERVISS/NWSS-shaped rows with obviously
fake locations/values; any realistic sample is drawn only from the **openly-licensed** ERVISS/NWSS
public datasets, never from the pilot's private feed.

- **E2E (highest priority):** drive the running FastAPI app end-to-end — unauthenticated request is
  blocked → login → `/api/config` + `/api/data` → a page renders the expected panels; per-page URLs
  are deep-linkable behind auth; language switch swaps strings. Tooling: Playwright (or FastAPI
  `TestClient` + a headless frontend harness) against the assembled app.
- **Integration:** API routes with a real `DataSource` (`FileDataSource` over a sample feed) and a
  real `AuthProvider`; **contract validation** of a sample feed against the active schema profile;
  the locale deep-merge (library base + country overrides). Prefer these over mocking the seams.
- **Unit (focused logic only):** Pydantic profile validation, config parsing, locale merge, small
  frontend helpers.
- **Frontend:** Vitest + React Testing Library for component/config-driven rendering where an E2E is
  overkill.
- **ETL (consumer side):** existing suite stays; add a test that the Greek ETL output validates
  against the contract.

## 13. Delivery process (staged PRs)

Work proceeds in **stages, one GitHub PR per stage**, each following this lifecycle:

1. Open the PR → **GitHub Copilot review** → iterate until Copilot has no substantive findings
   (the same loop already run on `greece-public-health` PR #2).
2. **User review** → iterate.
3. **Merge.**

**Size cap: ≤ 800 lines of changed code per PR** — beyond that, complexity outstrips reviewable
understanding. If a stage would exceed the cap, split it further. Generated/compiled artifacts
(the Vite `_ui/` bundle, lockfiles) and vendored files do **not** count toward the cap. Each stage
should be independently reviewable and, where practical, leave the app in a working state.

The implementation plan (writing-plans) decomposes the build into stages that each satisfy this
cap and lifecycle.

**Repo:** `weilu/health-signal` on GitHub — **public**, **MIT** licensed. The staged-PR flow runs here.

## 14. Open questions / assumptions

- A shared Status/Trend analytics package (post-MVP): a `StatusTrendEstimator` interface with
  pluggable **aedseo** and **MEM** estimators, so ETLs produce comparable derived rows without each
  reimplementing a method. The app already consumes the `method`-tagged output (§6.3), so this is a
  producer-side addition, not an app change.
- Exact per-country config schema (`dashboard.yaml`) fields — to be pinned in the implementation plan.
- Whether the generic repo is a true monorepo (frontend + package together) or split — assume
  monorepo for MVP.
