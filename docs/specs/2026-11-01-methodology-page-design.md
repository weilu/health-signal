# Methodology page — design

Replaces the dashboard's Configuration page with a **Methodology** page that each deployment writes for its
own readers, in Markdown, with placeholders the app fills from the deployment's live settings.

## Intent

The readers are epidemiologists and officials (e.g. at EODY or a ministry) who want to know **how the dashboard
reaches what it shows**: how each pathogen's key signals were chosen, how Status and Trend are graded, and when a
pathogen counts as in season or in a wave. greece-public-health answers this today in
`modeling/STATUS_TREND_METHODOLOGY.md`; this page brings that into the dashboard, configurable per deployment,
and later covers MEM too when it is added.

The Configuration page it replaces shows config to readers who can't act on it. The settings that matter to a
reader belong on the Methodology page, in context, as prose and tables.

## Goals

- A deployment writes its own methodology page as Markdown files in its repository, one per offered language.
  No in-app editor.
- The page can embed **values and tables drawn from the deployment's settings**, so what it says can't drift
  from what the dashboard does.
- The library ships a **general method text** (how its method grades), which uses the same placeholders so it
  reads correctly for any deployment's settings. A deployment can include it where it wants, or leave it out and
  write its own entirely.
- A deployment that writes nothing gets the library's general method page alone.

## Non-goals

- An in-app editor, or editing by epidemiologists inside the app.
- Raw HTML in the Markdown.
- Public (pre-login) access: the page sits behind login like the rest of the dashboard.
- A list of indicators per pathogen: each pathogen's summary table already shows it.

## Anti-goals

- Text that silently contradicts the dashboard's settings (the reason for placeholders).
- A typo in a placeholder that reaches readers as raw `{{…}}` text.

## Decided (with the user)

- **Layout B:** a contents list on the left, built from the page's headings, marking where the reader is; the text
  on the right. Collapses to a single column on a phone.
- **Settings-filled parts stand out:** generated blocks sit in a shaded box with an amber left edge and a small
  caption (e.g. "This dashboard's streams"); inline values carry a light shade and dotted underline. The rest is
  the deployment's prose, unmarked.
- **Where it goes:** "Configuration" in the top bar becomes "Methodology"; the Configuration page and its route
  are removed, and the old `/config` route redirects to the Methodology page.
- **Library ships general text; a deployment includes it or replaces it entirely.**
- **The streams table** shows "Not configured" for a pathogen and location with no streams (e.g. Attica
  influenza).
- **Embeddable content** (from the user's list plus a check of STATUS_TREND_METHODOLOGY.md):
  - values: the surveillance year's start and end weeks, `min_seasons`, the burden-level parameters (`n_peak`,
    `conf_levels`, `decay_factor`, lognormal), the trend window (`k`) and interval (95%), the wave-end rule
    (`steps_with_decrease`, `burden_level_decrease`), the gap bridging (a 1-week dip, a reporting gap of up to 8
    weeks), and the aedseo build used for the current tables;
  - blocks: the streams table (community and admissions stream per pathogen and location, named as the panels
    are on the tabs); season or wave per pathogen; how each kind of indicator enters aedseo; censored qualities
    fitted as gaps; the five levels and their three colours.
- **How indicators enter aedseo: one row per rule**, from the configured feeds' profiles, not one row per
  indicator. The code decides count, rate or constant exposure from each data row's unit, which config doesn't
  hold, so a per-indicator table would make the page depend on the data. Rows read e.g. "counts (unit `count`) →
  counts"; "test positivity → a rate of tests, per 100"; "SARI rate per 1,000 admissions → a rate of admissions,
  per 1,000"; "any other rate or load → a constant exposure", named with the library's labels.
- **One PR.** The user reviews its logic; the Markdown texts (library and example) are prose read separately, so
  the size cap is not a reason to split it.

## Decided (by me; the user agreed to the outline)

- **Files:** `site.methodology_dir` holds `<language>.md` per offered language, like `site.locales_dir`. Startup
  checks match the locale files: a missing or unreadable file for an offered language, or an unknown placeholder,
  stops the app with a message naming the file and the placeholder. Without `methodology_dir`, the page is the
  library's general text alone.
- **Placeholder syntax**, double braces as the subtitles already use:
  - values inline: `{{surveillance.year_start_week}}`, `{{analytics.min_seasons}}`, etc.;
  - blocks on a line of their own: `{{> streams}}`, `{{> indicator_models}}`, `{{> phase_patterns}}`,
    `{{> censored}}`, `{{> levels}}`;
  - the library's general text for the method in use: `{{> method}}`.
  The full set of names is fixed by the library and listed in the README.
- **Rendering:** CommonMark plus GFM tables, in the browser. Raw HTML is not rendered. Headings (`##`, `###`)
  build the contents list and get anchors.
- **Where values come from:**
  - config: `surveillance.year_start_week`, `analytics.*`, `analytics.phase_streams`, panels, profiles;
  - the method's own parameters (`n_peak`, `conf_levels`, `decay_factor`, `k`, the interval level): today they
    live in `analytics/aedseo_r.py` (`_ONSET`, `_BURDEN`), which the app doesn't import. They move into the method
    definition in `methods.py`, and `aedseo_r.py` reads them from there, so there is one source and the app can
    show them without R;
  - the gap bridging constants (`MAX_DIP`, `MAX_MISSING` in `analytics/rules.py`), likewise exposed without R;
  - the aedseo build: the `package_version` the assessments' `assessed_with.csv` records (one per feed; if feeds
    disagree, all are shown).
- **Generated blocks use the app's own names:** the streams table names each stream as its panel is named on the
  tab, and pathogens and locations as the header does, in the reader's language. So the server sends the
  Markdown with values filled in and each block's data (ids and label keys, not text), and the browser renders
  the blocks with the same labelling functions the tabs use.
- **Library text** ships in English and Greek, adapted from STATUS_TREND_METHODOLOGY.md's general sections (how
  indicators enter aedseo, Status, Trend, season and onset, waves), with every setting as a placeholder and
  nothing Greece-specific. A deployment language the library doesn't ship falls back to the English library
  text, as the rest of the interface does.
- **The Greece example** gets `examples/methodology/en.md` and `el.md`: the note's Greece-specific parts (stream
  choices and their constraints, the open questions for the experts, the 2025-W44 network change, references),
  around `{{> method}}` and the blocks. Its content comes from STATUS_TREND_METHODOLOGY.md, nothing invented.
  Where the note and the code differ, the text follows the code (e.g. ILI's exposure is the example's
  `consultations` indicator, not "cases × 1000 ÷ rate"), since text contradicting the dashboard is an anti-goal.
- **Serving:** `GET /api/methodology/{language}` behind login, like `/api/locales/{language}`.

## Constraints

- One PR, branched from `feat/profile-extensions` (#14). Its code and tests should stay as small as the work
  allows; the Markdown texts don't count toward that.
- The library's usual rules: test-first; comments say why only; no tests that restate constants; synthetic data
  only in the repo.
- The spec (`docs/specs/2026-09-23-reusable-surveillance-dashboard-design.md`, §9) gains the page; the README
  documents `methodology_dir` and the placeholder names.

## Left to the builder

- The Markdown renderer (e.g. react-markdown with remark-gfm), and how block markers travel from server to
  browser.
- The exact block captions and the table columns beyond those named above.
- How the contents list tracks the reader's position.
- Placeholder names beyond the examples above, kept consistent with config paths where one exists.
