# Reusable Public-Health Surveillance Dashboard — Design

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

**Scope — not respiratory-specific.** The pilot and the MVP's first schema profile are respiratory
(ERVISS clinical + PHES-ODM wastewater), but the dashboard is a **general integrated public-health
surveillance** platform. The data contract, auth, i18n, theming, and config-driven UI are
**domain-agnostic**; other surveillance domains (AMR, vaccine-preventable diseases, HIV, polio, …)
plug in as configuration plus a schema profile, without a fork (see §6.4). Nothing in the design is
respiratory-specific — "respiratory" is the first profile, not a boundary.

## 2. Goals & non-goals

### Goals (MVP)

- One generic, config-driven dashboard reusable across countries.
- App-managed authentication gating all content, no dependency beyond Posit Connect.
- A documented, versioned ETL→app data contract based on the EU/WHO ERVISS model.
- A pluggable data connector (files first; Postgres later) and a pluggable auth provider
  (local accounts first; OIDC/SAML later).
- Migrate the Greek dashboard onto the library.

### Non-goals (explicitly deferred)

- Postgres connector, **DHIS2 connector**, **MCP server** (AI-agent access — OpenAPI covers baseline
  AI access, see §7.3), OIDC/SAML SSO, in-app aedseo analytics, roles/permissions beyond
  authenticated-or-not, data write-back, single-deployment multi-tenancy.
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

```text
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
| Frontend | React 19 + Vite, **plain JavaScript (JSX)**, no TypeScript |
| UI components & theming | **MUI (Material UI)** — canonical components + MUI styling APIs, **minimal custom CSS** (see §9); theme built at runtime from config (design tokens → `ThemeProvider` + CSS variables) for **per-government white-label** — no rebuild |
| Routing | **React Router** — every page has its own URL path (deep-linkable, shareable) |
| i18n | react-i18next; `en` + `el`; default `en` |
| Charts | Chart.js (reused from the prototype) |
| API docs | FastAPI-generated **OpenAPI** — Swagger UI (`/docs`) + ReDoc (`/redoc`) + `/openapi.json`, auth-gated; optional static reference via Redoc (`@redocly/cli`) in CI |
| Contract validation | Pydantic models declare the contract (profile vocab + `FeedRow`, the single source of truth); pandas applies the profile rules vectorized when loading |
| Packaging | hatchling; Vite build baked into the wheel as package data |
| Auth | Pluggable `AuthProvider` — **not hand-rolled**: local = `fastapi-login` + argon2 (DB-free config accounts, MVP); SSO = **Authlib** OIDC RP (deferred). Per-page access policy (default locked, opt-in public) |
| Data (MVP) | CSV files in ERVISS format via `FileDataSource` (pandas) |

## 6. Data contract (ETL ↔ app boundary)

The contract is a **domain-agnostic tidy long-format spine** plus a pluggable **schema profile**.
The spine is the same for every surveillance domain; a profile defines the domain-specific
dimensions, controlled vocabularies, indicators, and units. **ERVISS (respiratory) is the first
profile and the MVP; PHES-ODM wastewater (§6.3) the second** — other domains (HIV, polio, AMR, Ebola, yellow fever, …) register as
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
| `quality` | string, optional | a quality indicator from the profile's vocabulary (e.g. PHES-ODM `beLOD`, below the limit of detection); annotates a value, so it never splits a series |

A profile is a Pydantic-backed declaration: `dimensions` (names + controlled vocabularies),
`indicators`, `units`, `period` granularity, and validation rules. New rows — not schema changes —
add pathogens/strata/indicators within a profile.

**Pathogens.** One shared registry of canonical pathogen keys (`SARS-CoV-2`, `Influenza`, `RSV`;
extended for other domains, e.g. polio or HIV). The keys use ERVISS's spellings: ERVISS is the EU
standard and its published data already uses them, so an ERVISS feed needs no mapping, and display
names come from i18n (`pathogens.SARS-CoV-2`). Every profile's `pathogen` dimension, the pathogen
phase table (§6.3) and target ids validate against it. (WHO's ICD-11 has infectious-agent extension
codes, e.g. `XN109` for SARS-CoV-2; nothing here uses them, so they are not carried.)

**Targets, pages and paths.** A target is a surveillance subject, so its `id` is a pathogen registry
key; there is no separate pathogen field. A panel that sets `pathogen` in its query must equal its
target's id, so a COVID tab can't show influenza. Cross-pathogen views are pages, not targets. Page
paths are derived, not configured: `/<lower-cased target id>/<page id>` (e.g. `/sars-cov-2/clinical`),
with page ids URL-safe (`[a-z0-9_-]+`); target ids and page ids being unique makes paths unique, and
no registry key may slugify to an app route (`config`, `api`, `login`, …). The server sends the
derived `path` and `label_key` to the client as computed fields. (Non-organism subjects such as AMR,
which spans organisms × antibiotics, are decided when an AMR profile arrives.)

**Feeds.** A dashboard serves one or more feeds, each a directory of one profile's rows:
`data.feeds: [{id, profile, dir, assessments?}]` (required; ids unique; e.g. `clinical`/`erviss` and
`wastewater`/`phes_odm`), plus an optional `data.phases` file (§6.3). There is no default feed:
every panel names the one it reads.

Pages declare **panels** in config — a `type` (default `timeseries`; later kinds such as status tiles or
stacked bars are stated explicitly), a `query` (a required `feed`, an `indicator`
plus a `dimensions: {name: value}` map of profile-dimension filters, which should match one row per
series per week) and an optional `series_by` dimension that splits it into lines. The map keeps the
config shape profile-agnostic: a wastewater profile's dimensions need no new fields. Each panel is
validated at load against its feed's profile, so a typo fails before the app serves.
**Location and the date range are dashboard-wide filters, not panel settings:**
`filters.location` lists the selectable locations and a default, and every panel is queried for the
selected one; a panel with no rows for it shows a "no data for {location}" message rather than being
hidden or falling back to another level. `filters.date_range` (optional) sets `default_weeks` (a count
or `"all"`, default 52). The yearly presets begin at `surveillance.year_start_week` (1–52, default 1;
e.g. 21 for a W21→W20 respiratory year), the dashboard's surveillance year, which the analytics
component (§6.3.1) also uses as its season boundary, so the two can't disagree. The range control offers "Last N weeks", "All history", one
preset per year and custom from/to weeks, all bounded by `GET /api/periods` (the first and latest
week across all feeds). Defaults count back from the latest week in the data, not from today, so a lagging feed
doesn't draw empty weeks; the header's Reporting week shows the lag. Every chart's axis spans the
selected range, so panels on a page line up.

### 6.2 ERVISS profile (respiratory — MVP)

The ECDC/WHO-Europe *European Respiratory Virus Surveillance Summary* public data model (repo
`EU-ECDC/Respiratory_viruses_weekly_data`, EUPL-1.2), pinned to the **2026-W40** snapshot. Its
`dimensions` and indicator vocabulary, taken from the published files:

| Field | Type | Notes / allowed values |
|---|---|---|
| `survtype` | enum | `primary care sentinel` \| `primary care syndromic` \| `non-sentinel` \| `SARI syndromic` \| `SARI virological` |
| `pathogen` | enum, nullable | `Influenza` \| `RSV` \| `SARS-CoV-2` (null for pure ILI/ARI syndromic) |
| `pathogentype` | enum, nullable | `Influenza`, `Influenza A`, `Influenza B`, `Influenza untyped`, `RSV`, `RSV untyped`, `RSV-A`, `RSV-B`, `SARS-CoV-2` |
| `pathogensubtype` | enum, nullable | `A (unknown)`, `A(H1)pdm09`, `A(H3)`, `B (unknown)`, `B/Vic`, `B/Yam`, `Influenza untyped`, `NA` *(a literal ERVISS value)*, `RSV`, `SARS-CoV-2`, `total` |
| `age` | enum | `0-4` \| `5-14` \| `15-64` \| `65+` \| `total` \| `unk` |
| `indicator` | enum | `ILIconsultationrate`, `ARIconsultationrate`, `SARIrate`, `tests`, `detections`, `positivity`, `hospitaladmissions`, `ICUadmissions`, `ICUinpatients`, `deaths` |

ERVISS's published files use `countryname`/`yearweek` and carry no `unit`; mapping them onto the
spine (`location`, `period`, `unit`) is the producing ETL's job. Unit vocabulary includes ERVISS's
reporting exceptions: ILI/ARI rates are per 100 000 population except per 100 consultations (Cyprus,
Luxembourg, Malta) and per 100 000 consultations (Finland), per the ERVISS README. ERVISS's variant
and sequencing files have a different shape and belong to the variant track.

#### 6.2.1 Extending a profile in config

A country's own surveillance rarely matches a published vocabulary exactly: Greece's EODY reports a SARI
rate per 1,000 hospital admissions (ERVISS's `SARIrate` is per 100k population) and positivity from a
private-hospital network ERVISS has no surveillance type for. Rather than adding those to a built-in
profile — which stays pinned to its published vocabulary — a dashboard declares a named, additive
extension and its feeds use it:

```yaml
profiles:
  erviss_gr:
    extends: erviss
    units: [per_1000_admissions]
    dimension_vocab: {survtype: [private hospital]}
    denominators:
      - {indicator: SARIrate, unit: per_1000_admissions, denominator: hospitaladmissions, per: 1000}
data:
  feeds:
    - {id: clinical, profile: erviss_gr, dir: data/clinical}
```

An extension may add indicators, units, dimension values, count units, censored qualities,
pathogen-specific indicators and denominators; it can't remove or rename anything (data valid under
the base stays valid), add a dimension key (that changes how series are identified), or extend the
`pathogen` vocabulary (the shared registry, §6.1). It must extend a built-in profile and may not take a
built-in's name; its version reads `<base version>+<name>`. Denominators may be scoped to a unit, so the
admissions-based SARI rate is modelled against admissions while ERVISS's per-population one isn't.
Everything validates against the extended profile exactly as against a built-in: feed rows, panel
queries, assessments and phase streams.

### 6.3 Extensions and derived analytics

- **Wastewater (WBE) — the `phes_odm` profile.** ERVISS has no wastewater indicator, so this is its
  own profile, **anchored on PHES-ODM v3** (Public Health Environmental Surveillance Open Data Model,
  CC-BY-4.0): the EU's de facto standard, adopted and adapted by the JRC's EU Sewage Sentinel System
  (EU Wastewater Observatory) and used by PHAC Canada. EU-WISH publishes no data model of its own, and
  the recast UWWTD 2024/3019 has no open field schema yet (provisions apply from 2027). ODM is long,
  one measurement per row, so it maps onto the spine almost directly:

  | Spine | `phes_odm` | Example |
  |---|---|---|
  | `location` | the area the ETL reports for (WWTP catchment or region) | `Attica` |
  | `period` | ISO week, derived by the ETL from ODM `aDateEnd` / `epiWeek` | `2026-W41` |
  | `indicator` | ODM `measure` (the gene target) | `fluA`, `covN1`, `rsvMe` |
  | `dimensions.pathogen` | ERVISS spelling, required, consistent with the measure (`fluA` → `Influenza`) so wastewater and clinical feeds join on *location × period × pathogen* | `Influenza` |
  | `dimensions.aggregation` | ODM aggregation code, which carries normalisation | `me`, `floMean`, `pmmovNorm` |
  | `dimensions.fraction` | ODM fraction analysed, optional | `liq`, `sol`, `mix` |
  | `value` / `unit` | the value and ODM unit code | `gcL`, `gcDay100k`, `gcPpmov`, `log10cpL` |
  | `quality` | ODM quality indicator; on a `beLOD` row the value is the producer's stand-in | `beLOD` |

  The vocabulary is pinned to the respiratory subset of **ODM v3.0.1** (SARS-CoV-2, influenza A/B, RSV
  measures, PMMoV `ppmv`, and the units, aggregations and fractions above), as ERVISS is pinned to a
  snapshot. ODM's `specimen` and `compartment` are left out: for wastewater they are always a sample
  (`sa`) of water (`wat`). Sample, site and method metadata (LOD values, protocols) stay in ODM's other tables, outside the feed; the
  ETL drops measures ODM marks as not reportable. **Non-detections are measurements, not gaps:** a
  week whose samples were all below the limit of detection is still a row, flagged `quality: beLOD`,
  so the line continues instead of breaking and the table and tooltip read "below detection limit".
  Its value is whatever the producer reports or substitutes (labs differ: 0, LOD/2, the LOD itself);
  ODM leaves it to them, the ETL documents its choice, and the app shows the label, not the number.

  **CDC NWSS crosswalk.** NWSS is semantically compatible but flat and wide (one row per sample ×
  target), so it is a documented mapping rather than the anchor; ODM v3 ships NWSS→ODM conversion
  tools. Concept-level: NWSS PCR target → `indicator` (ODM measure); concentration in copies/L, log10
  copies/L or copies/g dry sludge → `gcL` / `log10cpL` / `gCGS`; flow-population and PMMoV-normalised
  concentrations → `aggregation` `floMean` / `pmmovNorm` with their units; NWSS's below-LOD flag →
  `quality: beLOD`. NWSS's derived WVAL has no ODM code. (Exact NWSS field names are pinned from the
  current NWSS data dictionary when a US adopter needs the crosswalk.)
- **Derived analytics (Status / Trend / phase) — a separate, method-agnostic contract, not feed
  rows.** These are *assessments of a series* by a method (aedseo, MEM, IDSR-style thresholds, …), not
  observations: categorical, carrying uncertainty and thresholds that don't fit a numeric feed row.
  They are **computed outside the app**, by the analytics component (§6.3.1) or by a country's own
  ETL, and the app only loads and presents them. The tables are the interface between the two.

  **Methods** are a registry in code, like profiles, read by both the app and the analytics
  component. Each declares its **ordered** `levels`, its `phases`, and whether it produces a `trend`;
  e.g. aedseo: levels `very_low` < `low` < `medium` < `high` < `very_high`, phases `in_season` /
  `out_of_season` (one season a year) and `in_wave` / `between_waves` (year-round circulation in
  waves), trend yes. Vocabularies are per method because other domains grade
  differently: IDSR-style surveillance of epidemic-prone diseases uses *normal / alert / epidemic*
  against fixed or week-of-year thresholds; polio AFP surveillance and HIV 95-95-95 monitoring grade
  attainment against fixed targets, with outbreak status as the useful phase and no season. The UI
  colours levels by their order, so tiles work for any method. A method that derives a pathogen-level
  phase from several series also declares its `stream_roles` (aedseo: `cases`, `admissions` — SSI's
  community and admissions pairing); a polio method would declare its own (e.g. AFP cases and
  environmental samples), and a method with no derived phase declares none.

  **Three tables**, long CSVs at their natural grain, codes not display text:
  - **`assessment.csv`** — series key (`location` + `indicator` + the feed profile's dimensions) ×
    `period` (every period, so tiles can describe any selected range, not only the latest week) ×
    `method` → `level` (the method's code, or blank when ungradeable), `provisional`
    (`true`/`false`: graded with less history than the method needs), `trend` (`increasing` /
    `stable` / `decreasing` / `inconclusive`, blank where the method has none), `growth_rate`,
    `growth_lower`, `growth_upper` (numbers or blank: the **proportional change per period**, e.g.
    `-0.2` = −20%/week; a producer converts a log-scale rate such as aedseo's with `exp(r) − 1`), and
    `phase` (the series' own phase, e.g.
    `in_season`, or blank) — the run of active weeks is the shaded band on that series' chart. Each
    period's row is computed **as of that period**, from data available up to it: a past week shows
    what the method said then, not a re-grade with hindsight (aedseo's thresholds and growth shift as
    data arrives). A producer may supply only recent periods (e.g. the latest); the UI handles gaps.
  - **`thresholds.csv`** — series key × `from`/`to` (the span's first and last period, stated
    explicitly so the app needs no method's season convention) × `method` × `level` → `lower_bound`:
    one row per level boundary, so methods may have any number of bands and thresholds may be fixed
    (one span) or change per season or per week. Draws the chart bands.
  - **`phase.csv`** — `location` × `pathogen` × `period` × `method` → `phase` (e.g. `in_season`,
    `out_of_season`, `in_wave`, `between_waves`): the pathogen-level status behind the "in season since W48" badge,
    e.g. greece-public-health's cross-stream rule (community and admissions streams have each onset
    and their runs overlap). **Precomputed, not derived in the app:** the rule is a policy choice that
    belongs with the analysis, and a country may write its officially declared season here instead.
    `out_of_season`, not "pre-season": a quiet week can't tell before-onset from after-season.
  - **`phase_streams.csv`** (optional) — `location` × `pathogen` × `method` × `role` → `feed` +
    `series`: the series a computed phase was derived from, `role` from the method's `stream_roles`,
    `series` written as `/api/data` parameters (e.g. `indicator=cov&aggregation=floMean`). Recorded by
    the producer, not re-declared in config, so the overview's evidence can't disagree with the rule
    that produced it. Absent for declared states (an official season, a polio outbreak declaration)
    and for pathogens with no phase (e.g. HIV).

  **Attachment and validation.** Assessments attach to a feed — `data.feeds[].assessments: <dir>`
  holding `assessment.csv` and `thresholds.csv`, validated against that feed's profile — and the
  cross-feed pathogen phases to `data.phases: <file>` (one `phase.csv` per dashboard), with their
  streams at `data.phase_streams: <file>`; all optional (no assessments, no tiles). Stream rows are
  checked against the method's `stream_roles`, a configured feed, and that feed's profile. At
  load, failing fast with file and row: series keys valid for the profile and periods matching its
  format; `method` in the registry and `level` / `phase` / `trend` in that method's lists or blank
  (`trend` blank for a method without one); growth finite with `lower ≤ rate ≤ upper`, or all blank;
  thresholds with `from ≤ to`, non-overlapping spans per series and method, and lower bounds rising
  in level order; phase pathogens in the registry. Duplicates follow the feed rule: exact copies
  dropped with a warning, conflicting readings for one series × period × method fail the load.
  Assessment rows for series no panel shows are allowed.

  **Methods coexist** as rows with different `method` values; config decides whether the UI shows one
  or a comparison. Whether MEM is viable for a series is a data-depth question (its thresholds need
  several seasons of history), not a schema one.

#### 6.3.1 Analytics component

The methods are standard, so they are computed once, generically, rather than in each country's
ETL: `health_signal.analytics` reads the feeds and writes the tables above. aedseo first (Status,
Trend, onset, waves and phase), generalised from greece-public-health's aedseo bridge, reusing its
reviewed code and tests where they fit; MEM and others as further registry entries. aedseo and MEM
are R packages (via rpy2, in-process), so the component installs as an optional extra
(`health-signal[analytics]`) and the app itself stays free of R and never imports it. Countries may
still supply their own tables in the same format.

greece-public-health will later migrate onto this package (the app, and the aedseo part of its
pipeline), so the component is a library first and a CLI second: `assess(config, full=False, jobs=1)`
and the per-series step it is built from are public and importable, nothing in it is specific to
Greece, and the code ported from greece-public-health is audited as it moves (behaviour it should not
keep is fixed here and reported back).

**Which series.** The series panels show: each feed with an `assessments` dir × its single-series
panels (no `series_by`; tiles, bands and shading appear only on those) × every location a viewer can
select (`filters.location`'s options; every location in the feed's data when there's no location
filter), so a feed covering all EU countries costs nothing for regions the dashboard can't show. No separate list to keep in step with the panels.

**Settings.** Defaults live with the method in code (SSI's: `k=5`, `n_peak=3`, `decay_factor=0.8`,
`conf_levels=0.975`, the families, and the wave-segmentation settings tuned on Greek COVID). Config
overrides only policy choices, each in one place:
- `surveillance.year_start_week` — the season boundary (the season ends the week before), shared
  with the date-range presets (§6.1). aedseo has no week 0, so `assess` refuses a season starting in
  week 1 before fitting anything.
- `analytics.min_seasons` (default 3) — completed seasons (≥ 30 weeks each, excluding the current
  one) before a grade stops being provisional.
- `analytics.wave_pathogens` (default `[SARS-CoV-2]`) — pathogens that circulate in waves rather than
  one season a year (a series shown on several tabs is phased in waves only if all of their pathogens
  are listed, so ILI on the COVID tab doesn't take COVID's waves onto the influenza tab); each must be a
  registry pathogen (not necessarily a target, so the default suits
  a dashboard without a COVID tab). Replaces greece-public-health's "covid in the
  key" rule.
- `analytics.phase_streams` — the inputs of a method's pathogen-level phase (below).

**Input to aedseo, by the row's `unit`.** Counts → aedseo's cases path (rounded). A rate with its
own denominator series → the incidence path with that series as the exposure offset; the profile
declares the pairing (ERVISS `positivity → tests`, same series key otherwise), and a week whose
denominator is missing or zero isn't graded; a denominator matching several rows per week, or none, skips
the series with a warning. Every other rate or load (per 100k, `gcDay100k`, `gcL`,
…) → the incidence path with a constant exposure (it cancels in the growth model), fitted on the values
× a per-series scale — the smallest power of ten that lifts the smallest positive value to ≥ 100 — with
the thresholds divided back. aedseo can't grade values below 1 (its disease threshold bottoms out at 1)
and rounds the counts it derives; its thresholds scale with the values (checked to within 0.01%) and its
growth is unchanged from a scale of 100 up.

**Censored values.** A value the profile flags as a stand-in rather than a measurement (PHES-ODM `beLOD`,
below the limit of detection) is fitted as a gap — aedseo's growth model would otherwise read a
non-detect's 0 as a −100% fall and back — but its own week is still graded and phased from the value
(a non-detect is very low and below the season threshold), and still counts as an observed week toward
completed seasons. On Attica's wastewater this reproduces greece-public-health's growth and trend exactly;
its disease thresholds differ by a few percent, because greece-public-health drops non-detect weeks and so
closes up the calendar aedseo's windows run over, where these stay as gaps.

**Per series, each week *t*, as of *t*.** aedseo runs on the series' data up to and including *t*,
on a contiguous weekly calendar where missing weeks are NA rows (aedseo's windows are rows, and it skips
those too sparse to fit, so growth across an outage is inconclusive rather than rescaled):
1. Thresholds: the disease threshold and burden levels for *t*'s season. Consecutive weeks with
   identical bounds share one `thresholds.csv` span, so a grade and its band always use the same bounds.
2. Level: *t*'s value against those bounds; blank when they aren't finite, except that a reported
   zero grades `very_low`. `provisional` when completed seasons < `analytics.min_seasons`.
3. Trend: `seasonal_onset`'s current-season growth, written as `exp(r) − 1`; `increasing` if the
   lower bound > 0, `decreasing` if the upper < 0, else `stable`; `inconclusive` with blank growth
   when aedseo returns NA (including R's NA-integer sentinel, rejected by magnitude).
4. The series' phase: for a wave pathogen, `in_wave` when aedseo's multiple-wave segmentation puts
   *t* in a wave, else `between_waves`. Otherwise `in_season` from the first onset alarm within a
   run at or above the disease threshold; one week below doesn't end it, a second consecutive one
   does (as-of rows can't bridge with hindsight, so the season ends a week late rather than being
   bridged); weeks with no data have no row and carry the state over, up to 8 missing weeks in a row; a
   longer reporting gap ends the season (greece-public-health's `max_missing`). Blank when the fit fails.

A week aedseo can't fit at all (thin or degenerate history) still gets a row — an `inconclusive` trend,
no phase, and a blank level, except that a reported zero grades `very_low` as greece-public-health does —
so a tile describes the data's latest week rather than an older graded one. A series with no gradeable week is warned by name; R or aedseo missing,
or nothing graded at all, stops the run with an actionable error.

**Pathogen phase.** `analytics.phase_streams` entries name, per pathogen × location × method, the
series for each of the method's `stream_roles`, as `<page>/<panel>` under that pathogen's target:

```yaml
analytics:
  phase_streams:
    - {pathogen: Influenza, location: Greece, method: aedseo,
       streams: {cases: clinical/ili, admissions: clinical/sari}}
```

Roles are checked against the method's `stream_roles`, each panel must exist, show a single series
and belong to a feed with an `assessments` dir; a method without stream roles can't appear. The
method owns the rule that combines the streams' own phases: aedseo's (SSI's) is "every role in season
(or in a wave)", else `out_of_season` (`between_waves`). A `phase.csv` row for *t* is written only when
every stream has a phase at *t*, so a lagging stream yields no row rather than a false
"out of season" — the UI shows the latest row as of its week. `phase_streams.csv` records each role's
feed and series straight from the panel's query. Pathogens or locations without an entry get no phase
(e.g. Attica influenza, which has no cases stream). Both tables are rebuilt in full every run from the
assessment rows: no R is involved, and they stay consistent after a rebuild.

**CLI.** `health-signal assess --config dashboard.yaml [--full] [--jobs N]`; `health-signal serve`
runs the app, and a bare `health-signal --config …` still serves. Each assessed feed's dir gets
`assessment.csv`, `thresholds.csv` and `assessed_with.csv`; `data.phases` and `data.phase_streams`
get the pathogen tables (required by config when `phase_streams` is set).

**Incremental runs.** The existing tables are the state: per series and method, only weeks after the
last assessed one are computed, up to the series' latest data week; the season-run state (in a run, or
one week below the threshold) resumes from the stored rows and thresholds, so an incremental week
matches what a full rebuild writes; a new series (a new panel or location) is backfilled automatically; new weeks extend the last threshold span when its bounds are
unchanged. `assessed_with.csv` (`method`, `setting`, `value`; one row per list item) records the
settings the rows were computed with — `year_start_week`, `min_seasons`, each `wave_pathogen`, and the
method's package version — and a run whose settings differ stops and asks for `--full` rather than
mixing rows from different rules. Long-form like the other tables, it maps onto a database table
(plus the feed) unchanged. Revisions to older data aren't detected: run `--full` after one. Rows of
series no panel shows any more are kept (the contract allows them) and logged; `--full` starts
afresh. `--jobs N` (default 1) assesses series in parallel processes, each with its own embedded R.

**Writing.** New tables go to temporary files, are loaded through the app's own loaders
(`AssessmentSource`, `PhaseSource`, `PhaseStreamSource`) — one contract check shared by producer and
app — and only then replace the old files by rename, so a failed run leaves the served tables intact.
Progress is logged per series (weeks computed, weeks graded) with a closing summary; a systemic
failure (no R, nothing graded, a settings mismatch without `--full`) exits non-zero so a scheduled
job fails visibly.

**Verification on real data.** Beyond the synthetic tests, `assess` runs locally on the Greek feeds
(ERVISS and the Attica wastewater in `phes_odm`) from a scratch directory outside the repo, and its
latest-week grades, thresholds, growth and phases are compared with greece-public-health's
`data.json` for the same weeks; differences are explained (as-of vs full-history fits, the season
run's end rule) or fixed. The output is never committed, and the 4c-4 UI is iterated against it before either merges.

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
    def query(self, *, location=None, indicator=None, week_from=None, week_to=None,
              **dimensions) -> list[FeedRow]: ...   # any profile dimension; unknown names raise
    def periods(self) -> tuple[str, str] | None: ...  # first and latest period; None when empty
```

- One `DataSource` per configured feed, keyed by feed id; each validates against its own profile.
- `FileDataSource(data_dir, profile)` — reads profile-format CSV with pandas and validates every row
  against the profile (fails at load naming the file and data row). Across a feed's files, an exact
  copy of a row is dropped with a logged warning (it carries no information, and ERVISS's published
  files overlap by design), while two different readings of one series-week — same location, period,
  indicator and dimensions, different value or unit — fail at load naming both rows. **MVP.** Parquet/JSON can be added behind it later.
- `PostgresDataSource(dsn)` — same schema as a table/view. **Deferred.**
- `DHIS2DataSource(base_url, token)` — pulls aggregate/analytics data via the DHIS2 Web API and maps
  it into a feed's schema profile, for countries that run DHIS2 as their HMIS. **Deferred.**
- Selected by config; the API and UI are agnostic to which is behind it. Every source returns rows
  validated against their feed's schema profile (§6).

### 7.2 `AuthProvider`

Auth risk is **not hand-rolled** — the risky pieces (session tokens, OAuth flows, password
hashing) are delegated to maintained libraries. The provider owns its own **login routes** so a
different login mechanism is a different provider, not an app change:

```python
class AuthProvider(Protocol):
    def install(self, app: FastAPI) -> None: ...       # register this provider's login/logout(/callback) routes
    def current_user(self, request: Request) -> "User | None": ...   # read the established session (shared shape)
```

- **`LocalAccountsProvider` (basic/demo — MVP):** DB-free, accounts from config/secrets
  (`HEALTH_SIGNAL_ACCOUNTS` email→hash + `HEALTH_SIGNAL_SECRET_KEY`). Session cookie/token managed
  by **`fastapi-login`** (`LoginManager` + a `user_loader` reading the config accounts); password
  hashing by **argon2** (argon2-cffi/passlib). We write only thin glue — no hand-rolled session or
  cookie crypto.
- **`OIDCProvider` (SSO — deferred):** OAuth2 Authorization-Code + PKCE via **Authlib** (audited),
  as an OIDC Relying Party to a managed IdP (Microsoft Entra/Azure AD, Auth0, or Keycloak — chosen
  at that stage; Authlib treats them identically via discovery). Installs a redirect `/login` +
  `/callback`; the app never handles credentials. Same seam, so it drops in without app changes.
- **Shared, app-level (provider-agnostic):** the signed session, the `require_auth` dependency, and
  the **per-page access policy** (§7.4) — these do not move when the provider changes.

### 7.3 AI access (OpenAPI now; MCP later)

The gated JSON API plus its OpenAPI schema (§5) is already an **AI-consumable contract** — agents and
LLM tool-use frameworks can call `/api/data` etc. straight from `/openapi.json`, so the app is
"AI-ready" at the data layer with no extra work. An **MCP (Model Context Protocol) server** — exposing
the same `DataSource` + config as MCP tools/resources (`list_indicators`, `query_series`,
`get_status_trend`) behind the same `AuthProvider` (MCP supports OAuth) — is the standard way to reach
MCP-native AI clients and plugs into the existing seam with **no core change**. **Deferred** (post-MVP);
OpenAPI covers baseline AI access for now.

### 7.4 Per-page access policy (public vs locked)

Page access is **configurable**: each page defaults to **`authenticated` (locked)** and is opted
into **`public`** in config. The enforced boundary is the **data** (`/api`), not the HTML — the SPA
is client-routed public code, so a public page's data is served unauthenticated while a locked
page's data requires auth; the client shows a login CTA for locked pages. `require_auth` and the
`/api` gate consult the config access policy (public resources bypass auth); `/healthz` and the
provider's login routes are always public. Default-locked matches "keep content off public eyes."

## 8. Server (FastAPI) — routes

| Route | Auth | Purpose |
|---|---|---|
| `GET /login`, `POST /login`, `POST /logout` | public / session | account login, session cookie |
| `GET /api/me` | required | current user (name/role for the UI) |
| `GET /api/config` | required | which pathogens/indicators/layout/branding/locales, plus the method registry (each method's ordered levels, phases, trend) |
| `GET /api/periods` | required | `{first, last}` ISO weeks spanned across all feeds (null without data); bounds the date-range control |
| `GET /api/data?feed=…&…` | required | rows from one feed (required `feed`); filters: `location`, `indicator`, `week_from`/`week_to`, and that feed's profile dimensions. Parameters come from the feed's profile, so a new profile needs no route change; an unknown feed or dimension is a 422 |
| `GET /api/assessments?feed=…&…` | required | assessment rows for one feed; same filters as `/api/data` plus optional `method`. A feed without assessments returns `[]` |
| `GET /api/thresholds?feed=…&…` | required | threshold rows whose `from`–`to` span overlaps `week_from`–`week_to`; same filters plus optional `method` |
| `GET /api/phase-streams?…` | required | the series behind each pathogen phase; filters `location`, `pathogen`, `method` |
| `GET /api/phases?…` | required | pathogen phase rows; filters `location`, `pathogen`, `method`, `week_from`/`week_to` |
| `GET /api/locales/{lang}` | required | translation bundle (library base + country overrides, merged) |
| `GET /api/methodology/{lang}` | required | config-selected methodology content (Markdown) for the Methodology view |
| `GET /docs`, `/redoc`, `/openapi.json` | required | auto-generated API documentation (Swagger UI / ReDoc / OpenAPI schema) |
| `GET /` and `/{path}` | required | serves the compiled SPA (`_ui/index.html` + assets) |

App factory: `create_app(config) -> FastAPI`, wiring the configured `DataSource` + `AuthProvider`.
The SPA catch-all is registered **last** so `/api/*`, `/docs`, `/redoc`, and `/openapi.json` take
precedence over client-side routes.

## 9. Frontend — modularity & i18n

- **Config-driven rendering.** The SPA fetches `/api/config` and builds pathogen tabs, panels, and
  indicator charts from it. One route per configured page. Layout (after greece-public-health): a plain
  utility strip for session controls (language, Configuration, Sign out), a header with the title on the
  left and the dashboard filters on the right as label/value rows (Region, Date range, Reporting week;
  stacked under the title on phones), a row of target tabs whose right end is reserved for a Methods
  link, and a second row of page tabs when a target has more than one page — MUI `Tabs`, active state
  from the URL. `/` lands on the first target. Filters live in the URL (`?location=`, and `?range=` for
  a preset or `?from=&to=` for custom weeks) so a view is deep-linkable, and tab links carry them;
  presets stay relative, so a shared "last 52 weeks" link rolls forward with new data. Adding/removing/reconfiguring a surveillance target = config + data,
  no code. **Status/Trend (Stage 4c-4).** A single-series time-series panel shows Status and Trend
  tiles (to the right of the chart; above it on phones) when its series has assessments — detected
  from the data (the panel fetches its series' assessments over all periods; none means no tiles).
  The tiles describe **the selected range's last week**: the latest assessment within the range,
  labelled "As of W##", styled as not-current when that week isn't the latest reporting week, and
  "No assessment in this range" when the range has none (never reaching before the range start).
  Charts draw the method's threshold bands for spans in view and shade the series' own `phase` run.
  Panel `type` adds `phase` and `summary`, which take no query and work from their target and the
  location filter; an Overview page composes them, and either can be left out. The **phase panel**
  overlays the `phase_streams` series, shaded with the pathogen-level phase, beside a tile stating
  the phase as of the range's last week (same guardrails), with the method's rule text from i18n
  (`methods.<method>.phase_rule`). The **summary panel** is a grid of the target's assessed
  single-series panels — label, page, Status, Trend, as-of — highlighting the phase streams' rows
  and linking to their pages. Prototype panels/logic (range selector, EuroMOMO
  strip, Methods view) port into config-driven React components.
- **Routing (per-page URLs).** React Router gives every page its own path — e.g.
  `/sars-cov-2/clinical`, `/sars-cov-2/wastewater` — so pages are deep-linkable and shareable. Paths
  are derived from the target id and page id (§6.1), never configured. The FastAPI
  catch-all (`GET /{path}`, auth-gated) serves `index.html` for all of them; React Router takes over
  client-side.
- **Styling discipline — minimize custom CSS.** Use **canonical MUI components** and MUI's own
  styling configs (the `theme` object, `sx` prop, `styled()`, component `variants`/`defaultProps`)
  rather than bespoke stylesheets. The prototype's hand-rolled `styles.css` is **not** carried over —
  its look is reproduced through MUI's system. Custom CSS is a last resort (a genuinely un-MUI layout
  need), kept minimal and justified. This keeps the library consistent, themeable, and low-maintenance.
- **Theming (per-government white-label).** MUI `ThemeProvider` built at runtime from the config
  branding block. `branding.theme` **is a MUI theme-options object** (e.g. `palette.mode`,
  `palette.primary.main`, typography) passed straight to `createTheme` — authors use MUI's own
  documented schema rather than a bespoke vocabulary, and MUI's validation is the validation (a
  malformed theme fails fast with a debuggable error, not a silent fallback). `logo`/`favicon` are
  separate branding assets. A government restyles via `dashboard.yaml` + assets — no rebuild, same UI
  bundle. Because styling flows through the theme (not ad-hoc CSS), a theme swap restyles the whole
  app coherently.
- **Data fetching.** Pages fetch through a small `useResource` hook + a shared `ResourceBoundary`
  that centralizes loading, the 401→login redirect, and error UI, so per-page boilerplate and the
  auth-redirect policy live in one place. When the data layer lands (charts + multiple `/api/data`
  queries), adopt **TanStack Query** as the fetching layer (caching, dedup, refetch/polling) rather
  than growing bespoke hooks.
- **Method display.** When a config panel has multiple analytic methods in the feed (e.g. aedseo +
  MEM), the UI can show a method toggle / side-by-side comparison; labels and level vocabulary come
  from the method metadata + locales.
- **i18n (layered locales).** react-i18next; `en` + `el`, default `en`; language switcher. The
  **library ships the base UI-string catalog** (generic chrome: nav, Status/Trend, "as of", login,
  buttons — en/el, extensible to more languages). The **consumer supplies only country-specific and
  data-driven strings** (pathogen display names, source subtitles, methodology text) and may override
  library defaults. `/api/locales/{lang}` **deep-merges** library base + country overrides (country
  wins) so no country re-translates the generic chrome.
  - **Config carries keys, not translations.** `dashboard.yaml` holds structure + stable ids/i18n
    **keys**, never inline `{en, el}` maps. Targets, pages and panels derive their label key from their
    stable id by convention (`id: covid` → `targets.covid`, `id: clinical` → `pages.clinical`,
    `id: hospital_admissions` → `panels.hospital_admissions`); config cannot set a different key, since
    renaming an id or rewording a locale string covers every case an override would.
    Page and panel ids need only be unique within their parent, so the same panel on several targets
    shares one id and one string. The text for each key lives in the locale files. This keeps **one source of truth** for translatable
    text, so translators work in one place and adding a language is a single new locale file — no
    config edits. (Config fields like `site.title` that name the app/OpenAPI, not user-facing UI, stay
    plain strings.)
- **Methodology view (config-driven).** Generalizes the prototype's "Methods" page: a page that
  renders **config-selected methodology content** (Markdown, per-locale, via `/api/methodology/{lang}`,
  rendered with react-markdown). The methodology shown **matches the configured analytic method(s)**
  (e.g. the Status & Trend note for aedseo, or MEM). The library ships base notes for methods it knows
  (aedseo); the consumer overrides/adds country-specific methodology. This is in-app content
  (config/data), independent of any repo `docs/` directory.
- **API docs.** FastAPI serves Swagger UI at `/docs`, ReDoc at `/redoc`, and `/openapi.json`, all
  behind the auth gate; generated from the route definitions + Pydantic models, so they track the code.
- **Charts.** Chart.js (`react-chartjs-2`), following the dataviz rules: one y-axis (the panel's
  unit), 2px lines, a crosshair with one tooltip per week (value before label), a legend for ≥ 2
  series and ink end-labels for ≤ 4, and a **table view** on every chart. Series colours come from a
  fixed-order, CVD-validated categorical palette in the theme (`palette.chart.light`/`.dark`,
  replaceable via branding) and are never cycled. A panel whose rows can't make an honest chart —
  none, mixed units, several rows per series-week, or more series than colours — shows a message
  instead of a misleading plot.

## 10. Packaging & reuse

```text
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

```text
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
private consumer repo. Fixtures are hand-crafted synthetic ERVISS/PHES-ODM-shaped rows with obviously
fake locations/values; any realistic sample is drawn only from the **openly-licensed** ERVISS/NWSS
public datasets, never from the pilot's private feed. Local verification may run the app against the
pilot's real Attica wastewater tables transformed into a `phes_odm` feed, from a scratch directory
outside the repo; that output is never committed, and screenshots of it stay out of PRs.

- **E2E (highest priority):** drive the running FastAPI app end-to-end — unauthenticated request is
  blocked → login → `/api/config` + `/api/data` → a page renders the expected panels; per-page URLs
  are deep-linkable behind auth; language switch swaps strings. Tooling: Playwright (or FastAPI
  `TestClient` + a headless frontend harness) against the assembled app.
- **Integration:** API routes with a real `DataSource` (`FileDataSource` over a sample feed) and a
  real `AuthProvider`; **contract validation** of a sample feed against its schema profile;
  the locale deep-merge (library base + country overrides). Prefer these over mocking the seams.
- **Unit (focused logic only):** Pydantic profile validation, config parsing, locale merge, small
  frontend helpers.
- **Frontend:** Vitest + React Testing Library for component/config-driven rendering where an E2E is
  overkill.
- **Analytics (§6.3.1):** most tests run without R against a fake aedseo backend returning set
  thresholds and growth per week — series derivation, input paths and denominators, grading and
  trend rules, the as-of phase rules, the cross-stream rule, incremental merge, `assessed_with.csv`
  and safe writing. A few tests run real aedseo on a synthetic series and assert invariants, not
  numbers: bounds rise, growth lies within its interval, and earlier weeks' as-of rows don't change
  when later weeks are added. They're skipped without R, and a separate CI job installs R and a
  pinned aedseo to run them, keeping the main job R-free.
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

Stage 4c (Status/Trend, z-score severity, wastewater) exceeds the cap, so it ships as five PRs:
**4c-1** wastewater feed (multiple feeds, the `phes_odm` profile, profile-derived `/api/data`
parameters, duplicate and conflicting-row handling, wastewater pages); **4c-2** the assessment
contract (§6.3: the three tables, method and pathogen registries, target ids as pathogen keys,
derived page paths, loading, validation and the three endpoints), no UI; **4c-3** the analytics
component (§6.3.1) with aedseo, as one PR over the cap by agreement, stacked on 4c-4 so the
pipeline is verified end to end on Greek data while the UI that consumes it is iterated on that data;
**4c-4** Status/Trend tiles, threshold bands, per-series phase shading, and the Overview's phase and
summary panels (with `phase_streams` and method `stream_roles`);
**4c-5** the EuroMOMO-style mortality z-score strip.

**Repo:** `weilu/health-signal` on GitHub — **public**, **MIT** licensed. The staged-PR flow runs here.

## 14. Open questions / assumptions

- Non-organism surveillance subjects (e.g. AMR) as targets — decided when an AMR profile arrives.
- Exact per-country config schema (`dashboard.yaml`) fields — to be pinned in the implementation plan.
- Whether the generic repo is a true monorepo (frontend + package together) or split — assume
  monorepo for MVP.
