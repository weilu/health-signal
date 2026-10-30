// One stamp for every week label, translated: "W42 2025".
export function weekStamp(t, week) {
  const [year, n] = week.split('-W')
  return t('range.week', { week: n, year })
}

// A split chart's line, named by its dimension value: labelled where the library or the deployment gives the value
// a name (age "total"), as itself otherwise (a code like "A(H3)" or "0-4" reads fine).
export function seriesLabel(t, dimension, value) {
  return value ? t(`dimensions.${dimension}.${value}`, { defaultValue: value }) : t('chart.unspecified')
}

// The stamp plus its parts, so a language can phrase it its own way (Greek bulletins: "εβδομάδα 41/2026").
export function reportingWeek(t, week) {
  const [year, n] = week.split('-W')
  return { stamp: weekStamp(t, week), week: n, year }
}

// i18next returns "" for t(null) instead of the default, so a missing key never reaches t.
export const configLabel = (t, key, id) => (key ? t(key, { defaultValue: id }) : id)

// Axis ticks in compact form ("50T", "50 τρισ."): wastewater loads reach 1e13, and full digits would eat a
// phone-width chart. Significant digits rather than fraction digits, so small ticks (0.42, 0.44) stay apart.
export function axisNumber(lang) {
  const format = new Intl.NumberFormat(lang, { notation: 'compact', maximumSignificantDigits: 3 })
  return (value) => format.format(value)
}
