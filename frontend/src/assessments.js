// The tile describes the range's last week (spec §9): the latest assessment within the range,
// never one from before it. null = the series is never assessed, so the panel shows no tiles.
export function pickInRange(rows, range, latest) {
  if (!rows.length) return null
  // Two rows for one week means the query matched several series: no row describes this panel's one.
  if (new Set(rows.map((r) => r.period)).size !== rows.length) return { ambiguous: true }
  const row = rows
    .filter((r) => r.period >= range.from && r.period <= range.to)
    .reduce((best, r) => (!best || r.period > best.period ? r : best), undefined)
  return row ? { row, asOf: row.period, current: row.period === latest } : { row: undefined }
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

// A panel's {indicator, ...dimensions} against a phase stream's series, in any parameter order.
export function sameSeries(feed, params, stream) {
  const keys = Object.keys(stream.series)
  return feed === stream.feed && keys.length === Object.keys(params).length
    && keys.every((k) => params[k] === stream.series[k])
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
