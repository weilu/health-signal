import { describe, expect, it } from 'vitest'
import { toChartModel } from './series.js'

const row = (period, value, dims = {}, unit = 'percent') => ({ period, value, unit, dimensions: dims })

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
  it('groups rows missing the dimension into a last, unnamed series', () => {
    const m = toChartModel([row('2025-W01', 1, {}), row('2025-W01', 2, { survtype: 'SARI' })], 'survtype', 8)
    expect(m.series.map((s) => s.key)).toEqual(['SARI', ''])
  })
  it('makes one series when nothing splits it', () => {
    expect(toChartModel([row('2025-W01', 4)], null, 8).series).toEqual([{ key: '', values: [4] }])
  })
})
