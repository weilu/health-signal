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
