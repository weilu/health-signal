// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { Tile } from './StatusTrendTiles.jsx'

afterEach(cleanup)

it('marks a past tile by its dashed edge, not by fading it', () => {
  // Fading would take a tone-coloured word (a level, a trend) below text contrast.
  render(<Tile title="Trend" current={false} footer="Not the latest week">Stable</Tile>)
  const style = getComputedStyle(screen.getByRole('region', { name: 'Trend' }))
  expect(style.borderStyle).toBe('dashed')
  expect(style.opacity === '' || style.opacity === '1').toBe(true)
})
