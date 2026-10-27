import { describe, expect, it } from 'vitest'
import { asOfFooter } from './StatusTrendTiles.jsx'

// Echoes keys and their options, so the test sees what the footer asks i18n for.
const t = (key, options) => (options ? `${key}(${Object.entries(options).map(([k, v]) => `${k}=${v}`).join(',')})` : key)

describe('asOfFooter', () => {
  it("names the part of the method behind each tile, so a mix of methods stays legible", () => {
    const pick = { asOf: '2026-W10', current: true }
    expect(asOfFooter(t, pick, 'aedseo', 'trend')).toContain('source=methods.aedseo.sources.trend')
    expect(asOfFooter(t, pick, 'mem', 'status')).toContain('source=methods.mem.sources.status')
  })
})
