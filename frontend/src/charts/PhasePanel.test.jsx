// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { fetchConfig, fetchData, fetchPhases, fetchPhaseStreams } from '../api.js'
import { PhasePanel } from './PhasePanel.jsx'

vi.mock('../api.js', () => ({ fetchConfig: vi.fn(), fetchData: vi.fn(), fetchPhases: vi.fn(), fetchPhaseStreams: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

const METHOD = { aedseo: { levels: ['very_low', 'low'], phases: ['in_season', 'out_of_season'],
  active_phases: ['in_season'], stream_roles: ['cases'], trend: true } }
const PHASES = [{ location: 'Greece', pathogen: 'Influenza', period: '2026-W10', method: 'aedseo', phase: 'in_season' }]
const STREAM = { location: 'Greece', pathogen: 'Influenza', method: 'aedseo', role: 'cases', feed: 'clinical',
  series: { indicator: 'ILIconsultationrate' } }

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PhasePanel panel={{ id: 'phase', label_key: 'panels.phase' }} target={{ id: 'Influenza', pages: [] }}
          location={{ value: 'Greece' }} range={{ from: '2026-W09', to: '2026-W10' }} latest="2026-W10" />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PhasePanel', () => {
  it('waits for the stream lookup instead of showing a stream-less phase', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhases.mockResolvedValue(PHASES)
    fetchPhaseStreams.mockReturnValue(new Promise(() => {}))
    renderPanel()
    await screen.findByText('phase.title')   // the phases have loaded; only the streams are pending
    expect(screen.getByRole('progressbar')).toBeTruthy()
  })

  it('reports a failed stream lookup', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhases.mockResolvedValue(PHASES)
    fetchPhaseStreams.mockRejectedValue(Object.assign(new Error('HTTP 500'), { status: 500 }))
    renderPanel()
    expect(await screen.findByRole('alert')).toBeTruthy()
  })

  it('offers each stream chart as a table', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhases.mockResolvedValue(PHASES)
    fetchPhaseStreams.mockResolvedValue([STREAM])
    fetchData.mockResolvedValue([
      { location: 'Greece', period: '2026-W09', indicator: 'ILIconsultationrate', value: 41, unit: 'per_100k', dimensions: {} },
      { location: 'Greece', period: '2026-W10', indicator: 'ILIconsultationrate', value: 57, unit: 'per_100k', dimensions: {} }])
    renderPanel()
    fireEvent.click(await screen.findByRole('button', { name: 'chart.showTable' }))
    expect(await screen.findByRole('table')).toBeTruthy()
    expect(screen.getByText('57')).toBeTruthy()
  })
})
