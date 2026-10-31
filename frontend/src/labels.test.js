import { describe, expect, it } from 'vitest'
import { axisNumber, configLabel, panelLabel, reportingWeek, seriesLabel, weekStamp } from './labels.js'

const t = (key, opts) => (key === 'targets.covid' ? 'COVID-19' : opts?.defaultValue ?? '')

describe('configLabel', () => {
  it('translates a known key', () => expect(configLabel(t, 'targets.covid', 'covid')).toBe('COVID-19'))
  it('falls back to the id for an untranslated key', () => expect(configLabel(t, 'targets.flu', 'flu')).toBe('flu'))
  it('uses the id when no key is configured', () => {
    expect(configLabel(t, null, 'rsv')).toBe('rsv')
    expect(configLabel(t, undefined, 'rsv')).toBe('rsv')
  })
})

describe('weekStamp', () => {
  it('passes the week and year to the translation', () => {
    const t = (key, vars) => `${key}:${vars.week}/${vars.year}`
    expect(weekStamp(t, '2025-W07')).toBe('range.week:07/2025')
  })
})

describe('reportingWeek', () => {
  it('offers the stamp and its parts to the translation', () => {
    const t = (key, vars) => `W${vars.week} ${vars.year}`
    expect(reportingWeek(t, '2026-W41')).toEqual({ stamp: 'W41 2026', week: '41', year: '2026' })
  })
})

describe('axisNumber', () => {
  it('keeps axis labels short at any magnitude, in the reader’s language', () => {
    expect([50e12, 1.25e12, 1400, 0.45, 12].map(axisNumber('en'))).toEqual(['50T', '1.25T', '1.4K', '0.45', '12'])
    expect(axisNumber('el')(50e12)).toBe('50\u00a0τρισ.')   // a non-breaking space: the unit never wraps away
  })
})

describe('seriesLabel', () => {
  const tr = (key, opts) => ({ 'dimensions.age.total': 'All ages', 'chart.unspecified': 'Unspecified' }[key]
                              ?? opts?.defaultValue ?? key)
  it("labels a split chart's line by its dimension value", () => expect(seriesLabel(tr, 'age', 'total')).toBe('All ages'))
  it('keeps a value that has no label, such as a subtype code', () =>
    expect(seriesLabel(tr, 'pathogensubtype', 'A(H3)')).toBe('A(H3)'))
  it('names a missing value', () => expect(seriesLabel(tr, 'age', '')).toBe('Unspecified'))
})

describe('panelLabel', () => {
  const text = {
    'indicators.positivity': 'Test positivity', 'indicators.SARIrate': 'SARI rate',
    'dimensions.survtype.SARI virological': 'SARI virological', 'dimensionNames.age': 'age group',
    'panelTypes.summary': 'Summary', 'panels.nice': 'SARI test positivity',
  }
  const tr = (key, opts) => {
    const found = text[key] ?? (key === 'chart.byDimension' ? `${opts.name} by ${opts.dimension}` : undefined)
    return found ?? opts?.defaultValue ?? key
  }
  const panel = (id, extra) => ({ id, type: 'timeseries', label_key: `panels.${id}`, ...extra })
  it("names a panel by its indicator and what sets it apart, when the deployment doesn't", () =>
    expect(panelLabel(tr, panel('pos', { name: { indicator: 'positivity', dimensions: { survtype: 'SARI virological' } } })))
      .toBe('Test positivity · SARI virological'))
  it("uses the deployment's own name where it gives one", () =>
    expect(panelLabel(tr, panel('nice', { name: { indicator: 'positivity', dimensions: {} } }))).toBe('SARI test positivity'))
  it('names a split panel by the dimension it splits on', () =>
    expect(panelLabel(tr, panel('by_age', { series_by: 'age', name: { indicator: 'SARIrate', dimensions: {} } })))
      .toBe('SARI rate by age group'))
  it('names a panel without a query by its kind', () =>
    expect(panelLabel(tr, panel('overview', { type: 'summary' }))).toBe('Summary'))
})
