// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { fetchAssessments, fetchConfig, fetchPhaseStreams } from '../api.js'
import { SummaryPanel } from './SummaryPanel.jsx'

vi.mock('../api.js', () => ({ fetchAssessments: vi.fn(), fetchConfig: vi.fn(), fetchPhaseStreams: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

const METHOD = { aedseo: { levels: ['very_low', 'low'], phases: [], active_phases: [], stream_roles: [], trend: true } }
const target = { id: 'Influenza', pages: [{ id: 'ww', path: '/influenza/ww', label_key: 'pages.ww', panels: [
  { id: 'load', type: 'timeseries', label_key: 'panels.load', query: { feed: 'wastewater', indicator: 'fluA', dimensions: {} } },
] }] }

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SummaryPanel panel={{ id: 'summary', label_key: 'panels.summary' }} target={target}
          location={{ value: 'Attica' }} range={{ from: '2026-W01', to: '2026-W20' }} latest="2026-W20" />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SummaryPanel', () => {
  it('shows a spinner, not "none", while assessments load', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhaseStreams.mockResolvedValue([])
    fetchAssessments.mockReturnValue(new Promise(() => {}))
    renderPanel()
    expect(await screen.findByRole('progressbar')).toBeTruthy()
    expect(screen.queryByText('summary.none')).toBeNull()
  })

  it('reports a failed lookup as an error, not as nothing assessed', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhaseStreams.mockResolvedValue([])
    fetchAssessments.mockRejectedValue(Object.assign(new Error('HTTP 500'), { status: 500 }))
    renderPanel()
    expect(await screen.findByRole('alert')).toBeTruthy()
    expect(screen.queryByText('summary.none')).toBeNull()
  })

  it('links each row with a real link inside a real table row', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhaseStreams.mockResolvedValue([])
    fetchAssessments.mockResolvedValue([{ period: '2026-W10', level: 'low', trend: 'stable', method: 'aedseo' }])
    renderPanel()
    const link = await screen.findByRole('link', { name: 'load' })
    expect(link.getAttribute('href')).toBe('/influenza/ww')
    expect(link.closest('tr')).toBeTruthy()
  })
})
