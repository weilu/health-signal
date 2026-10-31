// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { initI18n } from '../i18n.js'
import { SeriesTable } from './SeriesTable.jsx'

afterEach(cleanup)

it('lists weeks as the rest of the app labels them, in its language', () => {
  initI18n({ defaultLocale: 'el', locales: ['en', 'el'] })
  render(<SeriesTable periods={['2025-W27']} series={[{ key: '', label: 'x', values: [1] }]} unit="count" />)
  expect(screen.getByRole('rowheader').textContent).toBe('Εβδ. 27/2025')
})
