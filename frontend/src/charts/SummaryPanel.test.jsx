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

function renderPanel(location = { value: 'Attica' }, tgt = target) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SummaryPanel panel={{ id: 'summary', label_key: 'panels.summary' }} target={tgt}
          location={location} range={{ from: '2026-W01', to: '2026-W20' }} latest="2026-W20" />
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

  it('reports a failed phase-stream lookup instead of dropping the highlights', async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhaseStreams.mockRejectedValue(Object.assign(new Error('HTTP 500'), { status: 500 }))
    fetchAssessments.mockResolvedValue([{ period: '2026-W10', level: 'low', trend: 'stable', method: 'aedseo' }])
    renderPanel()
    expect(await screen.findByRole('alert')).toBeTruthy()
  })

  it("says when a panel's query matches several assessed series", async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhaseStreams.mockResolvedValue([])
    fetchAssessments.mockResolvedValue([{ period: '2026-W10', level: 'low', method: 'aedseo' },
                                        { period: '2026-W10', level: 'high', method: 'aedseo' }])
    renderPanel()
    expect(await screen.findByText('assessment.ambiguous')).toBeTruthy()
    expect(screen.queryByText('level.high')).toBeNull()
    expect(screen.queryByText('assessment.noneInRange')).toBeNull()
  })

  it("highlights a row as a stream only at the stream's own location", async () => {
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhaseStreams.mockResolvedValue([{ location: 'Greece', pathogen: 'Influenza', method: 'aedseo', role: 'cases',
                                           feed: 'wastewater', series: { indicator: 'fluA' } }])
    fetchAssessments.mockResolvedValue([{ location: 'Attica', period: '2026-W10', level: 'low', method: 'aedseo' }])
    renderPanel(null)
    await screen.findByRole('link', { name: 'load' })
    expect(screen.queryByText('cases')).toBeNull()   // the role chip (its defaultValue: no locale loaded)
  })

  it('groups rows under feed and kind subheadings instead of a page column', async () => {
    const panel = (id, feed, kind, targets) => ({ id, type: 'timeseries', label_key: `panels.${id}`,
      query: { feed, indicator: id, dimensions: {} }, group: { feed, kind, targets } })
    const grouped = { id: 'Influenza', pages: [{ id: 'c', path: '/influenza/c', label_key: 'pages.c', panels: [
      panel('adm', 'clinical', 'pathogen_specific', ['Influenza']),
      panel('ili', 'clinical', 'syndromic', ['SARS-CoV-2', 'Influenza']),
      panel('load', 'wastewater', 'pathogen_specific', ['Influenza']),
    ] }] }
    fetchConfig.mockResolvedValue({ methods: METHOD })
    fetchPhaseStreams.mockResolvedValue([])
    fetchAssessments.mockResolvedValue([{ location: 'Attica', period: '2026-W10', level: 'low', method: 'aedseo' }])
    renderPanel(undefined, grouped)
    const headings = (await screen.findAllByRole('rowheader')).map((h) => h.textContent)
    // The clinical feed has both kinds, so each is named; wastewater has one, so its heading is the feed alone.
    // Feed names fall back to the feed id when no locale is loaded, as here.
    expect(headings).toEqual(['clinical · summary.group.pathogen_specific',
                              'clinical · summary.group.syndromic · summary.sharedAcross', 'wastewater'])
    expect(screen.queryByText('summary.page')).toBeNull()
  })
})
