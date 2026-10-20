import { weekRange } from './weeks.js'

// Every dimension except the series split; one line must hold one population. Blank and missing
// dimensions are the same.
function population(row, seriesBy) {
  return Object.fromEntries(Object.entries(row.dimensions ?? {}).filter(([d, v]) => d !== seriesBy && v !== ''))
}

function firstDifference(a, b) {
  return [...new Set([...Object.keys(a), ...Object.keys(b)])].sort().find((f) => a[f] !== b[f])
}

// Returns a status instead of a model when the rows can't make an honest chart.
// `span` is the selected range: panels on a page share one axis, and late-starting data shows as a gap.
export function toChartModel(rows, seriesBy, maxSeries, span) {
  if (!rows.length) return { status: 'empty' }
  const units = [...new Set(rows.map((r) => r.unit))].sort()
  if (units.length > 1) return { status: 'mixedUnits', units }  // one axis only
  // Panel-wide, unlike dimensions (subtypes differ in pathogentype): series labels never name the location.
  if (new Set(rows.map((r) => r.location)).size > 1) return { status: 'mixedSeries', field: 'location' }
  const reported = [...new Set(rows.map((r) => r.period))].sort()  // ISO weeks sort as strings
  const periods = span ? weekRange(span.from, span.to) : weekRange(reported[0], reported.at(-1))
  const byKey = new Map()
  const populations = new Map()
  for (const r of rows) {
    const key = seriesBy ? (r.dimensions?.[seriesBy] ?? '') : ''
    if (!byKey.has(key)) { byKey.set(key, new Map()); populations.set(key, population(r, seriesBy)) }
    // In disjoint weeks two populations never collide on a week, so compare them directly.
    const field = firstDifference(populations.get(key), population(r, seriesBy))
    if (field) return { status: 'mixedSeries', key, field }
    const points = byKey.get(key)
    // Two rows per series-week: the query is too broad (e.g. subtypes alongside totals).
    if (points.has(r.period)) return { status: 'ambiguous', key, period: r.period }
    points.set(r.period, r.value)
  }
  if (byKey.size > maxSeries) return { status: 'tooManySeries', count: byKey.size }
  const keys = [...byKey.keys()].sort((a, b) => (a === '') - (b === '') || a.localeCompare(b))
  return {
    status: 'ok', unit: units[0], periods,
    series: keys.map((key) => ({ key, values: periods.map((p) => byKey.get(key).get(p) ?? null) })),
  }
}

// Overlapping labels: draw none and let legend + tooltip carry identity (nudging detaches them).
export function endLabelsFit(ys, minGap) {
  const sorted = [...ys].sort((a, b) => a - b)
  return sorted.every((y, i) => i === 0 || y - sorted[i - 1] >= minGap)
}
