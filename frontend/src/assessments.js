// The tile describes the range's last week (spec §9): the latest assessment within the range,
// never one from before it. null = the series is never assessed, so the panel shows no tiles.
export function pickInRange(rows, range, latest) {
  if (!rows.length) return null
  // Two rows for one week, or rows of several locations or dimension values (even in disjoint weeks), are several
  // series: no row describes this panel's one, and one series' weeks aren't another's history.
  if (new Set(rows.map((r) => r.period)).size !== rows.length || !singleSeries(rows)) {
    return { ambiguous: true }
  }
  const row = rows
    .filter((r) => r.period >= range.from && r.period <= range.to)
    .reduce((best, r) => (!best || r.period > best.period ? r : best), undefined)
  return row ? { row, asOf: row.period, current: row.period === latest } : { row: undefined }
}

// The one series a panel's data rows plot (its location and dimensions); { mixed: true } when they mix several
// (the chart warns about that itself), null when there are none.
export function plottedSeries(rows) {
  if (!rows?.length) return null
  // Data mixing several series has no one series' status or bands to show.
  if (!singleSeries(rows)) return { mixed: true }
  const dims = Object.entries(rows[0].dimensions ?? {}).filter(([k, v]) => rows.every((r) => r.dimensions?.[k] === v))
  return { location: rows[0].location, dimensions: Object.fromEntries(dims) }
}

// Whether a lookup row (assessment, threshold) belongs to the plotted series: same location and the same value of
// every dimension either carries. Blank equals missing, but missing is never a wildcard: fraction=liq isn't a
// series with no fraction.
export function ofSeries(row, series) {
  const mine = row.dimensions ?? {}
  return row.location === series.location
    && [...new Set([...Object.keys(mine), ...Object.keys(series.dimensions)])]
      .every((k) => (mine[k] ?? '') === (series.dimensions[k] ?? ''))
}

// Whether rows (assessments, thresholds) all belong to one series: one location, one set of dimensions.
export function singleSeries(rows) {
  const key = (r) => `${r.location}|${JSON.stringify(Object.entries(r.dimensions ?? {}).filter(([, v]) => v !== '').sort())}`
  return new Set(rows.map(key)).size <= 1
}

// Ordered levels onto three tones by position, so any method's scale reads the same way. An ungraded
// week is neutral: the lowest tone would read as "all clear".
export function levelTone(levels, level) {
  if (!levels.includes(level)) return 'neutral'
  const position = levels.indexOf(level) / Math.max(levels.length - 1, 1)
  return position < 0.5 ? 'success' : position === 0.5 ? 'warning' : 'error'
}

export function activeWeeks(rows, activePhases) {
  return new Set(rows.filter((r) => activePhases.includes(r.phase)).map((r) => r.period))
}

// Each level's lower bound up to the next level's, the top one open-ended. Thresholds give lower bounds
// from the second level on, so the lowest level runs from the axis bottom: without it, the commonest
// state reads as unexplained white space.
export function bandsFor(rows, levels) {
  const spans = new Map()
  for (const r of rows) {
    const key = `${r.from}|${r.to}`
    if (!spans.has(key)) spans.set(key, [])
    spans.get(key).push(r)
  }
  return [...spans.values()].flatMap((span) => {
    const sorted = [...span].sort((x, y) => levels.indexOf(x.level) - levels.indexOf(y.level))
    const bands = sorted.map((r, i) => ({
      from: r.from, to: r.to, level: r.level, lower: r.lower_bound, upper: sorted[i + 1]?.lower_bound ?? Infinity,
    }))
    const lowest = levels.find((l) => !span.some((r) => r.level === l) && levels.indexOf(l) < levels.indexOf(sorted[0].level))
    return lowest ? [{ from: sorted[0].from, to: sorted[0].to, level: lowest, lower: -Infinity, upper: sorted[0].lower_bound }, ...bands] : bands
  })
}

// "Since W48": the start of the unbroken active run that reaches the as-of week.
export function phaseSince(rows, asOf, activePhases) {
  const sorted = rows.filter((r) => r.period <= asOf).sort((x, y) => (x.period < y.period ? -1 : 1))
  if (!sorted.length || !activePhases.includes(sorted.at(-1).phase)) return null
  let i = sorted.length - 1
  while (i > 0 && activePhases.includes(sorted[i - 1].phase)) i--
  return sorted[i].period
}

// The runs of active weeks overlapping the range (the stream charts' shaded bands, as a list): each run keeps
// its true start and end, flagged where the range clips it, and is ongoing when it reaches the latest row.
// Rows are consecutive weeks, as phaseSince reads them.
export function phaseRuns(rows, range, activePhases) {
  const sorted = [...rows].sort((x, y) => (x.period < y.period ? -1 : 1))
  const runs = []
  let run = null
  for (const r of sorted) {
    if (activePhases.includes(r.phase)) {
      run = run ? { ...run, to: r.period, weeks: run.weeks + 1 } : { from: r.period, to: r.period, weeks: 1 }
    } else if (run) {
      runs.push(run)
      run = null
    }
  }
  if (run) runs.push({ ...run, ongoing: true })
  return runs
    .filter((x) => x.to >= range.from && x.from <= range.to)
    .map((x) => ({ from: x.from, to: x.to, weeks: x.weeks, startsBefore: x.from < range.from, endsAfter: x.to > range.to,
                   ongoing: !!x.ongoing }))
}

// A panel's {indicator, ...dimensions} against a phase stream's series. Only the values the query states must
// agree: a stream also pins the dimensions a single-series query leaves implicit.
export function sameSeries(feed, params, stream) {
  return feed === stream.feed && Object.entries(params).every(([k, v]) => stream.series[k] === v)
}

// Levels sharing a tone step darker in level order, so e.g. very low and low stay distinguishable.
export function bandAlpha(levels, level) {
  const tone = levelTone(levels, level)
  const rank = levels.filter((l) => levelTone(levels, l) === tone).indexOf(level)
  return 0.1 + 0.08 * Math.max(rank, 0)
}

export function toneColor(tone) {
  return tone === 'neutral' ? 'grey.500' : `${tone}.main`
}

// The summary's lookups as one state, by ResourceBoundary's rules: a 401 redirects, any lookup still
// pending shows loading, and a failure is an error rather than "nothing assessed".
export function combinedState(results) {
  if (results.some((r) => r.error?.status === 401)) return 'unauth'
  if (results.some((r) => r.data === undefined && r.isPending)) return 'loading'
  if (results.some((r) => r.data === undefined)) return 'error'
  return 'ok'
}
