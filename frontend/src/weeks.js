const DAY = 86400000
const WEEK = 7 * DAY

// Monday (UTC ms) of an ISO week "YYYY-Www".
export function weekStart(week) {
  const [year, n] = week.split('-W').map(Number)
  const jan4 = Date.UTC(year, 0, 4)  // always in ISO week 1
  return jan4 - ((new Date(jan4).getUTCDay() + 6) % 7) * DAY + (n - 1) * WEEK
}

export function isoWeek(monday) {
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

export function addWeeks(week, n) {
  return isoWeek(weekStart(week) + n * WEEK)
}

// The pattern alone admits 2025-W53, which doesn't exist; a real week survives the round trip.
export function isWeek(value) {
  return /^\d{4}-W\d{2}$/.test(value ?? '') && isoWeek(weekStart(value)) === value
}
