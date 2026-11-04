<!-- section: overview -->
## Overview

The dashboard can grade each indicator with the **Moving Epidemic Method** (MEM) [1, 2], the method ERVISS uses to
set countries' epidemic and intensity thresholds for influenza-like illness (ILI) and acute respiratory infection
(ARI) rates [4]. MEM was built for ILI and ARI consultation rates; a deployment may apply it to other indicators,
which it then grades the same way.

MEM assumes one epidemic a season, so it doesn't grade pathogens that circulate year-round in waves:
{{method.not_graded}}. For those, the dashboard's grades are aedseo's alone.

Each season's thresholds come from up to {{method.seasons}} complete seasons before it, in MEM's own season window,
ISO week {{method.season_start_week}} → {{method.season_end_week}}, and stay fixed for the whole season: every week
is graded from history only, as it would have been at the time. The fit uses the R package mem [3] (build
{{method.build}}).

<!-- section: status -->
## Status: epidemic and intensity levels

For each past season MEM locates the epidemic, the run of weeks holding most of the season's activity (its timing
parameter is {{method.epidemic_param}}%). From the weeks before each past epidemic it sets the **epidemic
threshold**; from the highest weeks during them, three **intensity thresholds**, at the {{method.intensity_levels}}
levels. Together they give five levels:

{{> levels}}

A week below the epidemic threshold is at **baseline**. Above it, the week takes the highest intensity level it
reaches. After seasons with small epidemics, an intensity threshold can come out below the epidemic threshold; a week
above the epidemic threshold is then at least at that intensity level, as MEM grades it.

With fewer than {{analytics.min_seasons}} complete seasons behind its thresholds, a grade is marked
**provisional**. Without enough history for MEM to fit at all, the week isn't graded.

<!-- section: seasons -->
## Season

A pathogen is **in season** under MEM while both its streams, community spread and health-system load, are in an
epidemic, as with aedseo's seasons [5]. A stream enters one in the week it reaches its epidemic threshold, and stays
while above it, across a lull of up to {{phase.max_dip}} week below it or a reporting gap of up to
{{phase.max_missing}} weeks. Until both streams have enough history for MEM, the pathogen's season isn't
determined. The two streams for each pathogen are:

{{> streams}}

<!-- section: trend -->
## Trend: change since last week

From the same past seasons MEM sets two limits for the change from one week to the next [3]: a rise larger than the
first is **increasing**, a fall larger than the second is **decreasing**, and anything in between is **stable**.

MEM assesses the trend only during an epidemic: above the epidemic threshold, plus the first week above it
(increasing) and the first week back below it (decreasing). Below the threshold, and in a week after one without
data, the trend is **not assessed**. Unlike a growth rate, MEM's trend has no confidence interval.

<!-- section: references -->
## References

1. Vega T, Lozano JE, Meerhoff T, et al. *Influenza surveillance in Europe: establishing epidemic thresholds by the
   moving epidemic method.* Influenza Other Respir Viruses. 2013;7(4):546–58.
   <https://doi.org/10.1111/j.1750-2659.2012.00422.x>
2. Vega T, Lozano JE, Meerhoff T, et al. *Influenza surveillance in Europe: comparing intensity levels calculated
   using the moving epidemic method.* Influenza Other Respir Viruses. 2015;9(5):234–46.
   <https://doi.org/10.1111/irv.12330>
3. Lozano JE. *mem: The Moving Epidemic Method* (R package). <https://cran.r-project.org/package=mem>
4. European Respiratory Virus Surveillance Summary (ECDC / WHO-Europe), Methods: MEM thresholds. <https://erviss.org/>
5. Statens Serum Institut, *Begrebsafklaring for integreret overvågning af luftvejsinfektioner* (December 2024).
