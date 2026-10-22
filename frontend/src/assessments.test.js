import { describe, expect, it } from 'vitest'
import { activeWeeks, assessmentParams, bandsFor, levelTone, phaseSince, pickInRange, sameSeries } from './assessments.js'

const a = (period, extra = {}) => ({ period, level: 'low', ...extra })
const LEVELS = ['very_low', 'low', 'medium', 'high', 'very_high']

describe('pickInRange', () => {
  const range = { from: '2025-W40', to: '2026-W20' }
  it('is null for a series that is never assessed (no tiles)', () => expect(pickInRange([], range, '2026-W20')).toBeNull())
  it('takes the latest row within the range and marks it current at the latest week', () =>
    expect(pickInRange([a('2025-W50'), a('2026-W20')], range, '2026-W20')).toMatchObject({ asOf: '2026-W20', current: true }))
  it('falls back to the latest in-range row when the series lags, not current', () =>
    expect(pickInRange([a('2026-W16')], range, '2026-W20')).toMatchObject({ asOf: '2026-W16', current: false }))
  it('never reaches before the range start', () =>
    expect(pickInRange([a('2025-W10')], range, '2026-W20')).toEqual({ row: undefined }))
})

describe('levelTone', () => {
  it('spreads ordered levels over three tones', () =>
    expect(LEVELS.map((l) => levelTone(LEVELS, l))).toEqual(['success', 'success', 'warning', 'error', 'error']))
})

describe('activeWeeks', () => {
  it('collects weeks in an active phase', () =>
    expect([...activeWeeks([a('W1', { phase: 'in_season' }), a('W2', { phase: null }), a('W3', { phase: 'out_of_season' })], ['in_season'])]).toEqual(['W1']))
})

describe('bandsFor', () => {
  it('turns lower bounds into bands, the top one open-ended', () => {
    const rows = [{ from: 'A', to: 'B', level: 'medium', lower_bound: 20 }, { from: 'A', to: 'B', level: 'low', lower_bound: 10 }]
    expect(bandsFor(rows, LEVELS)).toEqual([
      { from: 'A', to: 'B', level: 'low', lower: 10, upper: 20 },
      { from: 'A', to: 'B', level: 'medium', lower: 20, upper: Infinity },
    ])
  })
})

describe('phaseSince', () => {
  const rows = ['2025-W47', '2025-W48', '2025-W49', '2025-W50'].map((p, i) => ({ period: p, phase: i ? 'in_season' : 'out_of_season' }))
  it('is the start of the active run ending at the as-of week', () => expect(phaseSince(rows, '2025-W50', ['in_season'])).toBe('2025-W48'))
  it('is null when not active', () => expect(phaseSince(rows, '2025-W47', ['in_season'])).toBeNull())
})

describe('sameSeries', () => {
  const stream = { feed: 'wastewater', series: { indicator: 'cov', aggregation: 'floMean' } }
  it('matches a panel query regardless of parameter order', () =>
    expect(sameSeries('wastewater', { aggregation: 'floMean', indicator: 'cov' }, stream)).toBe(true))
  it('needs the same feed and every parameter', () => {
    expect(sameSeries('clinical', { indicator: 'cov', aggregation: 'floMean' }, stream)).toBe(false)
    expect(sameSeries('wastewater', { indicator: 'cov' }, stream)).toBe(false)
  })
})

describe('assessmentParams', () => {
  it('drops the date range so the whole history is fetched once', () =>
    expect(assessmentParams({ feed: 'w', indicator: 'cov', week_from: 'a', week_to: 'b' })).toEqual({ feed: 'w', indicator: 'cov' }))
})
