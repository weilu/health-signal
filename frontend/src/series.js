// Location plus every dimension except the series split; one line must hold one population.
// Blank and missing dimensions are the same.
function population(row, seriesBy) {
  const dims = Object.entries(row.dimensions ?? {}).filter(([d, v]) => d !== seriesBy && v !== '')
  return { location: row.location, ...Object.fromEntries(dims) }
}

function firstDifference(a, b) {
  return [...new Set([...Object.keys(a), ...Object.keys(b)])].sort().find((f) => a[f] !== b[f])
}

// Returns a status instead of a model when the rows can't make an honest chart.
export function toChartModel(rows, seriesBy, maxSeries) {
  if (!rows.length) return { status: 'empty' }
  const units = [...new Set(rows.map((r) => r.unit))].sort()
  if (units.length > 1) return { status: 'mixedUnits', units }  // one axis only
  const reported = [...new Set(rows.map((r) => r.period))].sort()  // ISO weeks sort as strings
  const periods = weekRange(reported[0], reported.at(-1))
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

const DAY = 86400000
const WEEK = 7 * DAY

// Monday (UTC ms) of an ISO week "YYYY-Www".
function weekStart(week) {
  const [year, n] = week.split('-W').map(Number)
  const jan4 = Date.UTC(year, 0, 4)  // always in ISO week 1
  return jan4 - ((new Date(jan4).getUTCDay() + 6) % 7) * DAY + (n - 1) * WEEK
}

function isoWeek(monday) {
  const thursday = new Date(monday + 3 * DAY)  // its year is the ISO year
  const year = thursday.getUTCFullYear()
  const n = Math.floor((thursday - Date.UTC(year, 0, 1)) / WEEK) + 1
  return `${year}-W${String(n).padStart(2, '0')}`
}

// Every week from first to last, so unreported weeks stay on the axis as gaps instead of closing up.
export function weekRange(first, last) {
  const weeks = []
  for (let t = weekStart(first); t <= weekStart(last); t += WEEK) weeks.push(isoWeek(t))
  return weeks
}

// Overlapping labels: draw none and let legend + tooltip carry identity (nudging detaches them).
export function endLabelsFit(ys, minGap) {
  const sorted = [...ys].sort((a, b) => a - b)
  return sorted.every((y, i) => i === 0 || y - sorted[i - 1] >= minGap)
}
