// One stamp for every week label, translated: "W42 2025".
export function weekStamp(t, week) {
  const [year, n] = week.split('-W')
  return t('range.week', { week: n, year })
}

// The stamp plus its parts, so a language can phrase it its own way (Greek bulletins: "εβδομάδα 41/2026").
export function reportingWeek(t, week) {
  const [year, n] = week.split('-W')
  return { stamp: weekStamp(t, week), week: n, year }
}

// i18next returns "" for t(null) instead of the default, so a missing key never reaches t.
export const configLabel = (t, key, id) => (key ? t(key, { defaultValue: id }) : id)
