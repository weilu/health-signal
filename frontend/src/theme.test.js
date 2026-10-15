import { describe, expect, it } from 'vitest'
import { buildTheme } from './theme.js'

describe('chart palette', () => {
  it('ships 8 fixed-order slots per mode', () => {
    const { chart } = buildTheme({}).palette
    expect(chart.light).toHaveLength(8)
    expect(chart.dark).toHaveLength(8)
  })
  it('lets branding replace the palette wholesale', () => {
    const theme = buildTheme({ theme: { palette: { chart: { light: ['#000000', '#111111'] } } } })
    expect(theme.palette.chart.light).toEqual(['#000000', '#111111'])
  })
})
