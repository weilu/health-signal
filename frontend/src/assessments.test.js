import { describe, expect, it } from 'vitest'
import { activeWeeks, bandAlpha, ofSeries, phaseRuns, bandsFor, levelTone, phaseSince, pickInRange, sameSeries, streamScale, trendTone } from './assessments.js'

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
  it('turns lower bounds into bands from the lowest level up, the top one open-ended', () => {
    // Thresholds give each level's lower bound from the second level on; the lowest runs from the axis bottom.
    const rows = [{ from: 'A', to: 'B', level: 'medium', lower_bound: 20 }, { from: 'A', to: 'B', level: 'low', lower_bound: 10 }]
    expect(bandsFor(rows, LEVELS)).toEqual([
      { from: 'A', to: 'B', level: 'very_low', lower: -Infinity, upper: 10 },
      { from: 'A', to: 'B', level: 'low', lower: 10, upper: 20 },
      { from: 'A', to: 'B', level: 'medium', lower: 20, upper: Infinity },
    ])
  })
})

describe('phaseSince', () => {
  const rows = ['2025-W47', '2025-W48', '2025-W49', '2025-W50'].map((p, i) => ({ period: p, phase: i ? 'in_season' : 'out_of_season' }))
  it('is the start of the active run ending at the as-of week', () => expect(phaseSince(rows, '2025-W50', ['in_season'])).toBe('2025-W48'))
  it('is null when not active', () => expect(phaseSince(rows, '2025-W47', ['in_season'])).toBeNull())
  it('reaches back no further than a week with no phase', () => {
    const gap = ['2025-W36', '2025-W37', '2025-W44', '2025-W45'].map((period) => ({ period, phase: 'in_season' }))
    expect(phaseSince(gap, '2025-W45', ['in_season'])).toBe('2025-W44')
  })
})

describe('sameSeries', () => {
  const stream = { feed: 'wastewater', series: { indicator: 'cov', aggregation: 'floMean' } }
  it('matches a panel query regardless of parameter order', () =>
    expect(sameSeries('wastewater', { aggregation: 'floMean', indicator: 'cov' }, stream)).toBe(true))
  it('needs the same feed and every parameter the query states', () => {
    expect(sameSeries('clinical', { indicator: 'cov', aggregation: 'floMean' }, stream)).toBe(false)
    expect(sameSeries('wastewater', { indicator: 'cov', aggregation: 'me' }, stream)).toBe(false)
  })
  it('matches a query that leaves a dimension the stream pins implicit', () =>
    expect(sameSeries('wastewater', { indicator: 'cov' }, stream)).toBe(true))
})

describe('levelTone for ungraded weeks', () => {
  it('is neutral, never the all-clear tone', () => {
    expect(levelTone(LEVELS, null)).toBe('neutral')
    expect(levelTone(LEVELS, 'alert')).toBe('neutral')
  })
})

describe('bandAlpha', () => {
  it('steps darker within a tone, so adjacent levels sharing a tone stay apart', () => {
    const alphas = LEVELS.map((l) => bandAlpha(LEVELS, l))
    expect(alphas[1]).toBeGreaterThan(alphas[0])  // low darker than very low (both green)
    expect(alphas[4]).toBeGreaterThan(alphas[3])  // very high darker than high (both red)
    expect(new Set(alphas.map((a, i) => `${levelTone(LEVELS, LEVELS[i])}:${a}`)).size).toBe(5)
  })
})


describe('pickInRange with several series', () => {
  it('reports rows of several series as ambiguous rather than picking one', () => {
    const rows = [{ period: '2026-W10', level: 'low' }, { period: '2026-W10', level: 'high' }]
    expect(pickInRange(rows, { from: '2026-W01', to: '2026-W20' }, '2026-W20')).toEqual({ ambiguous: true })
  })
})

describe('pickInRange across locations', () => {
  it('treats rows of several locations as ambiguous even when their weeks differ', () => {
    // Without a location filter, Greece's W10 and Attica's W09 aren't one series' history.
    const rows = [{ location: 'Greece', period: '2026-W10' }, { location: 'Attica', period: '2026-W09' }]
    expect(pickInRange(rows, { from: '2026-W01', to: '2026-W20' }, '2026-W20')).toEqual({ ambiguous: true })
  })
})

describe('series identity', () => {
  it('treats rows of different dimensions as ambiguous even in disjoint weeks', () => {
    const rows = [{ location: 'Greece', period: '2026-W09', dimensions: { age: '0-4' } },
                  { location: 'Greece', period: '2026-W10', dimensions: { age: '65+' } }]
    expect(pickInRange(rows, { from: '2026-W01', to: '2026-W20' }, '2026-W20')).toEqual({ ambiguous: true })
  })

  it('never lets a missing dimension match a set one', () => {
    const plotted = { location: 'Attica', dimensions: { aggregation: 'floMean' } }
    expect(ofSeries({ location: 'Attica', dimensions: { aggregation: 'floMean', fraction: 'liq' } }, plotted)).toBe(false)
    expect(ofSeries({ location: 'Attica', dimensions: { aggregation: 'floMean', fraction: '' } }, plotted)).toBe(true)
    expect(ofSeries({ location: 'Attica', dimensions: {} }, plotted)).toBe(false)
  })
})

describe('phaseRuns', () => {
  const ACTIVE = ['in_wave']
  const phases = (list) => list.map((x) => ({ period: x.split(':')[0], phase: x.split(':')[1] }))
  const rows = phases(['2023-W50:between_waves', '2023-W51:in_wave', '2023-W52:in_wave', '2024-W01:in_wave',
                       '2024-W02:between_waves', '2024-W20:in_wave', '2024-W21:in_wave'])

  it('lists each run of active weeks overlapping the range, flagging clipped and ongoing runs', () => {
    expect(phaseRuns(rows, { from: '2023-W52', to: '2024-W20' }, ACTIVE)).toEqual([
      { from: '2023-W51', to: '2024-W01', weeks: 3, startsBefore: true, endsAfter: false, ongoing: false },
      { from: '2024-W20', to: '2024-W21', weeks: 2, startsBefore: false, endsAfter: true, ongoing: true },
    ])
  })

  it('lists none when no run touches the range', () => {
    expect(phaseRuns(rows, { from: '2024-W05', to: '2024-W10' }, ACTIVE)).toEqual([])
  })

  it('ends a run at weeks with no phase (a reporting gap), as the charts leave them unshaded', () => {
    const gap = phases(['2025-W36:in_wave', '2025-W37:in_wave', '2025-W44:in_wave', '2025-W45:in_wave', '2025-W46:between_waves'])
    expect(phaseRuns(gap, { from: '2025-W30', to: '2025-W50' }, ACTIVE).map((r) => [r.from, r.to, r.weeks]))
      .toEqual([['2025-W36', '2025-W37', 2], ['2025-W44', '2025-W45', 2]])
  })
})


describe('streamScale', () => {
  // A phase stream is charted on its panel's axis, so wastewater reads the same on the overview as on its own page.
  const ww = { id: 'ww', type: 'timeseries', y_scale: 'log', query: { feed: 'wastewater', indicator: 'cov', dimensions: { aggregation: 'floMean' } } }
  const target = { pages: [{ panels: [{ id: 'summary', type: 'summary' }, ww] }] }
  it("takes the stream's panel's scale", () =>
    expect(streamScale(target, { feed: 'wastewater', series: { indicator: 'cov', aggregation: 'floMean' } })).toBe('log'))
  it('skips a split chart that also covers the stream: only a single-series panel can be one', () => {
    const split = { id: 'by_fraction', query: { feed: 'wastewater', indicator: 'cov', dimensions: {} }, series_by: 'fraction' }
    const liquid = { id: 'liq', y_scale: 'log', query: { feed: 'wastewater', indicator: 'cov', dimensions: { fraction: 'liq' } } }
    expect(streamScale({ pages: [{ panels: [split, liquid] }] }, { feed: 'wastewater', series: { indicator: 'cov', fraction: 'liq' } }))
      .toBe('log')
  })
  it('is linear for a stream without a panel on the tab', () =>
    expect(streamScale(target, { feed: 'clinical', series: { indicator: 'deaths' } })).toBe('linear'))
})


describe('trendTone', () => {
  // Rising is the early warning; never red, which stays the burden's. No direction is no reading: grey.
  it('is amber when rising and green when steady or falling', () =>
    expect(['increasing', 'stable', 'decreasing'].map(trendTone)).toEqual(['warning', 'success', 'success']))
  it('is neutral without a direction', () => expect([trendTone('inconclusive'), trendTone(null)]).toEqual(['neutral', 'neutral']))
})
