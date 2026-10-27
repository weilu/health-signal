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

const METHOD = { aedseo: { levels: ['very_low', 'low'], phases: ['in_season', 'out_of_season'], active_phases: ['in_season'],
  stream_roles: [], trend: true } }
const GREECE_W10 = { location: 'Greece', period: '2026-W10', indicator: 'fluA', value: 5, unit: 'gcL', dimensions: {} }
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

  it("uses only the plotted series' rows for tiles, bands and shading", async () => {
    // No location filter: Greece is plotted, but the lookups also hold Attica.
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchData.mockResolvedValue([GREECE_W10])
    fetchAssessments.mockResolvedValue([{ location: 'Greece', period: '2026-W10', level: 'low', phase: 'in_season', method: 'aedseo' },
                                        { location: 'Attica', period: '2026-W09', level: 'high', phase: 'in_season', method: 'aedseo' }])
    fetchThresholds.mockResolvedValue([{ location: 'Attica', dimensions: {}, from: '2025-W21', to: '2026-W20', level: 'low', lower_bound: 1 }])
    renderPanel(null)
    expect(await screen.findByText('level.low')).toBeTruthy()
    expect(screen.queryByText('level.high')).toBeNull()
    const props = charted.at(-1)
    expect(props.bands ?? []).toEqual([])
    expect([...props.shading]).toEqual(['2026-W10'])
  })

  it("shows no other population's status or bands on a chart", async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchData.mockResolvedValue([GREECE_W10])
    fetchAssessments.mockResolvedValue([{ location: 'Attica', period: '2026-W10', level: 'high', method: 'aedseo' }])
    fetchThresholds.mockResolvedValue([{ location: 'Attica', dimensions: {}, from: '2025-W21', to: '2026-W20', level: 'low', lower_bound: 1 }])
    renderPanel(null)
    await vi.waitFor(() => expect(charted.length).toBeGreaterThan(0))
    expect(screen.queryByText('level.high')).toBeNull()
    expect(charted.at(-1).bands ?? []).toEqual([])
  })

  it('draws threshold bands for a series with no assessment history', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchData.mockResolvedValue([GREECE_W10])
    fetchAssessments.mockResolvedValue([])
    fetchThresholds.mockResolvedValue([{ location: 'Greece', dimensions: {}, from: '2025-W21', to: '2026-W20', level: 'low', lower_bound: 1 }])
    renderPanel({ value: 'Greece' })
    await vi.waitFor(() => expect((charted.at(-1)?.bands ?? []).length).toBeGreaterThan(0))
  })


  it('shows no tile or overlay when its own data mixes series', async () => {
    // W09 has no fraction, W10 has fraction=liq: the chart reports a mix, so no one series' status applies.
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchData.mockResolvedValue([{ ...GREECE_W10, period: '2026-W09' }, { ...GREECE_W10, dimensions: { fraction: 'liq' } }])
    fetchAssessments.mockResolvedValue([{ location: 'Greece', period: '2026-W09', level: 'low', phase: 'in_season', method: 'aedseo', dimensions: {} }])
    fetchThresholds.mockResolvedValue([{ location: 'Greece', dimensions: {}, from: '2025-W21', to: '2026-W20', level: 'low', lower_bound: 1 }])
    renderPanel({ value: 'Greece' })
    await screen.findByText('chart.mixedSeries')
    // Let the assessment lookups land: a tile would appear only after them.
    await vi.waitFor(() => expect(fetchAssessments).toHaveBeenCalled())
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(screen.queryByText('level.low')).toBeNull()
  })
})
