// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { fetchAssessments, fetchConfig, fetchData, fetchThresholds } from '../api.js'
import { TimeSeriesPanel } from './TimeSeriesPanel.jsx'

// The chart draws on a canvas; its props are what the panel decides.
const charted = []
vi.mock('./TimeSeriesChart.jsx', () => ({ TimeSeriesChart: (props) => { charted.push(props); return null },
                                          useChartPalette: () => ['#000'] }))

vi.mock('../api.js', () => ({ fetchAssessments: vi.fn(), fetchConfig: vi.fn(), fetchData: vi.fn(), fetchThresholds: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks(); charted.length = 0 })

const METHOD = { aedseo: { levels: ['very_low', 'low'], phases: [], active_phases: [], stream_roles: [], trend: true } }
const PANEL = { id: 'load', type: 'timeseries', label_key: 'panels.load', query: { feed: 'wastewater', indicator: 'fluA', dimensions: {} } }

function renderPanel(location = { value: 'Attica' }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/influenza/ww']}>
        <Routes>
          <Route path="/login" element={<p>login page</p>} />
          <Route path="*" element={<TimeSeriesPanel panel={PANEL} location={location}
            range={{ from: '2026-W01', to: '2026-W20' }} latest="2026-W20" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TimeSeriesPanel assessments', () => {
  it('says the status is unavailable when the assessment lookup fails', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchData.mockResolvedValue([])
    fetchThresholds.mockResolvedValue([])
    fetchAssessments.mockRejectedValue(Object.assign(new Error('HTTP 500'), { status: 500 }))
    renderPanel()
    expect(await screen.findByText('assessment.unavailable')).toBeTruthy()
  })

  it('sends an expired session from a threshold lookup to login', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchData.mockResolvedValue([])
    fetchAssessments.mockResolvedValue([])
    fetchThresholds.mockRejectedValue(Object.assign(new Error('HTTP 401'), { status: 401 }))
    renderPanel()
    expect(await screen.findByText('login page')).toBeTruthy()
  })

  it("draws no bands or shading from other series' rows, and says why", async () => {
    // No location filter: Greece is plotted, but the overlays' rows also hold Attica.
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchData.mockResolvedValue([{ location: 'Greece', period: '2026-W10', indicator: 'fluA', value: 5, unit: 'gcL', dimensions: {} }])
    fetchAssessments.mockResolvedValue([{ location: 'Greece', period: '2026-W10', level: 'low', phase: 'in_season', method: 'aedseo' },
                                        { location: 'Attica', period: '2026-W09', level: 'low', phase: 'in_season', method: 'aedseo' }])
    fetchThresholds.mockResolvedValue([{ location: 'Attica', dimensions: {}, from: '2025-W21', to: '2026-W20', level: 'low', lower_bound: 1 }])
    renderPanel(null)
    expect(await screen.findByText('assessment.ambiguous')).toBeTruthy()
    const props = charted.at(-1)
    expect(props.bands ?? []).toEqual([])
    expect([...(props.shading ?? [])]).toEqual([])
  })
})
