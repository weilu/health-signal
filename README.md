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
- Node.js 20+ — only to build the frontend from source. Installing the published wheel does **not**
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
locales), translation overrides, and a data feed adhering to the contract.

### Authentication & access

The dashboard is gated by an app-managed local auth provider (fastapi-login + argon2, no database),
configured with two environment variables:

- `HEALTH_SIGNAL_SECRET_KEY` — signs the session cookie. **Must be at least 32 bytes** (a weak value
  can be brute-forced offline to forge sessions). Generate one with
  `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- `HEALTH_SIGNAL_ACCOUNTS` — a JSON object mapping each email to its argon2 hash.

Access is **default-locked**: unless a page's path prefix is listed in `public_paths` (in
`dashboard.yaml`), unauthenticated requests to it are redirected to `/login`, and its data
endpoints (`/api/*`) return `401` — locked content is never served without authentication.

| `public_paths` | Effect |
| --- | --- |
| `[]` (default) | Whole site locked — everything behind auth |
| `["/about"]` | Only that prefix (and its sub-paths) public |
| `["/"]` | Whole site public |

`/healthz`, `/login`, and `/logout` are always reachable (operational endpoints). Entries must be
non-empty, and `/` is the only match-all value.

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

## Contact

Wei Lu — <wlu4@worldbank.org>

## License

This project is licensed under the MIT License together with the World Bank IGO Rider.
The Rider is purely procedural: it reserves all privileges and immunities enjoyed by the
World Bank, without adding restrictions to the MIT permissions. Please review both files
before using, distributing or contributing.

See [LICENSE](LICENSE) and [WB-IGO-RIDER.md](WB-IGO-RIDER.md).
