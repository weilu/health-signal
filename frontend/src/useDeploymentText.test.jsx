// @vitest-environment jsdom
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { initI18n, setLocale } from './i18n.js'
import { useDeploymentText } from './useDeploymentText.js'

const TEXT = { el: { panels: { deaths: 'Θάνατοι' } }, en: { panels: { deaths: 'Deaths' } }, fr: { panels: { deaths: 'Décès' } } }

function Labels() {
  useDeploymentText(true)
  const { t } = useTranslation()
  return <p>{`${t('panels.deaths', { defaultValue: 'deaths' })} | ${t('nav.logout')}`}</p>
}

function renderLabels() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><Labels /></QueryClientProvider>)
}

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('fetch', vi.fn(async (url) => ({ ok: true, json: async () => TEXT[url.split('/').pop()] })))
})
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

it("shows the deployment's own label over the raw id, keeping the library's text", async () => {
  initI18n({ defaultLocale: 'el', locales: ['en', 'el'] })
  renderLabels()
  expect(await screen.findByText('Θάνατοι | Αποσύνδεση')).toBeTruthy()
  expect(fetch).toHaveBeenCalledWith('/api/locales/el', expect.anything())
})

it('loads the other language when the user switches to it', async () => {
  initI18n({ defaultLocale: 'el', locales: ['en', 'el'] })
  renderLabels()
  await screen.findByText(/Θάνατοι/)
  await act(async () => setLocale('en'))
  expect(await screen.findByText('Deaths | Sign out')).toBeTruthy()
})

it("loads a language the library doesn't ship from the deployment's text, the rest in the library's English", async () => {
  initI18n({ defaultLocale: 'el', locales: ['el', 'fr'] })
  renderLabels()
  await screen.findByText(/Θάνατοι/)
  await act(async () => setLocale('fr'))
  expect(await screen.findByText('Décès | Sign out')).toBeTruthy()
  expect(fetch).toHaveBeenCalledWith('/api/locales/fr', expect.anything())
  expect(document.documentElement.lang).toBe('fr')
})

function Status() {
  const query = useDeploymentText(true)
  return <p>{query.error ? `failed ${query.error.status}` : query.data ? 'loaded' : 'pending'}</p>
}

it("hands its failure to the shell: a lost session (401) must reach sign-in, not leave raw ids", async () => {
  initI18n({ defaultLocale: 'en', locales: ['en'] })
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 401, json: async () => ({}) })))
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><Status /></QueryClientProvider>)
  expect(await screen.findByText('failed 401')).toBeTruthy()
})
