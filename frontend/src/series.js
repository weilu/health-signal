// Rows -> the model one panel plots: one series per value of `seriesBy`, values aligned to the sorted
// week axis. Returns a status instead when the rows can't make an honest chart.
export function toChartModel(rows, seriesBy, maxSeries) {
  if (!rows.length) return { status: 'empty' }
  const units = [...new Set(rows.map((r) => r.unit))].sort()
  if (units.length > 1) return { status: 'mixedUnits', units }  // one axis only
  const periods = [...new Set(rows.map((r) => r.period))].sort()  // ISO weeks sort as strings
  const byKey = new Map()
  for (const r of rows) {
    const key = seriesBy ? (r.dimensions?.[seriesBy] ?? '') : ''
    if (!byKey.has(key)) byKey.set(key, new Map())
    const points = byKey.get(key)
    // Two rows for one series-week means the query is too broad (e.g. subtypes alongside totals).
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
