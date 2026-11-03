// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { initI18n } from '../i18n.js'
import { StatusTrendTiles } from './StatusTrendTiles.jsx'

const MEM = { name: 'mem', levels: ['baseline', 'low', 'medium', 'high', 'very_high'], phases: [], active_phases: [] }
const pick = (row) => ({ row: { method: 'mem', period: '2026-W10', ...row }, asOf: '2026-W10', current: true })

beforeEach(() => initI18n({ defaultLocale: 'en', locales: ['en'] }))
afterEach(cleanup)

it("says MEM doesn't assess the trend below its epidemic threshold, with no arrow", () => {
  const { container } = render(<StatusTrendTiles pick={pick({ level: 'baseline', trend: 'not_assessed' })} method={MEM} />)
  expect(screen.getByText('Baseline')).toBeTruthy()
  expect(screen.getByText("Not assessed: below MEM's epidemic threshold")).toBeTruthy()
  expect(screen.getByText('MEM assesses trend only during an epidemic')).toBeTruthy()
  expect(container.querySelector('[data-mark="up"],[data-mark="down"],[data-mark="flat"]')).toBeNull()
})

it("names MEM's rising trend as the dashboard's increasing, with its arrow", () => {
  const { container } = render(<StatusTrendTiles pick={pick({ level: 'medium', trend: 'increasing' })} method={MEM} />)
  expect(screen.getByText('Increasing')).toBeTruthy()
  expect(container.querySelector('[data-mark="up"]')).toBeTruthy()
})
