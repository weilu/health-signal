## How the dashboard grades

Each indicator is read on two axes:

- **Status**: how intense activity is now, compared with earlier seasons of the same indicator;
- **Trend**: whether it is rising or falling.

Both come from Statens Serum Institut's (SSI) **aedseo** method (*Automated and Early Detection of Seasonal
Epidemic Onset and Burden Levels*), evaluated across 21 European countries, run through its R package
(build {{method.build}}). Every week is graded from the data available up to that week, so a past week reads as it
would have at the time, and later data never rewrites it.

## How each indicator enters aedseo

aedseo takes either whole counts or a rate with its own denominator, which it uses as the exposure in its growth
model, so the trend is the trend of the rate itself rather than of the counts behind it.

{{> indicator_models}}

A rate with no denominator of its own is modelled against a constant exposure, which cancels out of the growth and
never enters the burden levels. A week with no value is a gap in the series, not a dropped row: the model's windows
count calendar weeks, so a reporting gap is never read as one week's change.

{{> censored}}

## Status: seasonal burden levels

Status grades the latest week against earlier **surveillance years** of the same indicator. aedseo fits a
log-normal distribution ({{method.burden_family}}) to the {{method.n_peak}} highest weekly values of each earlier year, weighting
recent years more (decay factor {{method.decay_factor}}), and sets the top boundary at the {{method.conf_levels}}
quantile of that fit. Its **disease threshold**, estimated from recent completed years, is the lowest boundary. The
boundaries partition activity into five levels; a week takes the level its value falls in.

{{> levels}}

The boundaries are set afresh at the start of each surveillance year, from the years before it. With fewer than
{{analytics.min_seasons}} completed years of history, a grade is marked **provisional**: the boundaries will still
move as years accrue.

## Trend: growth rate

The trend fits a quasi-Poisson model ({{method.onset_family}}) to the latest {{method.window_weeks}} weeks:

$$\log \mathbb{E}[y_t] = a + r\,t$$

where $r$ is the weekly growth rate, reported as a weekly change of $e^{r} - 1$. The trend is **increasing** when the
whole {{method.interval_percent}}% interval for $r$ lies above zero, **decreasing** when it lies below zero, and
**stable** when it contains zero. The tile shows that interval, since it alone decides the label. When too few
weeks in the window have a value to fit (a reporting gap, or a run of zeros), the trend is **inconclusive**.

## Seasons and their onset

A **surveillance year** runs from ISO week {{surveillance.year_start_week}} to week {{surveillance.year_end_week}}
of the next. A pathogen is graded either as one **season** a year or as **waves** through the year:

{{> phase_patterns}}

For one indicator, an **onset** needs both conditions in the same week: the average over its
{{method.window_weeks}}-week window is above the disease threshold, and its growth is significantly positive. A
season then lasts while the indicator stays above the threshold. It survives a dip below it of up to
{{phase.max_dip}} week, and a reporting gap of up to {{phase.max_missing}} weeks.

A pathogen is in season only while **both** of its streams are: one for community spread, one for the load on the
health system. Each starts on its own onset, and the pathogen's season is where their seasons overlap. Requiring
two independent streams guards against declaring a season on noise in one series.

## Waves

A pathogen graded as waves (one that circulates all year) has no single season. A wave starts on an onset in its
own week, judged with that week's data and threshold, and ends after {{analytics.aedseo.wave_end.steps_with_decrease}}
consecutive weekly decreases below the {{analytics.aedseo.wave_end.burden_level_decrease}} level. A week with no
value breaks a run of decreases, so a reporting gap never ends a wave; a wave carries across a gap of up to
{{phase.max_missing}} weeks. As with seasons, the pathogen is in a wave only while both of its streams are.

## References

- aedseo: *A method for robust estimation of seasonal onset and intensity in respiratory surveillance data:
  evaluated using data from 21 European countries* (medRxiv, 2025), <https://doi.org/10.1101/2025.11.18.25340240>;
  package <https://cran.r-project.org/package=aedseo>, source <https://github.com/ssi-dk/aedseo>.
- Wallinga J. & Lipsitch M. (2007), *How generation intervals shape the relationship between growth rates and
  reproductive numbers*, Proc. R. Soc. B 274:599–604.
