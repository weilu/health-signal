// Assessments are fetched over the whole history once; the range then only re-picks a row.
export function assessmentParams({ week_from, week_to, ...rest }) {
  return rest
}

// The tile describes the range's last week (spec §9): the latest assessment within the range,
// never one from before it. null = the series is never assessed, so the panel shows no tiles.
export function pickInRange(rows, range, latest) {
  if (!rows.length) return null
  const row = rows
    .filter((r) => r.period >= range.from && r.period <= range.to)
    .reduce((best, r) => (!best || r.period > best.period ? r : best), undefined)
  return row ? { row, asOf: row.period, current: row.period === latest } : { row: undefined }
}

// Ordered levels onto three tones by position, so any method's scale reads the same way.
export function levelTone(levels, level) {
  const position = levels.indexOf(level) / Math.max(levels.length - 1, 1)
  return position < 0.5 ? 'success' : position === 0.5 ? 'warning' : 'error'
}

export function activeWeeks(rows, activePhases) {
  return new Set(rows.filter((r) => activePhases.includes(r.phase)).map((r) => r.period))
}

// Each level's lower bound up to the next level's, the top one open-ended.
export function bandsFor(rows, levels) {
  const spans = new Map()
  for (const r of rows) {
    const key = `${r.from}|${r.to}`
    if (!spans.has(key)) spans.set(key, [])
    spans.get(key).push(r)
  }
  return [...spans.values()].flatMap((span) => {
    const sorted = [...span].sort((x, y) => levels.indexOf(x.level) - levels.indexOf(y.level))
    return sorted.map((r, i) => ({
      from: r.from, to: r.to, level: r.level, lower: r.lower_bound, upper: sorted[i + 1]?.lower_bound ?? Infinity,
    }))
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
