// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fetchConfig } from '../api.js'
import { initI18n, setLocale } from '../i18n.js'
import { Block } from './blocks.jsx'

vi.mock('../api.js', async (original) => ({ ...(await original()), fetchConfig: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

const CONFIG = {
  filters: { location: { options: [{ value: 'Greece', label_key: null }, { value: 'Attica', label_key: null }] } },
  methods: { aedseo: { levels: ['very_low', 'low', 'medium', 'high', 'very_high'], stream_roles: ['cases', 'admissions'] } },
  targets: [{ id: 'SARS-CoV-2', label_key: 'targets.SARS-CoV-2', pages: [
    { id: 'clinical', panels: [{ id: 'hospital_admissions', label_key: 'panels.hospital_admissions',
                                 name: { indicator: 'hospitaladmissions', dimensions: {} } }] },
    { id: 'wastewater', panels: [{ id: 'ww_load', label_key: 'panels.ww_load', name: { indicator: 'cov', dimensions: {} } }] }] }],
}
const BLOCKS = {
  streams: [
    { target: 'SARS-CoV-2', location: 'Attica', streams: { cases: { page: 'wastewater', panel: 'ww_load' },
                                                           admissions: { page: 'clinical', panel: 'hospital_admissions' } } },
    { target: 'SARS-CoV-2', location: 'Greece', streams: null }],
  indicator_models: [{ kind: 'count', units: ['count'] },
                     { kind: 'rate', indicator: 'SARIrate', unit: 'per_1000_admissions', denominator: 'hospitaladmissions', per: 1000 },
                     { kind: 'constant' }],
  phase_patterns: [{ target: 'SARS-CoV-2', pattern: 'waves' }],
  levels: { method: 'aedseo' },
}

function renderBlock(name, lang = 'en') {
  initI18n({ defaultLocale: lang, locales: ['en', 'el'] })
  fetchConfig.mockResolvedValue(CONFIG)
  return render(<QueryClientProvider client={new QueryClient()}><Block name={name} blocks={BLOCKS} /></QueryClientProvider>)
}

it("names each stream as its panel on the tab, under its role", async () => {
  renderBlock('streams')
  const row = (await screen.findByText('Attica')).closest('tr')
  expect(within(row).getByText('SARS-CoV-2 in wastewater')).toBeTruthy()
  expect(screen.getByRole('columnheader', { name: 'Community spread' })).toBeTruthy()
})

it('says a pathogen and location with no streams is not configured, under each role', async () => {
  renderBlock('streams')
  expect(within((await screen.findByText('Greece')).closest('tr')).getAllByText('Not configured')).toHaveLength(2)
})

it('reads indicator models as rules', async () => {
  renderBlock('indicator_models')
  const row = (await screen.findByText(/SARI rate/)).closest('tr')
  expect(row.textContent).toMatch(/admissions/)
  expect(row.textContent).toContain('1,000')
})

it('shows each level with its colour group', async () => {
  renderBlock('levels')
  await screen.findByText('Very high')
  expect([...document.querySelectorAll('tr[data-tone]')].map((r) => r.dataset.tone))
    .toEqual(['success', 'success', 'warning', 'error', 'error'])
})

it('sits in a box with its caption', async () => {
  renderBlock('phase_patterns')
  expect(await screen.findByText("This dashboard's season or wave by pathogen")).toBeTruthy()
})

it("follows the reader's language", async () => {
  renderBlock('streams')
  await screen.findByText('Attica')
  await act(async () => setLocale('el'))
  expect(await screen.findAllByText('Δεν έχει οριστεί')).toHaveLength(2)
})
