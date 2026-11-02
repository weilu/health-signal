// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { TabLabel } from './TabLabel.jsx'

afterEach(cleanup)

it('locks a gated tab, named for screen readers', () => {
  render(<TabLabel label="AMR" lock="Signed-in users only" />)
  expect(screen.getByText('AMR')).toBeTruthy()
  expect(screen.getByRole('img', { name: 'Signed-in users only' })).toBeTruthy()
})

it('leaves a public tab unmarked', () => {
  render(<TabLabel label="RSV" />)
  expect(screen.queryByRole('img')).toBeNull()
})
