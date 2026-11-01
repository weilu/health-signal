// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { useEffect } from 'react'
import { cleanup, render } from '@testing-library/react'
import { AlignedCharts, useAlignedAxis } from './AlignedCharts.jsx'
import { TimeSeriesChart } from './TimeSeriesChart.jsx'
import { createTheme } from '@mui/material/styles'
import { initI18n } from '../i18n.js'

// Chart.js needs a real canvas; the options the chart builds are what this test checks.
const drawn = []
const fed = []
vi.mock('react-chartjs-2', () => ({ Line: ({ options, data }) => { drawn.push(options); fed.push(data); return null } }))
afterEach(() => { cleanup(); drawn.length = 0; fed.length = 0 })

function Wider() {   // a sibling chart in the group with a wider axis
  const { onAxisWidth } = useAlignedAxis()
  useEffect(() => onAxisWidth(120))
  return null
}

it('fits its y-axis to the widest in its group', async () => {
  render(
    <AlignedCharts>
      <TimeSeriesChart periods={['2025-W01']} series={[{ label: 'x', values: [1] }]} unit="count" />
      <Wider />
    </AlignedCharts>,
  )
  await new Promise((resolve) => setTimeout(resolve, 0))
  const scale = { width: 40 }
  drawn.at(-1).scales.y.afterFit(scale)
  expect(scale.width).toBe(120)
})

it('labels weeks on the axis and in the tooltip as the rest of the app does, in its language', () => {
  initI18n({ defaultLocale: 'el', locales: ['en', 'el'] })
  render(<TimeSeriesChart periods={['2025-W27', '2025-W28']} series={[{ label: 'x', values: [1, 2] }]} unit="count" />)
  const { x } = drawn.at(-1).scales
  expect(x.ticks.callback.call({ getLabelForValue: (i) => ['2025-W27', '2025-W28'][i] }, 0)).toBe('Εβδ. 27/2025')
  expect(drawn.at(-1).plugins.tooltip.callbacks.title([{ label: '2025-W28' }])).toBe('Εβδ. 28/2025')
})


it('puts a log chart on a log axis, labelled at 1, 2 and 5 of each decade and named as log', () => {
  initI18n({ defaultLocale: 'en', locales: ['en', 'el'] })
  render(<TimeSeriesChart periods={['2025-W01', '2025-W02']} series={[{ label: 'x', values: [1e10, 3e11] }]}
                          unit="copies" scale="log" />)
  const { y } = drawn.at(-1).scales
  expect(y.type).toBe('logarithmic')
  expect(y.title.text).toEqual(['copies', 'log scale'])   // two lines: a long unit mustn't clip
  // A range inside one decade still gets labels; the 3s, 4s… between them would crowd them.
  expect([1e10, 1.3e10, 2e10, 3e10, 5e10].map(y.ticks.callback)).toEqual(['10B', '', '20B', '', '50B'])
  // Grid lines only where there's a label: a line at every 3, 4, 6… of each decade is clutter.
  const line = (value) => y.grid.color({ tick: { value } })
  expect([line(1e10), line(3e10), line(5e10)].map((c) => c === 'transparent')).toEqual([false, true, false])
})

it('leaves a below-detection week out of a log line but marks it at the floor', () => {
  // A zero has no place on a log axis; the stand-in for a non-detect still needs to show the week was sampled.
  render(<TimeSeriesChart periods={['2025-W01', '2025-W02', '2025-W03']} unit="copies" scale="log"
                          series={[{ label: 'x', values: [1e10, 0, 3e11], qualities: [null, 'beLOD', null] }]} />)
  expect(fed.at(-1).datasets[0].data).toEqual([1e10, null, 3e11])
  expect(drawn.at(-1).plugins.floorMarkers.points).toEqual([[0, 1]])
})

it('keeps a linear chart as it was', () => {
  render(<TimeSeriesChart periods={['2025-W01', '2025-W02']} series={[{ label: 'x', values: [0, 3] }]} unit="count" />)
  expect(drawn.at(-1).scales.y.type).toBe('linear')
  expect(fed.at(-1).datasets[0].data).toEqual([0, 3])
})

it("draws a single series in the theme's ink with a dot at every week; several keep their palette", () => {
  // One line has nothing to tell apart, so it reads as text does; the dots show which weeks reported.
  const ink = createTheme().palette.text.primary
  render(<TimeSeriesChart periods={['2025-W01', '2025-W02', '2025-W03']} series={[{ label: 'x', values: [1, 2, 3] }]}
                          unit="count" />)
  const [one] = fed.at(-1).datasets
  expect([one.borderColor, one.pointBackgroundColor]).toEqual([ink, ink])
  expect([0, 1, 2].map((dataIndex) => one.pointRadius({ dataset: one, dataIndex }))).toEqual([3, 3, 3])
  render(<TimeSeriesChart periods={['2025-W01', '2025-W02']} unit="count"
                          series={'abcde'.split('').map((label) => ({ label, values: [1, 2] }))} />)
  const [a] = fed.at(-1).datasets
  expect(a.borderColor).not.toBe(ink)
  expect(a.pointRadius({ dataset: a, dataIndex: 0 })).toBe(0)
})
