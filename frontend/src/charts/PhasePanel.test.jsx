// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { fetchConfig, fetchData, fetchPhases, fetchPhaseStreams } from '../api.js'
import { PhasePanel } from './PhasePanel.jsx'

vi.mock('../api.js', () => ({ fetchConfig: vi.fn(), fetchData: vi.fn(), fetchPhases: vi.fn(), fetchPhaseStreams: vi.fn() }))
// The chart draws on a canvas; its props are what the panel decides.
const charted = []
vi.mock('./TimeSeriesChart.jsx', () => ({ TimeSeriesChart: (props) => { charted.push(props); return null } }))
afterEach(() => { cleanup(); vi.resetAllMocks(); charted.length = 0 })

const METHOD = { aedseo: { levels: ['very_low', 'low'], phases: ['in_season', 'out_of_season'],
  active_phases: ['in_season'], stream_roles: ['cases'], trend: true } }
const PHASES = [{ location: 'Greece', pathogen: 'Influenza', period: '2026-W10', method: 'aedseo', phase: 'in_season' }]
const STREAM = { location: 'Greece', pathogen: 'Influenza', method: 'aedseo', role: 'cases', feed: 'clinical',
  series: { indicator: 'ILIconsultationrate' } }

function renderPanel(location = { value: 'Greece' }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <PhasePanel panel={{ id: 'phase', label_key: 'panels.phase' }} target={{ id: 'Influenza', pages: [] }}
          location={location} range={{ from: '2026-W09', to: '2026-W10' }} latest="2026-W10" />
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

  it('says when phases of several locations share the range, with no location filter', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhases.mockResolvedValue([...PHASES, { ...PHASES[0], location: 'Attica', phase: 'out_of_season' }])
    fetchPhaseStreams.mockResolvedValue([])
    renderPanel(null)
    expect(await screen.findByText('phase.ambiguous')).toBeTruthy()
    expect(screen.queryByText('assessment.noneInRange')).toBeNull()
  })

  it("charts each stream at its own location, shaded with that location's phase", async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhases.mockResolvedValue([...PHASES, { ...PHASES[0], location: 'Attica', period: '2026-W09' }])
    fetchPhaseStreams.mockResolvedValue([STREAM])
    fetchData.mockResolvedValue([
      { location: 'Greece', period: '2026-W10', indicator: 'ILIconsultationrate', value: 57, unit: 'per_100k', dimensions: {} }])
    renderPanel(null)
    await vi.waitFor(() => expect(charted.length).toBeGreaterThan(0))
    expect(fetchData.mock.calls[0][0].location).toBe('Greece')
    expect([...charted.at(-1).shading]).toEqual(['2026-W10'])   // not Attica's W09
  })

  it('reports why a stream cannot be charted rather than calling it missing', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhases.mockResolvedValue(PHASES)
    fetchPhaseStreams.mockResolvedValue([STREAM])
    fetchData.mockResolvedValue([
      { location: 'Greece', period: '2026-W09', indicator: 'fluA', value: 4, unit: 'gcL', dimensions: {} },
      { location: 'Greece', period: '2026-W10', indicator: 'fluA', value: 5, unit: 'gcMl', dimensions: {} }])
    renderPanel()
    expect(await screen.findByText('chart.mixedUnits')).toBeTruthy()
  })
})
