# health-signal

[![CI](https://github.com/weilu/health-signal/actions/workflows/ci.yml/badge.svg)](https://github.com/weilu/health-signal/actions/workflows/ci.yml)

A reusable, configuration-driven **public-health surveillance dashboard** library. It presents
integrated surveillance data — clinical indicators alongside complementary signals such as
wastewater — as status, trend, and seasonal/wave phase, behind app-managed authentication. It is
**modular**: which surveillance targets (pathogens, indicators, whole domains) appear is driven
entirely by configuration and pluggable **schema profiles**, so it is not tied to any single
disease area. It is designed to be deployed by any country or agency with its own data, branding,
and languages.

`health-signal` is a [FastAPI](https://fastapi.tiangolo.com/) application that serves a React
([MUI](https://mui.com/)) single-page app plus a gated JSON API. It ships a respiratory profile
first (ECDC/WHO **ERVISS** clinical indicators + US CDC **NWSS** wastewater); further domains
(e.g. AMR, vaccine-preventable diseases) are added as configuration plus a schema profile, not a
fork. It is packaged as a Python library that a country's own repository configures and deploys
(for example, to Posit Connect).

**Audience:** public-health agencies, epidemiologists, and the teams building surveillance
dashboards for them.

> **Status:** early development; the first functional release is in progress.

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 22+ — only to build the frontend from source. Installing the published wheel does **not**
  require Node (the compiled UI ships inside it).

### Installation

From PyPI (once published):

```bash
pip install health-signal
```

Directly from GitHub — source install, which builds the bundled frontend, so **Node.js is required**:

```bash
pip install "git+https://github.com/weilu/health-signal.git"
```

> Released wheels bundle the pre-compiled frontend and install **without** Node; only the source
> install above needs it.

### Usage

```python
from health_signal import create_app, load_config

app = create_app(load_config("dashboard.yaml"))
```

A consuming repository supplies a `dashboard.yaml` (which pathogens/indicators, layout, branding,
locales), translation overrides, and a data feed adhering to the contract. See
[`examples/greece.dashboard.yaml`](examples/greece.dashboard.yaml) for a worked example —
`branding.theme` is a [MUI theme-options](https://mui.com/material-ui/customization/theming/) object
merged over the library's neutral default, so a government restyles with no rebuild.

### Status, Trend and phase (`health-signal assess`)

The dashboard shows Status and Trend tiles, threshold bands and season or wave phases from tables it
loads at startup (spec §6.3). `health-signal assess` writes them from the feeds with SSI's
[aedseo](https://cran.r-project.org/package=aedseo), grading every single-series panel at every location
week by week, each week from the data available up to it. It needs R, which the app itself doesn't:

```bash
# once: R (https://cran.r-project.org) with aedseo, and the analytics extra
Rscript -e 'install.packages("aedseo")'
pip install "health-signal[analytics]"        # or: uv sync --extra analytics

health-signal assess --config dashboard.yaml --full --jobs 8   # first run: every week of history
health-signal assess --config dashboard.yaml                   # then after each feed refresh: new weeks only
```

It writes each feed's `assessments` dir and `data.phases` / `data.phase_streams`, and records the
settings it used in `assessed_with.csv`: when `surveillance.year_start_week`, `analytics` or the aedseo
version change, it stops and asks for `--full`. Run `--full` too after a feed revises past weeks. It saves
each series as it finishes, so an interrupted run resumes where it stopped when run again without `--full`,
and it runs at low priority so `--jobs` up to the core count leaves the machine usable. The
policy settings live under `analytics:` (see the example config); countries may also write the tables
themselves in the same format, with or without aedseo.

### Authentication & access

The dashboard is gated by an app-managed local auth provider (fastapi-login + argon2, no database),
configured with two environment variables:

- `HEALTH_SIGNAL_SECRET_KEY` — signs the session cookie. **Must be at least 32 bytes** (a weak value
  can be brute-forced offline to forge sessions). Generate one with
  `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- `HEALTH_SIGNAL_ACCOUNTS` — a JSON object mapping each email to its argon2 hash.

Access is **default-locked**: `public_paths` (in `dashboard.yaml`) lists the SPA **pages** that
render without login. An unauthenticated request to any other page is redirected to `/login`.

| `public_paths` | Public SPA pages |
| --- | --- |
| `[]` (default) | None — every page requires login |
| `["/about"]` | `/about` and its sub-paths |
| `["/"]` | All pages |

`public_paths` controls **page (HTML) access only** — it does not open API endpoints. Gated routes
such as `/api/me` stay authenticated even under `["/"]`, and the always-public routes — the OpenAPI
docs (`/docs`, `/redoc`, `/openapi.json`) and `/healthz`, `/login`, `/logout` — are reachable
regardless. Entries must be non-empty, and `/` is the only match-all value.

`/login` runs an intentionally expensive argon2 verification on every attempt, so deploy it behind a
proxy (e.g. Posit Connect or a reverse proxy) that rate-limits `/login` and returns HTTP 429 when
exceeded — the library does not throttle in-process.

### Development

This project uses [uv](https://docs.astral.sh/uv/) for the development workflow (the build backend
is still hatchling, so consumers install with plain `pip` as above):

```bash
uv sync          # create the venv and install the project + dev dependencies
uv run pytest    # run the tests
```

### Running it locally

`uv sync` installs the project editable, which does **not** build the frontend, so build it once
(needs Node):

```bash
npm --prefix frontend ci && npm --prefix frontend run build
```

`npm ci` installs exactly the versions pinned in `frontend/package-lock.json`. To add or upgrade a
frontend dependency, use `npm --prefix frontend install <pkg>` instead and commit the updated lockfile.

Then wrap `create_app` in a module and serve it. Each feed in `data.feeds` must be an existing
directory: put that profile's CSV files in it (`data/clinical` for ERVISS rows, `data/wastewater` for
PHES-ODM rows); left empty, the dashboard starts and every panel says there's no data. Auth needs a
secret and at least one account (email → argon2 hash):

```bash
mkdir -p data/clinical data/wastewater
export HEALTH_SIGNAL_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export HEALTH_SIGNAL_ACCOUNTS=$(uv run python -c "import json; from argon2 import PasswordHasher as P; print(json.dumps({'you@example.org': P().hash('change-me')}))")

cat > app.py <<'PY'
from health_signal import create_app, load_config
app = create_app(load_config("examples/greece.dashboard.yaml"))
PY

uv run uvicorn app:app --port 8000   # http://127.0.0.1:8000  (login: you@example.org / change-me)
```

For frontend hot-reload, skip the build and run `npm --prefix frontend run dev` alongside the server
— Vite proxies `/api`, `/login`, and `/logout` to `:8000`.

## Contact

Wei Lu — <wlu4@worldbank.org>

## License

This project is licensed under the MIT License together with the World Bank IGO Rider.
The Rider is purely procedural: it reserves all privileges and immunities enjoyed by the
World Bank, without adding restrictions to the MIT permissions. Please review both files
before using, distributing or contributing.

See [LICENSE](LICENSE) and [WB-IGO-RIDER.md](WB-IGO-RIDER.md).
