import { describe, expect, it } from 'vitest'
import { buildTheme } from './theme.js'

describe('buildTheme', () => {
  it('lets branding replace the palette wholesale', () => {
    const theme = buildTheme({ theme: { palette: { chart: { light: ['#000000', '#111111'] } } } })
    expect(theme.palette.chart.light).toEqual(['#000000', '#111111'])
  })
})
