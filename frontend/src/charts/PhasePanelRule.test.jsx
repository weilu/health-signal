// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { fetchConfig, fetchPhases, fetchPhaseStreams } from '../api.js'
import { initI18n } from '../i18n.js'
import { PhasePanel } from './PhasePanel.jsx'

// The real English catalog: the rule text is method content, so the key alone can't show where it lands.
vi.mock('../api.js', () => ({ fetchConfig: vi.fn(), fetchData: vi.fn(), fetchPhases: vi.fn(), fetchPhaseStreams: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

it("states the method's phase rule in the status tile, after its as-of line", async () => {
  initI18n({ defaultLocale: 'en', locales: ['en'] })
  fetchConfig.mockResolvedValue({ methods: { aedseo: { levels: ['very_low'], phases: ['in_season', 'out_of_season'],
    active_phases: ['in_season'], stream_roles: ['cases'], trend: true } } })
  fetchPhases.mockResolvedValue([{ location: 'Greece', pathogen: 'Influenza', period: '2026-W10', method: 'aedseo', phase: 'in_season' }])
  fetchPhaseStreams.mockResolvedValue([])
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <PhasePanel panel={{ id: 'phase', label_key: 'panels.phase' }} target={{ id: 'Influenza', pages: [] }}
          location={{ value: 'Greece' }} range={{ from: '2026-W09', to: '2026-W10' }} latest="2026-W10" />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  const tile = (await screen.findByText(/^Season status$/i)).closest('section').textContent
  expect(tile.indexOf('As of')).toBeGreaterThan(-1)
  expect(tile.indexOf('A pathogen is in season')).toBeGreaterThan(tile.indexOf('As of'))
})
