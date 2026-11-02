This page explains how the dashboard reaches what it shows for Greece: which signals it pairs for each pathogen and
why, and how it grades them. The method follows Statens Serum Institut's integrated surveillance approach, run with
SSI's own aedseo software.

## Key signals

Each pathogen's season or wave is decided by two streams together: one tracking **community spread**, one tracking
the **load on the health system** (new hospital admissions), as SSI pairs laboratory-confirmed cases with
admissions. These are the streams this dashboard uses:

{{> streams}}

**What we would like, and what constrains it.** The community stream should track transmission in the community,
distinct from the admissions stream. COVID-19 uses wastewater in Attica and test positivity nationally. We would
prefer wastewater for influenza and RSV too: it doesn't depend on testing, and it would give Attica a local
influenza signal. But the reliability floor (CVₗₙ = 35%, Galani 2022) is validated only for the SARS-CoV-2 assay,
and 60–77% of influenza and RSV detections fall below even that floor, too noisy to start a season on. So influenza
uses sentinel positivity, which is national only, and RSV uses SARI positivity, available in both places. Attica
influenza has no community stream yet, so it has no season status.

{{> method}}

## For expert review

These points are flagged for EODY's and the surveillance experts' attention.

1. **The community stream for RSV.** Is SARI positivity an acceptable community proxy for RSV, or is a primary-care
   (sentinel) RSV measure preferable? SARI positivity is itself hospital-based, so RSV's two streams both sit on the
   severe side, weakening the contrast the two-stream rule depends on.
2. **A local community stream for Attica influenza.** Should Attica influenza get a locally available community
   stream (e.g. Attica SARI positivity) so its season can be flagged, accepting a different definition across the
   two areas?
3. **Wastewater for influenza and RSV.** Can influenza A/B and RSV get their own validated reliability floors, as
   SARS-CoV-2 has, or more sensitive assays, so their wastewater becomes usable as a community stream? That would
   also give Attica influenza the local signal it lacks.
4. **The surveillance year.** Influenza and RSV are graded within an ISO week {{surveillance.year_start_week}} →
   {{surveillance.year_end_week}} year. Is that window right for Greece, including post-pandemic RSV, which can spill
   outside a single winter peak? Do COVID-19's waves match EODY's own reading of the waves?
5. **COVID-19's community stream after mass testing.** Nationally it is test positivity, but testing volume and
   behaviour changed sharply once mass testing ended, while wastewater and admissions, which don't depend on
   testing, stayed robust. Should the national stream move to wastewater?
6. **The disease threshold and official thresholds.** aedseo estimates its own disease threshold; EODY's official
   disease-specific thresholds, if any, could validate or refine it.
7. **The 2025-W44 network change.** At week 44 of 2025, EODY switched from all hospitals in Greece to active
   surveillance of 84 hospitals. COVID-19 admissions therefore span a coverage break: current 84-hospital counts are
   graded against earlier all-hospital history, which can read as a decline. This is flagged, not corrected, until
   it is known exactly how membership changed across the hospital, sentinel and SARI networks. Influenza and RSV
   admissions begin at week 44 of 2025, wholly within the 84-hospital network.

## Sources for Greece's choices

- Statens Serum Institut, *Begrebsafklaring for integreret overvågning af luftvejsinfektioner* (December 2024).
- European Respiratory Virus Surveillance Summary (ECDC / WHO-Europe), <https://erviss.org/>.
