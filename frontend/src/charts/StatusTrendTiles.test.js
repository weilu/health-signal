import { describe, expect, it } from 'vitest'
import { asOfFooter, growthText, sourceFooter, trendFooter } from './StatusTrendTiles.jsx'

// Echoes keys and their options, so the test sees what the footer asks i18n for.
const t = (key, options) => (options ? `${key}(${Object.entries(options).map(([k, v]) => `${k}=${v}`).join(',')})` : key)

describe('asOfFooter', () => {
  it("names the part of the method behind each tile, so a mix of methods stays legible", () => {
    const pick = { asOf: '2026-W10', current: true }
    expect(asOfFooter(t, pick, 'aedseo', 'trend')).toContain('source=methods.aedseo.sources.trend')
    expect(asOfFooter(t, pick, 'mem', 'status')).toContain('source=methods.mem.sources.status')
  })
})

describe('growthText', () => {
  // The label comes from the interval alone (stable when it holds 0), so the tile shows the interval, in the
  // method's own words: its window is the method's.
  const row = { method: 'aedseo', growth_rate: -0.43, growth_lower: -0.8, growth_upper: 0.19 }
  it('gives the likely range of the weekly change, without the point estimate', () => {
    const text = growthText(t, { asOf: '2026-W26', current: true }, row)
    expect(text).toContain('methods.aedseo.growth(')
    expect(text).toContain('lower=-80%,upper=+19%')
    expect(text).not.toContain('-43%')
    expect(text).not.toContain('context=past')
  })
  it('names the week when it is not the latest', () => {
    expect(growthText(t, { asOf: '2025-W40', current: false }, row)).toContain('context=past')
  })
})

describe('sourceFooter', () => {
  // The trend tile's week is in its sentence, but a cropped tile must still say it isn't the latest.
  it('names the source, and says when the week is not the latest', () => {
    expect(sourceFooter(t, { asOf: '2026-W26', current: true }, 'aedseo', 'trend'))
      .toBe('assessment.source(source=methods.aedseo.sources.trend(defaultValue=aedseo))')
    expect(sourceFooter(t, { asOf: '2025-W40', current: false }, 'aedseo', 'trend')).toContain('assessment.sourcePast(')
  })
})


describe('trendFooter', () => {
  // The week is in the growth sentence; an inconclusive trend has none, so the footer must carry it.
  const past = { asOf: '2025-W40', current: false }
  it('is the source alone beside a growth sentence', () =>
    expect(trendFooter(t, past, { method: 'aedseo', growth_lower: -0.1, growth_upper: 0.2 })).toContain('assessment.sourcePast('))
  it('keeps the week when there is no sentence to give it', () =>
    expect(trendFooter(t, past, { method: 'aedseo', growth_lower: null, growth_upper: null })).toContain('assessment.asOfPast('))
})
