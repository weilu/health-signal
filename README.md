# health-signal

A reusable, configuration-driven **respiratory-surveillance dashboard** library. It presents
integrated public-health surveillance data — clinical indicators alongside wastewater signals —
as status, trend, and seasonal onset/wave phase, behind app-managed authentication. It is designed
to be deployed by any country or agency with its own data, branding, and languages.

`health-signal` is a [FastAPI](https://fastapi.tiangolo.com/) application that serves a React
([MUI](https://mui.com/)) single-page app plus a gated JSON API. It consumes a standards-based data
feed (ECDC/WHO **ERVISS** for clinical indicators; US CDC **NWSS** for wastewater) and is packaged
as a Python library that a country's own repository configures and deploys (for example, to Posit
Connect).

**Audience:** public-health agencies, epidemiologists, and the teams building surveillance
dashboards for them.

> **Status:** early development. The architecture and data contract are documented under
> [`docs/specs`](docs/specs); the first functional release is in progress.

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
locales), translation overrides, and a data feed adhering to the contract. See
[`docs/specs`](docs/specs) for the configuration schema and data contract.

## Documentation

Design and data-contract documentation lives in [`docs/`](docs). A hosted documentation site will
follow.

## Contact

Wei Lu — <wlu4@worldbank.org>

## License

This project is licensed under the MIT License together with the World Bank IGO Rider.
The Rider is purely procedural: it reserves all privileges and immunities enjoyed by the
World Bank, without adding restrictions to the MIT permissions. Please review both files
before using, distributing or contributing.

See [LICENSE](LICENSE) and [WB-IGO-RIDER.md](WB-IGO-RIDER.md).
