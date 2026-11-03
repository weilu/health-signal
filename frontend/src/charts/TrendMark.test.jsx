// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { cleanup, render } from '@testing-library/react'
import { TrendMark } from './TrendMark.jsx'

afterEach(cleanup)

it('points the way the trend goes', () => {
  const marks = ['increasing', 'stable', 'decreasing'].map((trend) => {
    const { container } = render(<TrendMark trend={trend} />)
    return container.firstChild.dataset.mark
  })
  expect(marks).toEqual(['up', 'flat', 'down'])
})

it('shows a direction only when there is one: a grey dot otherwise, never a flat arrow', () => {
  const { container } = render(<TrendMark trend="inconclusive" />)
  expect(container.firstChild.dataset.mark).toBe('none')
  expect(container.querySelector('svg')).toBeNull()
})
