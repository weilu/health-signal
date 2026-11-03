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
first (ECDC/WHO **ERVISS** clinical indicators + **PHES-ODM** wastewater); further domains
(e.g. AMR, vaccine-preventable diseases) are added as configuration plus a schema profile, not a
fork. It is packaged as a Python library that a country's own repository configures and deploys
(for example, to Posit Connect, where it runs below the content's own path, `/content/<guid>/`).

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

### Data feeds and profiles

Each feed in `data.feeds` names a **profile**: the columns, indicators, units and dimension values its CSVs
must use, checked when the app starts. Two are built in: `erviss` (ECDC/WHO ERVISS respiratory indicators,
vocabulary pinned to its published dataset) and `phes_odm` (PHES-ODM v3 wastewater measures).

A country whose own series mostly fit a built-in profile can **extend** it in config rather than in the
library. Extensions are additive, so data valid under the base stays valid. They may add indicators, units,
dimension values, qualities, count and censored units, pathogen-specific indicators and denominators; they
may not add a dimension, extend the shared pathogen list, extend another extension, or reuse a built-in's name.
An extended profile reports its version as `<base version>+<name>`.

```yaml
profiles:
  erviss_gr:
    extends: erviss
    units: [per_1000_admissions]
    dimension_vocab: { survtype: [private hospital] }
    denominators:   # a rate in this unit is modelled against admissions, not as a constant exposure
      - { rate: SARIrate, unit: per_1000_admissions, denominator: hospitaladmissions, per: 1000 }
data:
  feeds:
    - { id: clinical, profile: erviss_gr, dir: data/clinical, assessments: data/clinical/assessed }
```

`examples/greece.dashboard.yaml` uses this for EODY's series: rates per 1,000 admissions and consultations,
the private-hospital network, and SARI's paediatric group, which EODY defines by hospital rather than age band.

### Deployment text (i18n)

The library ships its own interface text in English and Greek, including names for everything it defines: the
pathogens targets are keyed by, and the indicators, units and named dimension values of its built-in profiles.
A deployment can offer another language with a file of its own; whatever that file leaves out reads in English.
A panel is therefore named by default from its query: its indicator, plus the values that set it apart from the
page's other panels of that indicator (e.g. "Test positivity · SARI virological"), or "by <dimension>" for a split
panel. A deployment supplies the rest: its page and location names, labels for any units or dimension values its
profile extensions add, and, optionally, its own panel names. Both use the same keys, so a deployment can also
reword any library text, or a panel's default name, by setting its key. Config carries only ids, each
labelled by convention (`pages.<page id>`, `targets.<target id>`, a location option's `label_key`, `unit.<unit>`,
`dimensions.<dimension>.<value>` for a split chart's lines, and `panels.<panel id>` to replace a panel's default name).

A time-series panel can set `y_scale: log` for values spanning orders of magnitude, such as wastewater loads.
Weeks whose value is zero (e.g. a below-detection stand-in) then show as a gap with a mark at the axis floor.

A chart's title also names the tab's pathogen and the selected location ("Hospital admissions · COVID-19 (Attica)"),
so it keeps its context once the tabs scroll out of view; so do the overview's cards ("Key signals · COVID-19 (Attica)"). A deployment can add a subtitle under it with
`subtitles.<panel id>`, which may use `{{pathogen}}` and `{{location}}`. More specific keys win where present:
`subtitles.<target id>.<panel id>` for one target, and a `_<location>` suffix for one location
(`subtitles.hospital_admissions_Attica`). Put one `<language>.json` per offered language in a directory and point
`site.locales_dir` at it:

```yaml
site:
  locales: [en, el]
  locales_dir: locales   # locales/en.json, locales/el.json
```

```json
{ "panels": { "hospital_admissions": "Εισαγωγές σε νοσοκομείο" }, "unit": { "per_1000_admissions": "ανά 1.000 εισαγωγές" } }
```

After sign-in, the app fetches the file for the current language and merges it over the library's text. The
deployment's text wins, so it can also reword a library string. A missing or malformed file for an offered
language stops the app at startup; a label with no text shows its id. The Greece example's files are in
`examples/locales/`.

### Methodology page

The **Methodology** page explains to readers how the dashboard reaches what it shows. A deployment writes it in
Markdown, one `<language>.md` per offered language in a directory named by `site.methodology_dir`; without one, the
page is the library's general text for its method. Placeholders are filled from the deployment's own settings, so the
page can't drift from them:

- values, inline: `{{surveillance.year_start_week}}`, `{{surveillance.year_end_week}}`, `{{analytics.min_seasons}}`,
  `{{analytics.aedseo.wave_end.steps_with_decrease}}`, `{{analytics.aedseo.wave_end.burden_level_decrease}}`,
  `{{phase.max_dip}}`, `{{phase.max_missing}}`, `{{method.build}}` (the aedseo build behind the current tables),
  `{{censored.qualities}}` and `{{censored.feeds}}` (the stand-in values fitted as gaps, and where), and
  the method's parameters `{{method.n_peak}}`, `{{method.conf_levels}}`, `{{method.decay_factor}}`,
  `{{method.burden_family}}`, `{{method.onset_family}}`, `{{method.window_weeks}}`, `{{method.interval_percent}}`;
- tables, each on a line of its own: `{{> streams}}` (each pathogen and location's two streams, named as their panels
  are), `{{> indicator_models}}` (how each kind of indicator enters the method), `{{> phase_patterns}}` (season or
  waves), `{{> levels}}` (the levels and their colours);
- `{{> method}}`: the library's general method text, in the reader's language (English where the library has none);
  or one section of it at a time, so a deployment can put its own reasoning where it belongs: `{{> method.overview}}`,
  `{{> method.status}}`, `{{> method.trend}}`, `{{> method.seasons}}` (ending with the streams table),
  `{{> method.waves}}`, `{{> method.indicators}}`, `{{> method.references}}`.

**One page per method.** The page shows the method selected in the header. A deployment grading with several methods
writes `methodology_dir/<method>/<language>.md` for each (e.g. `aedseo/el.md`, `mem/el.md`); one without a folder
shows the library's text for it, and a single-method deployment's `methodology_dir/<language>.md` is read as aedseo's.
Placeholders mean the page's method: on a MEM page `{{> method}}` is MEM's text, and `{{method.seasons}}`,
`{{method.season_start_week}}`, `{{method.season_end_week}}`, `{{method.epidemic_param}}` and
`{{method.intensity_levels}}` its settings; `{{> streams}}`, `{{> indicator_models}}` and `{{> phase_patterns}}`
are aedseo's alone.

The page is CommonMark with tables and `$…$` / `$$…$$` maths; raw HTML isn't rendered. Inside maths a value
placeholder becomes the bare value and LaTeX's own double braces are left alone; inside a fenced code block
placeholders are shown as written. Its `##` and `###` headings
build its contents list. An unknown placeholder, a table placeholder sharing its line, or a missing file for an
offered language stops the app at startup. The Greece example's pages are in `examples/methodology/`.

### Pages of the deployment's own

A page the library's panels can't express (a forecast, a bespoke analysis) can be written by the deployment as a web
page of its own and shown in its tab, under the dashboard's header and tabs:

```yaml
site:
  embeds_dir: embeds          # served under /embeds, behind the sign-in like everything else
targets:
  - id: SARS-CoV-2
    pages:
      - { id: predictive, embed: forecast/index.html }   # a page embeds or has panels, not both
```

Every file under `embeds_dir` is served, so the page can load its own scripts and data from beside it. Its address
carries the reader's language and the header's filters, `?lang=el&location=Attica&from=2025-W45&to=2026-W44` (a
filter the dashboard doesn't have is left out), and it reloads when they change. So the frame takes the page's height
rather than scrolling inside the tab, the page posts it: `parent.postMessage({ type: "health-signal:height", height:
document.documentElement.scrollHeight }, "*")`. A missing embed file stops the app at startup.

### Status, Trend and phase (`health-signal assess`)

The dashboard shows Status and Trend tiles, threshold bands and season or wave phases from tables it
loads at startup (spec §6.3). `health-signal assess` writes them from the feeds with SSI's
[aedseo](https://cran.r-project.org/package=aedseo), grading every single-series panel at every location
week by week, each week from the data available up to it. It needs R, which the app itself doesn't:

```bash
# once: R (https://cran.r-project.org) with aedseo, and the analytics extra. Until ssi-dk/aedseo#114 reaches
# CRAN, aedseo from this development commit: CRAN's 1.1.0 can't place a wave after a reporting gap
Rscript -e 'install.packages("remotes"); remotes::install_github("ssi-dk/aedseo@f65ddf153060773f9bac4759a458b2ff76df6027")'
Rscript -e 'install.packages("mem")'          # only if analytics.methods includes mem
pip install "health-signal[analytics]"        # or: uv sync --extra analytics

health-signal assess --config dashboard.yaml --full --jobs 8   # first run: every week of history
health-signal assess --config dashboard.yaml                   # then after each feed refresh: new weeks only
```

It writes each feed's `assessments` dir and `data.phases` / `data.phase_streams`, and records the
settings it used in `assessed_with.csv`: when `surveillance.year_start_week`, `analytics`, a feed profile's
modelling rules (count units, censored qualities, denominators) or the aedseo build change, it stops and asks
for `--full`. Run `--full` too after a feed revises past weeks. It
checkpoints each series as it finishes (in `.assess-checkpoint/` beside the tables), so an interrupted run
resumes where it stopped when run again without `--full`; the served tables change only when a run completes,
all of them together. It runs at low priority, so `--jobs` up to the core count leaves the machine usable.
A phase is marked provisional (an optional `provisional` column) when either of its streams' grades is, so
the season tile shows the same chip as the status tile.
Phase tables may come from another producer, so `assess` writes them only while `analytics.phase_streams`
lists streams: to stop showing its phases, remove `data.phases` and `data.phase_streams` too. The
policy settings live under `analytics:` (see the example config); countries may also write the tables
themselves in the same format, with or without aedseo.

**More than one method.** `analytics.methods` lists the methods `assess` grades with, `[aedseo]` by default; the first
is the one the dashboard shows by default. The other is the **Moving Epidemic Method** ([mem](https://cran.r-project.org/package=mem),
Vega et al.), as ERVISS uses it for ILI/ARI: each season's epidemic and intensity thresholds come from the
`analytics.mem.seasons` (default 5) complete seasons before it, in MEM's own window starting at
`analytics.mem.season_start_week` (default 40), and stay fixed for the season. Its levels are baseline, low, medium,
high and very high; its trend compares each week with the last, and isn't assessed below the epidemic threshold.
MEM assumes one epidemic a season and sets no phases, so it leaves out series graded in waves. Each method grades
every single-series panel unless it lists some, as `"<target>/<page>/<panel>"`:

```yaml
analytics:
  methods: [aedseo, mem]
  mem: { season_start_week: 25, seasons: 5, panels: [Influenza/clinical/ili_rate] }
```

`assess --full --method mem` recomputes one method's tables and keeps the others'.

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
directory: put that profile's CSV files in it (`data/clinical` for ERVISS-shaped rows, read with the
example's `erviss_gr` extension; `data/wastewater` for PHES-ODM rows). The example also reads the tables
`health-signal assess` writes: its `assessments` dirs and phase files must exist, so create them empty (header
only) until the first run. Left empty, the dashboard starts and every panel says there's no data. Auth needs a
secret and at least one account (email → argon2 hash):

```bash
mkdir -p data/clinical/assessed data/wastewater/assessed
echo "location,pathogen,period,method,phase" > data/phase.csv
echo "location,pathogen,method,role,feed,series" > data/phase_streams.csv
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
