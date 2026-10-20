import { addWeeks, isWeek } from './weeks.js'

// Links between pages carry these, so switching page keeps the view.
const FILTER_PARAMS = ['location', 'range', 'from', 'to']

// In the URL so a regional view is deep-linkable; an unknown value falls back to the default.
export function selectedLocation(filter, search) {
  if (!filter) return null
  const wanted = new URLSearchParams(search).get('location')
  return filter.options.some((o) => o.value === wanted) ? wanted : filter.default
}

export function withFilters(path, search) {
  const kept = new URLSearchParams([...new URLSearchParams(search)].filter(([k]) => FILTER_PARAMS.includes(k)))
  return kept.size ? `${path}?${kept}` : path
}

// A null change removes the param.
export function updateSearch(search, changes) {
  const params = new URLSearchParams(search)
  for (const [k, v] of Object.entries(changes)) v == null ? params.delete(k) : params.set(k, v)
  return params.size ? `?${params}` : ''
}

const pad = (n) => String(n).padStart(2, '0')

// With years starting at W21, 2025-W10 belongs to the year that began in 2024.
function yearOf(week, startWeek) {
  const [year, n] = week.split('-W').map(Number)
  return n >= startWeek ? year : year - 1
}

export function yearLabel(year, startWeek) {
  return startWeek === 1 ? String(year) : `${year}–${String(year + 1).slice(2)}`
}

export function isCurrentYear(preset, filter, periods) {
  return preset === `year:${yearOf(periods.last, filter.year_start_week)}`
}

// Newest year first; the trailing window is dropped when all history is already the default.
export function rangePresets(filter, periods) {
  const start = filter.year_start_week
  const presets = filter.default_weeks === 'all' ? ['all'] : ['last', 'all']
  for (let y = yearOf(periods.last, start); y >= yearOf(periods.first, start); y--) presets.push(`year:${y}`)
  return presets
}

const clamp = (week, { first, last }) => (week < first ? first : week > last ? last : week)  // zero-padded: string order is chronological

function presetBounds(preset, filter, periods) {
  if (preset === 'all') return { from: periods.first, to: periods.last }
  if (preset === 'last') return { from: clamp(addWeeks(periods.last, 1 - filter.default_weeks), periods), to: periods.last }
  const year = Number(preset.slice('year:'.length))
  const from = `${year}-W${pad(filter.year_start_week)}`
  const to = addWeeks(`${year + 1}-W${pad(filter.year_start_week)}`, -1)  // a year with W53 keeps it
  return { from: clamp(from, periods), to: clamp(to, periods) }
}

// Presets stay relative in the URL, so a shared "last 52 weeks" link rolls forward with new data;
// a custom range is fixed weeks. Anything unreadable falls back to the default preset.
export function selectedRange(filter, periods, search) {
  if (!periods) return null
  const params = new URLSearchParams(search)
  const from = params.get('from')
  const to = params.get('to')
  if (isWeek(from) && isWeek(to)) {
    const [a, b] = [clamp(from, periods), clamp(to, periods)].sort()
    return { preset: 'custom', from: a, to: b }
  }
  const presets = rangePresets(filter, periods)
  const preset = presets.includes(params.get('range')) ? params.get('range') : presets[0]
  return { preset, ...presetBounds(preset, filter, periods) }
}

export function panelParams(query, location, range) {
  return {
    feed: query.feed, indicator: query.indicator, ...query.dimensions,
    ...(location ? { location } : {}),
    ...(range ? { week_from: range.from, week_to: range.to } : {}),
  }
}
