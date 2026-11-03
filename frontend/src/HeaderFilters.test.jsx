// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { HeaderFilters } from './HeaderFilters.jsx'

afterEach(cleanup)

const show = (methods) => render(
  <MemoryRouter><HeaderFilters locationFilter={null} methods={methods} method={methods[0]} /></MemoryRouter>)

it('offers a method only when the dashboard grades with more than one', () => {
  show(['aedseo'])
  expect(screen.queryByLabelText('filters.method')).toBeNull()
  cleanup()
  show(['aedseo', 'mem'])
  expect(screen.getByLabelText('filters.method')).toBeTruthy()
})
