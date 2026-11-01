// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { fetchConfig, fetchData, fetchPhases, fetchPhaseStreams } from '../api.js'
import { initI18n } from '../i18n.js'
import { PhasePanel } from './PhasePanel.jsx'

// The real English catalog: the rule text is method content, so the key alone can't show where it lands.
vi.mock('../api.js', () => ({ fetchConfig: vi.fn(), fetchData: vi.fn(), fetchPhases: vi.fn(), fetchPhaseStreams: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

async function tileText(phase) {
  initI18n({ defaultLocale: 'en', locales: ['en'] })
  fetchConfig.mockResolvedValue({ methods: { aedseo: { levels: ['very_low'], trend: true, stream_roles: ['cases'],
    phases: ['in_season', 'out_of_season', 'in_wave', 'between_waves'], active_phases: ['in_season', 'in_wave'] } } })
  fetchPhases.mockResolvedValue([{ location: 'Greece', pathogen: 'Influenza', period: '2026-W10', method: 'aedseo', phase }])
  fetchPhaseStreams.mockResolvedValue([])
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <PhasePanel panel={{ id: 'phase', label_key: 'panels.phase' }} target={{ id: 'Influenza', pages: [] }}
          location={{ value: 'Greece' }} range={{ from: '2026-W09', to: '2026-W10' }} latest="2026-W10" />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return (await screen.findByText(/^(Season|Wave) status$/i)).closest('section').textContent
}

it("states a seasonal pathogen's rule in the status tile, after its as-of line, in season terms only", async () => {
  const tile = await tileText('in_season')
  expect(tile.indexOf('In season while')).toBeGreaterThan(tile.indexOf('As of'))
  expect(tile).not.toMatch(/wave/i)
})

it("states a year-round pathogen's rule in wave terms only", async () => {
  const tile = await tileText('between_waves')
  expect(tile).toContain('Wave status')
  expect(tile).toContain('aedseo wave detection')
  expect(tile).toContain('In a wave while')
  expect(tile).not.toMatch(/season/i)
})


async function runsTile(phases, range) {
  initI18n({ defaultLocale: 'en', locales: ['en'] })
  fetchConfig.mockResolvedValue({ methods: { aedseo: { levels: ['very_low'], trend: true, stream_roles: ['cases'],
    phases: ['in_season', 'out_of_season', 'in_wave', 'between_waves'], active_phases: ['in_season', 'in_wave'] } } })
  fetchPhases.mockResolvedValue(phases.map(([period, phase]) => ({ location: 'Attica', pathogen: 'SARS-CoV-2', period, method: 'aedseo', phase })))
  fetchPhaseStreams.mockResolvedValue([])
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <PhasePanel panel={{ id: 'phase', label_key: 'panels.phase' }} target={{ id: 'SARS-CoV-2', pages: [] }}
          location={{ value: 'Attica' }} range={range} latest={range.to} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return (await screen.findByText(/^(Seasons|Waves) in this range$/)).closest('section').textContent
}

it('lists the waves in the range with their weeks, as the charts shade them', async () => {
  const tile = await runsTile([['2023-W48', 'between_waves'], ['2023-W49', 'in_wave'], ['2023-W50', 'in_wave'],
                               ['2023-W51', 'between_waves'], ['2024-W09', 'in_wave'], ['2024-W10', 'in_wave']],
                              { from: '2023-W40', to: '2024-W10' })
  expect(tile).toContain('Waves in this range')
  expect(tile).toContain('W49 2023 – W50 2023 · 2 weeks')
  expect(tile).toContain('W09 2024 – ongoing · 2 weeks')
  expect(tile).not.toMatch(/season/i)
})

it('says when no wave falls in the range', async () => {
  const tile = await runsTile([['2023-W48', 'between_waves'], ['2023-W49', 'between_waves']], { from: '2023-W40', to: '2023-W49' })
  expect(tile).toContain('No wave in this range')
})


function renderPhase({ target, phases, streams = [], data = [] }) {
  initI18n({ defaultLocale: 'en', locales: ['en'] })
  fetchConfig.mockResolvedValue({ methods: { aedseo: { levels: ['very_low'], trend: true, stream_roles: ['cases', 'admissions'],
    phases: ['in_season', 'out_of_season', 'in_wave', 'between_waves'], active_phases: ['in_season', 'in_wave'] } } })
  fetchPhases.mockReturnValue(phases)
  fetchPhaseStreams.mockResolvedValue(streams)
  fetchData.mockResolvedValue(data)
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter>
        <PhasePanel panel={{ id: 'phase', type: 'phase', label_key: 'panels.phase' }} target={target}
          location={{ value: 'Greece' }} range={{ from: '2026-W09', to: '2026-W10' }} latest="2026-W10" />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

it('titles the card Key signals, with or without a season or wave', async () => {
  renderPhase({ target: { id: 'SARS-CoV-2', pages: [] },
                phases: Promise.resolve([{ location: 'Greece', pathogen: 'SARS-CoV-2', period: '2026-W10', method: 'aedseo', phase: 'between_waves' }]) })
  expect(await screen.findByRole('heading', { name: 'Key signals', level: 2 })).toBeTruthy()
})

it('names each stream chart by its role and the panel that measures it', async () => {
  const panel = { id: 'hospital_admissions', type: 'timeseries', label_key: 'panels.hospital_admissions', query: { feed: 'clinical', indicator: 'hospitaladmissions', dimensions: {} },
                  name: { indicator: 'hospitaladmissions', dimensions: {}, pathogen: true } }
  renderPhase({ target: { id: 'Influenza', pages: [{ panels: [panel] }] },
                phases: Promise.resolve([{ location: 'Greece', pathogen: 'Influenza', period: '2026-W10', method: 'aedseo', phase: 'in_season' }]),
                streams: [{ location: 'Greece', pathogen: 'Influenza', method: 'aedseo', role: 'admissions', feed: 'clinical',
                            series: { indicator: 'hospitaladmissions' } }] })
  expect(await screen.findByRole('heading', { name: 'Health-system load · measured by hospital admissions', level: 3 }))
    .toBeTruthy()
})
