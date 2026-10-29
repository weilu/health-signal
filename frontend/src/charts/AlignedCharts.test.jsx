// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { useEffect } from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { AlignedCharts, useAlignedAxis } from './AlignedCharts.jsx'

afterEach(cleanup)

// Stands in for a chart: reports its natural axis width, shows the width it is given.
function Chart({ name, natural }) {
  const { axisWidth, onAxisWidth } = useAlignedAxis()
  useEffect(() => { onAxisWidth(natural) })
  return <p>{`${name}:${axisWidth}`}</p>
}

it('gives every chart in a group the widest axis, so their plots start at the same x', async () => {
  render(<AlignedCharts><Chart name="cases" natural={60} /><Chart name="admissions" natural={110} /></AlignedCharts>)
  expect(await screen.findByText('cases:110')).toBeTruthy()
  expect(screen.getByText('admissions:110')).toBeTruthy()
})

it('leaves a chart outside any group to its own axis', () => {
  render(<Chart name="alone" natural={80} />)
  expect(screen.getByText('alone:0')).toBeTruthy()
})
