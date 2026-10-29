// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { useEffect } from 'react'
import { cleanup, render } from '@testing-library/react'
import { AlignedCharts, useAlignedAxis } from './AlignedCharts.jsx'
import { TimeSeriesChart } from './TimeSeriesChart.jsx'

// Chart.js needs a real canvas; the options the chart builds are what this test checks.
const drawn = []
vi.mock('react-chartjs-2', () => ({ Line: ({ options }) => { drawn.push(options); return null } }))
afterEach(() => { cleanup(); drawn.length = 0 })

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
