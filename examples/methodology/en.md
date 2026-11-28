{{> method.overview}}

{{> method.status}}

{{> method.trend}}

{{> method.seasons}}

The community-spread stream is a single designated series per location, not a combination. For COVID-19 it is
location-specific: wastewater in Attica, since there is no Attica test-positivity denominator, and test positivity
nationally.

**What we would like, and what constrains it.** The community-spread stream should track *community transmission*,
distinct from the health-system-load stream. COVID-19 uses wastewater (Attica) and test positivity (national). We
would prefer wastewater for influenza and RSV too, as it is test-independent and would give Attica a local influenza
signal, but the reliability floor (CVₗₙ = 35%, Galani 2022) is validated only for the SARS-CoV-2 assay, and **60–77%
of influenza and RSV detections fall below even that COVID floor**, too noisy to gate a season on. So influenza uses
**sentinel (ILI) positivity** and RSV uses **SARI positivity** (available in both places). Attica influenza cannot
yet flag in-season: sentinel positivity is national-only, and its local substitute, Attica influenza wastewater, is
not yet reliable.

**Open questions for the experts (community-spread stream).**

1. Is SARI positivity an acceptable community proxy for RSV, or is a primary-care (sentinel) RSV measure
   preferable? SARI positivity is itself hospital-based, so RSV's two streams both sit on the severe side, weakening
   the community-versus-severity contrast the two-stream rule depends on.
2. Should Attica influenza be given a locally available community stream (e.g. Attica SARI positivity) so its flag
   can operate, accepting a mixed definition across the two places?
3. *For the wastewater team:* can influenza A/B and RSV get their own validated reliability floors (as SARS-CoV-2
   has), or more sensitive assays, so their wastewater becomes usable as a community stream? That would also give
   Attica influenza the local signal it lacks.

{{> method.waves}}

For COVID-19 the wave-boundary parameters were tuned on the Greek COVID series to separate the real waves (e.g. the
2025 summer and autumn waves) without single-week noise.

{{> method.indicators}}

## For expert review

The overall approach should be reviewed by EODY and surveillance experts. The method is established by SSI's
aedseo [2], so the dashboard does not wait on their input, but the following points are flagged for their
attention.

1. **Pathogen framing.**
   - **Season or wave.** Influenza and RSV are graded within an ISO week {{surveillance.year_start_week}} →
     {{surveillance.year_end_week}} season. Is that window right for Greece, including post-pandemic RSV, which can
     spill outside a single winter peak? SARS-CoV-2, being year-round, is shaded as discrete **waves**: do the
     identified waves match EODY's reading of the real COVID waves? The wave-boundary parameters are tunable if not.
   - **COVID's community stream after mass testing.** Nationally it is test positivity, but testing volume and
     behaviour shifted sharply once mass testing ended, so positivity may no longer track community transmission the
     way it did in 2021/22, while wastewater and admissions, being test-independent, stayed robust (Attica already
     uses wastewater). Should the national COVID stream move off positivity toward wastewater?
2. **The disease threshold versus official thresholds.** The disease threshold is estimated by
   `aedseo::estimate_disease_threshold`; EODY's official disease-specific thresholds, if any, could refine or
   validate it later.
3. **Surveillance-network change (2025-W44).** EODY switched from *all hospitals across Greece* to **active
   surveillance of 84 hospitals** at week 44 of 2025. COVID-19 hospital admissions therefore span a **coverage
   break**: aedseo grades current 84-hospital counts against pre-W44 all-hospital history, which are not comparable,
   so the coverage drop can read as a decline and shift COVID's wave bands. This is **flagged, not corrected**: the
   chart subtitle notes the break, and the series is still fitted as one. The adjustment (split or rebase at the
   break, or scale to a common coverage) waits until it is known exactly how membership changed across the
   hospital, sentinel and SARI networks. Influenza and RSV admissions begin at week 44 of 2025, wholly within the
   84-hospital network, so they have no break.

{{> method.references}}
