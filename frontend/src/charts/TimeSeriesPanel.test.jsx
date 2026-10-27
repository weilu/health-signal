// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { fetchAssessments, fetchConfig, fetchData, fetchThresholds } from '../api.js'
import { TimeSeriesPanel } from './TimeSeriesPanel.jsx'

vi.mock('../api.js', () => ({ fetchAssessments: vi.fn(), fetchConfig: vi.fn(), fetchData: vi.fn(), fetchThresholds: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

const METHOD = { aedseo: { levels: ['very_low', 'low'], phases: [], active_phases: [], stream_roles: [], trend: true } }
const PANEL = { id: 'load', type: 'timeseries', label_key: 'panels.load', query: { feed: 'wastewater', indicator: 'fluA', dimensions: {} } }

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/influenza/ww']}>
        <Routes>
          <Route path="/login" element={<p>login page</p>} />
          <Route path="*" element={<TimeSeriesPanel panel={PANEL} location={{ value: 'Attica' }}
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
})
