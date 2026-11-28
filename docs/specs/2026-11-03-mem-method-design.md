# MEM as a second method — design

Adds the **Moving Epidemic Method** (MEM; R package `mem`, Vega et al. 2013, 2015) beside aedseo, so a deployment can
grade its indicators with either or both, and readers can switch between them.

## Intent

Greece's public health organisation, EODY, says it uses MEM. ERVISS shows how: it computes MEM thresholds for each
country's national ILI/ARI rate once a year, from five past seasons, and the country's focal point approves them or
supplies its own. On erviss.org, Greece appears in "Weekly intensity of influenza-like illness (ILI) activity by
country" (ILI/ARI syndromic tab), which shows only countries with approved thresholds, from 2022/23 on. So EODY's
readers know MEM's levels for ILI, and the dashboard should be able to show them, next to aedseo's for comparison.

This is also the last piece before health-signal's first release, which greece-public-health will pin.

## What MEM does (from `mem` 2.19's own documentation)

- **Input:** one series, laid out one column per season. Missing weeks stay missing, never zero. Each season must
  hold one epidemic wave.
- **Epidemic period** of each past season: where the accumulated rate stops climbing fast (`i.param`, default 2.8%).
- **Epidemic threshold**, from the weeks before each past epidemic, and a post-epidemic threshold.
- **Intensity thresholds** (`memintensity`), from the epidemic weeks at 40%, 90% and 97.5% (`i.level.intensity`),
  giving five levels: **baseline** (below the epidemic threshold), **low**, **medium**, **high**, **very high**.
- **Trend** (`memtrend`): Delta and Eta from past seasons. A week is *ascending* when above the epidemic threshold and
  up on last week by more than Delta, or the first week above it; *descending* when above it and down by more than
  Eta, or the first week back below it; *stable* otherwise, which includes every week below the threshold.
- There is no growth interval and no pathogen-level season flag in MEM.

## Goals

- MEM is a second entry in the method registry (`methods.py`), graded by `health-signal assess` into the same tables
  (`assessed.csv`, `thresholds.csv`, `assessed_with.csv`), each row naming its method.
- **Which panels a method grades** is one general setting for every method: an optional allowlist. Without one, a
  method grades every single-series panel (aedseo today); with one, only those listed.
- A **Method** selector in the dashboard's header, next to Location and Date range, when the deployment grades with
  more than one method. The tiles, the chart's level shading and the Overview's summary follow the selection.
- The Methodology page describes **the selected method**, from a page per method.
- For Greece, MEM's weekly levels for national ILI match ERVISS's heatmap.

## Non-goals

- MEM for pathogens graded as waves (COVID-19): MEM assumes one epidemic per season.
- memapp, `memsurveillance` graphs, or any of `mem`'s plots.
- Fetching ERVISS's or EODY's own thresholds: MEM is computed here, and checked against theirs.

## Anti-goals

- **Mixing methods in one view.** With MEM selected, an indicator MEM doesn't grade says so; it never falls back to
  aedseo's grade under a MEM heading.
- **A "Stable" that means "not looked at".** Below the epidemic threshold MEM doesn't assess trend, so the dashboard
  says that, rather than repeat `memtrend`'s literal "stable".

## Decided (with the user)

1. **MEM grades any indicator a deployment points it at**, not just ILI. Guards rather than a ban: provisional below
   the history it needs, rejected for wave pathogens, and the method text says it was built for ILI/ARI.
2. **Allowlist per method**, the same for every method: none = every single-series panel, a list = those only.
3. **A Method dropdown** next to Location and Date range, shown when more than one method grades. With aedseo
   selected, tiles and shading use aedseo's results; with MEM, MEM's.
4. **Below the epidemic threshold, MEM's trend reads "Not assessed"** (Greek «Δεν αξιολογείται»), with the tile's
   footer saying MEM assesses trend only during an epidemic. The first week above the threshold (ascending) and the
   first week back below it (descending) still show.
5. **MEM seasons for influenza and RSV** *(revised 2026-11-04; first decided: no Key signals for MEM)*: a pathogen's
   MEM season pairs the same two streams as aedseo's, community spread and hospital admissions. COVID-19 stays
   aedseo-only, and the MEM methodology page names the pathogens MEM doesn't grade. Admissions start at 2025-W44, so
   MEM can't grade them, nor set these seasons, before 2027/28; accepted.
6. **MEM keeps its own season window**, so it can match ERVISS: `analytics.mem.season_start_week`, which Greece sets
   to 25 (ERVISS lays out Greece's seasons as W25→W24). aedseo keeps the dashboard's surveillance year (W21 for
   Greece).
7. **The Methodology page follows the selected method**: one page per method, the one shown being the one
   selected.

## Design

### Settings

```yaml
analytics:
  methods: [aedseo, mem]          # graded methods, in the selector's order; the first is its default
  min_seasons: 3                  # unchanged: below it, a grade is provisional, whatever the method
  aedseo:
    wave_end: { steps_with_decrease: 3, burden_level_decrease: medium }
    # panels: [...]               # optional allowlist (below); absent = every single-series panel
  mem:
    season_start_week: 25         # MEM's own season window (the week before ends it)
    seasons: 5                    # past seasons each season's thresholds come from (ERVISS's setup)
    panels:                       # optional allowlist
      - Influenza/clinical/ili_rate
      - Influenza/clinical/sari_rate
```

- `analytics.methods` defaults to `[aedseo]`, so existing deployments are unchanged.
- **Allowlist entries are panel references, `<target>/<page>/<panel>`.** Grading is per series, so listing one
  panel grades its series, and every panel showing that series (e.g. ILI on each tab) shows the grade. An entry
  naming no panel, or a panel that isn't single-series, stops startup. *(My call: panel references rather than
  indicators, because an indicator alone doesn't pick out one series.)*
- MEM's other statistical settings stay in code, at `mem`'s defaults, like aedseo's (spec §6.3.1).

### Method registry

`Method` gains a **trend vocabulary per method**, in place of today's shared `TRENDS`:

| | aedseo | MEM |
|---|---|---|
| levels (lowest first) | very_low, low, medium, high, very_high | baseline, low, medium, high, very_high |
| trends | increasing, stable, decreasing, inconclusive | increasing, stable, decreasing, not_assessed |
| phases | in_season, out_of_season, in_wave, between_waves | none |
| growth interval | yes | no |

`mem`'s ascending and descending map to `increasing` and `decreasing`. The colours come from the level's position,
so MEM's levels take the same three tones without new UI.

### Grading (`health-signal assess`)

- **Per method:** `assess` runs each method in `analytics.methods` over the series its allowlist picks. The run loop
  (`analytics/run.py`) currently fixes the method to aedseo throughout; it becomes a loop over methods, each with its
  own settings in `assessed_with.csv`. Changing one method's settings needs `--full` for that method only.
- **As of each week, as aedseo is.** A season's MEM thresholds, and its Delta and Eta, come from the up to `seasons`
  complete MEM seasons before it, and stay fixed for that season, as ERVISS's yearly thresholds do. So one
  `memmodel` fit per series per season, not per week.
- **A complete MEM season** is counted as aedseo's are (at least 30 weeks with values), over MEM's window.
- **Provisional** when fewer than `min_seasons` complete MEM seasons stand behind the season's thresholds. Below the
  minimum `mem` can fit, the week is not graded. *(The builder confirms `mem`'s minimum.)*
- **Input:** the series' values as they are, a rate or a count. MEM has no exposure model, so a rate's denominator
  isn't used, and a week whose denominator is missing is still a gap, as for aedseo. Censored stand-ins and missing
  weeks are missing (NA), never zero.
- **Trend:** each week, from the season's Delta and Eta and the change on the week before, by `memtrend`'s rule,
  except that a week below the epidemic threshold is `not_assessed` unless it's the first week back below it. A week
  whose previous week is missing is `not_assessed`. *(My call.)*
- **Thresholds table:** one row per series per season, its four values as the lower bounds of low, medium, high and
  very high, in the series' own units.
- **Wave pathogens:** a series every one of whose tabs is a wave pathogen isn't graded by MEM. Without an allowlist
  it's skipped; listing such a panel stops startup.
- **R:** `mem` via rpy2, beside `aedseo_r.py` (e.g. `analytics/mem_r.py`), behind the same backend protocol where it
  fits. The package build is recorded in `assessed_with.csv` like aedseo's.

### API

Unchanged in shape: `/api/assessments` and `/api/thresholds` already filter by `method`. `/api/config` sends
`analytics.methods` (the selector's options and default), each method's vocabulary, and, per panel, which methods
grade it.

### The dashboard

- **Method selector:** a dropdown in the header after Location and Date range, shown when two or more methods
  grade. It's a filter like the others: in the address (`?method=mem`) and kept by tab links. Labels "aedseo" and
  "MEM", with the full names in the tooltip or the Methodology page.
- **Tiles:** Status shows the selected method's level. Trend shows its trend word and arrow; MEM's has no interval
  sentence, and its footer names MEM's rule. `not_assessed` shows the words "Not assessed: below MEM's epidemic
  threshold" with no arrow.
- **Indicators the selected method doesn't grade:** the tiles read "Not graded with MEM" (or the selected method's
  name), and the chart has no level shading.
- **Chart shading:** the selected method's thresholds. With MEM selected, no in-season or wave bands.
- **Overview:** with MEM selected, Key signals show for the pathogens MEM phases (influenza, RSV), not for COVID-19.
- **Text:** new labels in English and Greek: the selector, MEM's level "baseline" («Βασικό επίπεδο»), "Not assessed",
  "Not graded with {{method}}", the MEM trend footer.

### Methodology page

- **The page follows the selected method**: it shows that method's text, and the selector's choice carries to it
  like the other filters (the top bar's Methodology link keeps `?method=`). A dashboard grading with one method is
  unchanged.
- **A page per method.** A deployment writes `methodology_dir/<method>/<language>.md`, e.g. `aedseo/el.md` and
  `mem/el.md`. A method without a deployment page shows the library's general text for it. *(My call: the old
  `methodology_dir/<language>.md` layout is read as aedseo's page, so a single-method deployment needs no change.)*
- **Placeholders keep their names and mean the page's method**: `{{> method}}` and `{{> method.<section>}}` inline
  that method's library text, `{{method.build}}` its package build, `{{> levels}}` its levels. Each method declares
  its own values (aedseo's `n_peak`, `conf_levels`, …; MEM's `seasons`, `season_start_week`, …) and sections. A
  placeholder the page's method doesn't have stops startup, as an unknown one does today: `{{> streams}}` and
  `{{> phase_patterns}}` belong to aedseo's pathogen-level phases, so a MEM page can't use them.
- **The API:** `GET /api/methodology/{language}?method=mem`; without `method`, the deployment's default.
- The library ships MEM's general text in English and Greek (`methodology_text/mem.{en,el}.md`): overview,
  status, trend, references, saying that MEM was built for ILI/ARI and grades each indicator on its own.

### Checking it against ERVISS

- A test fits MEM to a synthetic series with a known outcome. No Greek data in the repository.
- Greece's check is run locally on the pilot's data: national ILI (from 2020-W01), MEM window W25, five past
  seasons. Each week's level for 2025/26, the first season with five past seasons behind it, is compared with the
  colour of the same week on ERVISS's heatmap; earlier seasons have fewer seasons behind them and may differ. The
  differences, and why, go in the PR description.
- EODY is asked for the threshold values they approved, to compare directly.

## Left to the builder

- `mem`'s minimum history, and how a `memmodel` failure on short history shows (not graded, not an error).
- The backend interface: one fit per season returns thresholds and Delta/Eta; whether that's a second backend type
  or the same protocol with a season-level call.
- How the run loop records and resumes per method (`FeedStore` already keys rows by method).
- Where the Method selector sits on phones, with the other filters.
- greece-public-health's follow-up: add `mem` to its settings (window 25, its allowlist), write its MEM methodology
  pages (or use the library's), and move its TODO pin to the release once this ships.
