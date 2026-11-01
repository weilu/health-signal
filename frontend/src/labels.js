// One stamp for every week label, translated: "W42 2025".
export function weekStamp(t, week) {
  const [year, n] = week.split('-W')
  return t('range.week', { week: n, year })
}

// panels.<id> overrides the name built from the query, which the library can label though not the panel id.
export function panelLabel(t, panel) {
  return t(panel.label_key, { defaultValue: defaultPanelName(t, panel) })
}

// A title-cased name inside a sentence ("measured by hospital admissions"); a capital that starts an acronym
// (SARI, SARS-CoV-2) stays.
export function inSentence(text) {
  return text.length > 1 && text[1] === text[1].toLocaleLowerCase() ? text[0].toLocaleLowerCase() + text.slice(1) : text
}

function defaultPanelName(t, panel) {
  if (!panel.name) return t(`panelTypes.${panel.type}`, { defaultValue: panel.id })
  const { indicator, dimensions } = panel.name
  const name = [t(`indicators.${indicator}`, { defaultValue: indicator }),
                ...Object.entries(dimensions).map(([d, v]) => seriesLabel(t, d, v))].join(' · ')
  return panel.series_by
    ? t('chart.byDimension', { name, dimension: t(`dimensionNames.${panel.series_by}`, { defaultValue: panel.series_by }) })
    : name
}

// The tab's pathogen and the selected location, so a chart keeps its context once the tabs scroll away; the
// server says whether the pathogen belongs (not for a syndromic series, or one whose name already says it). A card
// about the whole tab (the overview's, named by its type rather than a query) is always its pathogen's.
export function chartTitle(t, panel, target, location) {
  const name = panelLabel(t, panel)
  const pathogen = (panel.name ? panel.name.pathogen : true) && configLabel(t, target.label_key, target.id)
  const form = pathogen && location ? 'full' : pathogen ? 'pathogen' : location ? 'location' : null
  return form ? t(`chart.title.${form}`, { name, pathogen, location: location?.label }) : name
}

// A deployment's own, from its text: target-specific before general, each with a location variant first
// (subtitles.<panel>_<location>), so wording can differ by pathogen or region.
export function chartSubtitle(t, panel, target, location) {
  return t([`subtitles.${target.id}.${panel.id}`, `subtitles.${panel.id}`],
           { context: location?.value, pathogen: configLabel(t, target.label_key, target.id), location: location?.label,
             defaultValue: '' })
}

// Unlabelled values read as themselves: codes like "A(H3)" or "0-4" need no name. Pathogens are named once, in
// the registry the tabs use.
export function seriesLabel(t, dimension, value) {
  if (!value) return t('chart.unspecified')
  return t(dimension === 'pathogen' ? `targets.${value}` : `dimensions.${dimension}.${value}`, { defaultValue: value })
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
