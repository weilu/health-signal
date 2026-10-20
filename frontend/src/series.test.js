import { describe, expect, it } from 'vitest'
import { endLabelsFit, toChartModel } from './series.js'

const row = (period, value, dims = {}, unit = 'percent', location = 'Greece') => ({ location, period, value, unit, dimensions: dims })

describe('toChartModel', () => {
  it('reports no rows as empty', () => {
    expect(toChartModel([], 'survtype', 8)).toEqual({ status: 'empty' })
  })
  it('refuses mixed units rather than share one axis', () => {
    expect(toChartModel([row('2025-W01', 1, {}, 'per_100k'), row('2025-W01', 2, {}, 'per_100_consultations')], null, 8))
      .toEqual({ status: 'mixedUnits', units: ['per_100_consultations', 'per_100k'] })
  })
  it('refuses a query with two rows for one series-week', () => {
    const rows = [row('2025-W01', 1, { pathogensubtype: 'A(H3)' }), row('2025-W01', 9, { pathogensubtype: 'A(H3)' })]
    expect(toChartModel(rows, 'pathogensubtype', 8)).toEqual({ status: 'ambiguous', key: 'A(H3)', period: '2025-W01' })
  })
  it('refuses to join different populations into one line, even in disjoint weeks', () => {
    expect(toChartModel([row('2025-W01', 1, { age: '0-4' }), row('2025-W02', 2, { age: '65+' })], null, 8))
      .toEqual({ status: 'mixedSeries', key: '', field: 'age' })
  })
  it('refuses more than one location per panel, even split across series', () => {
    const rows = [row('2025-W01', 1, { age: '0-4' }, 'percent', 'Greece'), row('2025-W02', 2, { age: '65+' }, 'percent', 'Attica')]
    expect(toChartModel(rows, null, 8)).toEqual({ status: 'mixedSeries', field: 'location' })
    expect(toChartModel(rows, 'age', 8)).toEqual({ status: 'mixedSeries', field: 'location' })
  })
  it('lets other dimensions differ between series', () => {
    const rows = [row('2025-W01', 1, { pathogensubtype: 'A(H3)', pathogentype: 'Influenza A' }),
      row('2025-W01', 2, { pathogensubtype: 'B/Victoria', pathogentype: 'Influenza B' })]
    expect(toChartModel(rows, 'pathogensubtype', 8).status).toBe('ok')
  })
  it('treats a blank dimension as a missing one', () => {
    expect(toChartModel([row('2025-W01', 1, { age: '' }), row('2025-W02', 2)], null, 8).status).toBe('ok')
  })
  it('refuses more series than colour slots', () => {
    const rows = ['a', 'b', 'c'].map((k) => row('2025-W01', 1, { survtype: k }))
    expect(toChartModel(rows, 'survtype', 2)).toEqual({ status: 'tooManySeries', count: 3 })
  })
  it('aligns series on the sorted week axis with gaps as null', () => {
    const rows = [
      row('2025-W03', 3, { survtype: 'sentinel' }), row('2025-W01', 1, { survtype: 'sentinel' }),
      row('2025-W02', 5, { survtype: 'SARI' }),
    ]
    expect(toChartModel(rows, 'survtype', 8)).toEqual({
      status: 'ok', unit: 'percent', periods: ['2025-W01', '2025-W02', '2025-W03'],
      series: [{ key: 'SARI', values: [null, 5, null] }, { key: 'sentinel', values: [1, null, 3] }],
    })
  })
  it('keeps a week no series reported on the axis', () => {
    expect(toChartModel([row('2025-W01', 1), row('2025-W03', 3)], null, 8))
      .toMatchObject({ periods: ['2025-W01', '2025-W02', '2025-W03'], series: [{ values: [1, null, 3] }] })
  })
  it('spans the selected range, not just the reported weeks', () => {
    expect(toChartModel([row('2025-W02', 2)], null, 8, { from: '2025-W01', to: '2025-W03' }))
      .toMatchObject({ periods: ['2025-W01', '2025-W02', '2025-W03'], series: [{ values: [null, 2, null] }] })
  })
  it('groups rows missing the dimension into a last, unnamed series', () => {
    const m = toChartModel([row('2025-W01', 1, {}), row('2025-W01', 2, { survtype: 'SARI' })], 'survtype', 8)
    expect(m.series.map((s) => s.key)).toEqual(['SARI', ''])
  })
  it('makes one series when nothing splits it', () => {
    expect(toChartModel([row('2025-W01', 4)], null, 8).series).toEqual([{ key: '', values: [4] }])
  })
})


describe('endLabelsFit', () => {
  it('fits labels that are far enough apart', () => expect(endLabelsFit([10, 40, 90], 14)).toBe(true))
  it('rejects labels that would overlap, in any order', () => expect(endLabelsFit([90, 10, 20], 14)).toBe(false))
  it('fits zero or one label', () => {
    expect(endLabelsFit([], 14)).toBe(true)
    expect(endLabelsFit([50], 14)).toBe(true)
  })
})
