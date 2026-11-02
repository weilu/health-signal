<!-- section: overview -->
## Overview

The dashboard presents an interpretation of each indicator on two axes:

- **Status**: how intense activity is at present, relative to earlier seasons; and
- **Trend**: whether activity is rising or falling.

Both axes are computed for **every** indicator by Statens Serum Institut's (SSI) aedseo package [2], the
*Automated and Early Detection of Seasonal Epidemic Onset and Burden Levels* method, published and evaluated across
21 European countries. In that evaluation aedseo detected season onset earlier than the conventional Moving Epidemic
Method (MEM) and its relatives (WHO-ACM, MSD), and graded intensity more consistently across seasons than all
three [2]; and unlike MEM its bands are disease-specific and weight recent seasons, so an unusually high or low past
season does not destabilise the onset threshold [1]. On the Status axis aedseo assigns each weekly indicator a
five-level seasonal-burden grade (*very low, low, medium, high, very high*), shown as wording with a corresponding
traffic-light colour dot; on the Trend axis aedseo's growth-rate model labels the indicator *increasing, stable,* or
*decreasing*. The two axes are orthogonal (one measures level, the other change) and mirror aedseo's own separation
of `seasonal_burden_levels` (intensity) from `seasonal_onset` (growth), the same split ERVISS/ECDC use when they
publish intensity and trend independently [4].

For each pathogen the dashboard additionally flags whether it is **in season** (for a pathogen that circulates
year-round, **in a wave**; see *Waves*). This draws on both axes for two indicators at once: a community-spread
stream and a health-system-load stream must each independently cross the elevated Status floor while rising in
Trend, and the flag remains on while the resulting runs overlap.

Every week is graded **as of that week**, from the data available up to it, so a past week reads as it would have at
the time. The method follows SSI's integrated-surveillance approach [1], implemented through SSI's own aedseo
software [2] (build {{method.build}}). The key parameters are `n_peak` = {{method.n_peak}}, `conf_levels` =
{{method.conf_levels}}, and an ISO-week {{surveillance.year_start_week}} → {{surveillance.year_end_week}}
**surveillance year** (the annual window defined under *Season and season onset*; "in season" is reserved for a
pathogen's active phase within that year).

<!-- section: status -->
## Status: seasonal burden levels

Status grades the latest week against the distribution of *previous* seasons rather than a fixed rolling window, so a
reading is judged high or low for this indicator at this point in its own seasonal history.
`aedseo::seasonal_burden_levels` fits a log-normal distribution (`{{method.burden_family}}`) to each past
surveillance year's peak activity (the `n_peak` = {{method.n_peak}} highest weekly observations per year, weighted
toward recent years by `decay_factor` = {{method.decay_factor}}) and returns four ascending burden thresholds, with
the high/very-high boundary at the `conf_levels` = {{method.conf_levels}} quantile of the fitted distribution (a
direct percentile, not a two-sided confidence level). These are the values the aedseo paper validated across 21
countries. The disease threshold, from `aedseo::estimate_disease_threshold`, anchors the lowest boundary. Together
the four thresholds partition activity into the five bands; the week is assigned to whichever band contains its
value. The thresholds are set afresh at the start of each surveillance year, from the years before it.

When an indicator has fewer than {{analytics.min_seasons}} completed surveillance years of history the bands are
still produced but the Status is flagged **provisional**, since the thresholds will shift as more years accrue; this
reflects data depth alone, not the method. A series aedseo cannot grade degrades gracefully: a week whose fit
returns no usable thresholds is shown as **"Very low"** if its value is zero, which is definitionally the lowest
burden, and as **"Not graded"** otherwise.

All five levels are computed and shown as wording; the traffic-light dot collapses them to three colours, so the
dashboard reads at a glance without discarding the finer grading beneath it:

{{> levels}}

<!-- section: trend -->
## Trend: aedseo growth rate

The Trend axis comes from `aedseo::seasonal_onset`, which fits a quasi-Poisson generalised linear model
(`{{method.onset_family}}`) to the trailing `k` = {{method.window_weeks}} weeks,

$$\log \mathbb{E}[y_t] = a + r\,t,$$

where the slope $r$ is the weekly log growth rate, reported as a per-week percentage, $e^{r} - 1$. The indicator is
labelled *increasing* when the lower bound of the {{method.interval_percent}}% confidence interval for $r$ lies
above zero (growth that is both positive and statistically significant), *decreasing* when the upper bound lies below
zero, and *stable* otherwise. The Trend tile therefore shows that interval rather than the point estimate, since the
interval alone decides the label. An off-season week, or a window with too few weeks of data, can legitimately
return a non-estimable growth; this is shown as **"Inconclusive"**, not an error. The growth rate is a standard early
epidemic indicator, the quantity that links the speed of spread to the reproductive number [3].

<!-- section: seasons -->
## Season and season onset

The **surveillance year** is aedseo's season window: ISO weeks **{{surveillance.year_start_week}} →
{{surveillance.year_end_week}}** of the following year. We name this annual window the *surveillance year* to keep
it distinct from a pathogen being *in season* (its active phase within the year). It suits a single winter peak best;
a pathogen that circulates year-round is shaded as discrete waves instead (see *Waves*):

{{> phase_patterns}}

Onset is declared only on a conjunction, not on a level crossing alone and not on growth alone: the start of a
**season**, or of a **wave**. For a single indicator the onset flag is aedseo's `seasonal_onset_alarm` [2], which
requires both that the average over its {{method.window_weeks}}-week window is at or above the disease threshold
(the burden floor) and that its growth rate is significantly positive. At the pathogen level, following SSI's joint
use of laboratory-confirmed cases and admissions [1], the flag requires a **community-spread stream** and a
**health-system-load stream** to be in season together, the same two-stream AND in both modes. Each stream onsets on
its own elevated-and-rising crossing, and the shared band is where their two in-season runs overlap, not a
week-by-week re-test that both are still rising, so a stream that onset earlier and is now plateauing still counts
while it stays above the floor. Requiring two streams guards against declaring on noise in a single series.

The season **band**, the shaded run on the charts, starts at the first onset week (it is not backdated to an earlier
floor-crossing) and continues while the stream stays above the floor. To keep one continuous band across brief
interruptions rather than fragmenting it, the run **bridges** a short below-floor lull (≤ {{phase.max_dip}} week) and
a fully-missing reporting gap (≤ {{phase.max_missing}} weeks). A longer silence is not bridged: the band ends and the
phase reverts to undetermined until reporting resumes. This is a deliberate continuity rule, distinct from the
two-stream elevated-and-rising test that governs onset itself; it never invents an onset, only spans a gap inside an
already-started season.

The two streams used for each pathogen (shared by the season and wave rollups) are:

{{> streams}}

<!-- section: waves -->
## Waves

A pathogen that circulates year-round with no clean off-season trough fits the single bounded-season model poorly:
its activity sits above the low-burden floor most of the year, so an above-floor onset run would shade almost the
whole year as "in season", which marks "the pathogen is present", not a season. This mirrors SSI's own practice: its
dashboard-method document [1] states that COVID-19 is "followed as a virus that can cause waves of infection
year-round".

For such a pathogen the dashboard shades discrete **waves** instead. aedseo's
`combined_seasonal_output(multiple_waves = TRUE)` segments the growth curve into waves. Because it replays the whole
history with the current week's disease threshold, a lower threshold could place a wave's start in the past where no
week, as of itself, flagged one; so a wave **starts only on an onset alarm in its own week**, and then lasts while
aedseo keeps it, across a reporting gap of up to {{phase.max_missing}} weeks. Wave boundaries use
`steps_with_decrease` = {{analytics.aedseo.wave_end.steps_with_decrease}} (a wave closes only after that many
consecutive weeks of decline, robust to noise) and `burden_level_decrease` =
{{analytics.aedseo.wave_end.burden_level_decrease}} (it closes when activity falls back to that burden level, so
back-to-back peaks separate rather than merge). A week with no value breaks a run of declines, so a reporting gap
never ends a wave. The **two-stream AND still applies**: a wave is shaded only where both streams are in a wave,
keeping the band conservative and descriptive. The badge reads **"In a wave" / "Between waves"** rather than
"In season" / "Out of season". Whether a pathogen is shaded as waves or as a season is a fixed property of the
pathogen, not a per-run decision.

<!-- section: indicators -->
## How each indicator enters aedseo

aedseo's time-series object accepts either **integer counts** or **per-denominator incidence** (with a population and
an incidence denominator). On the incidence path the supplied population is aedseo's **Poisson exposure offset**:
`seasonal_onset` fits `glm(cases ~ week + offset(log(population)))`, so the estimated growth is of **cases ÷
population, the rate itself**, with count-based (quasi-Poisson) uncertainty on the numerator, while burden is graded
on the incidence (display) scale. The dashboard's indicators split along that seam:

{{> indicator_models}}

**Why the count/incidence split.** The distinction reflects what the growth model needs. Case counts (admissions,
ICU, deaths) grow multiplicatively through a wave and are Poisson-appropriate directly, so they enter as counts. A
rate or test positivity is a *proportion*: the standard way to estimate its growth is Poisson/quasi-Poisson
regression of the numerator with the denominator as an `offset(log(·))`, exactly aedseo's incidence path, which
gives the growth of the proportion with count-appropriate uncertainty rather than treating a percentage as Gaussian.
Using each indicator's real at-risk base (tests, admissions, consultations) as that offset is what makes the estimate
the growth of the *rate*; a census population would model a meaningless quantity, since the numerator is only
observed within the surveilled denominator.

A rate or load with no denominator of its own, such as wastewater already normalised per inhabitant, still needs a
population for the incidence path, but because the observation is per-capita the offset is **inert**: a constant
cancels out of the growth and never enters the burden levels.

A week with a missing denominator, or with no value at all (e.g. a reporting outage), is kept in the series as a
**gap**, not dropped: aedseo's windows count rows, so dropping it would make the weeks either side look adjacent and
report the change across the gap as one week's growth. A gap week is fitted as missing and not graded.

{{> censored}}

<!-- section: references -->
## References

1. Statens Serum Institut, *Begrebsafklaring for integreret overvågning af luftvejsinfektioner* (December 2024).
2. aedseo: *A method for robust estimation of seasonal onset and intensity in respiratory surveillance data:
   evaluated using data from 21 European countries* (medRxiv, 2025), <https://doi.org/10.1101/2025.11.18.25340240>.
   CRAN package: <https://cran.r-project.org/package=aedseo>; source: <https://github.com/ssi-dk/aedseo>.
3. Wallinga J. & Lipsitch M. (2007), *How generation intervals shape the relationship between growth rates and
   reproductive numbers*, Proc. R. Soc. B 274:599–604. <https://royalsocietypublishing.org/doi/10.1098/rspb.2006.3754>
4. European Respiratory Virus Surveillance Summary (ECDC / WHO-Europe). <https://erviss.org/>
