// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { fetchConfig, fetchMethodology } from '../api.js'
import { initI18n } from '../i18n.js'
import { AppRoutes } from '../App.jsx'
import MethodologyPage from './MethodologyPage.jsx'

vi.mock('../api.js', async (original) => ({ ...(await original()), fetchConfig: vi.fn(), fetchMethodology: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

function renderPage(markdown, entry = '/methodology') {
  initI18n({ defaultLocale: 'en', locales: ['en', 'el'] })
  fetchConfig.mockResolvedValue({ methods: { aedseo: {}, mem: {} } })
  fetchMethodology.mockResolvedValue({ markdown, blocks: {} })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[entry]}>
    <MethodologyPage /><Where testId="where" />
  </MemoryRouter></QueryClientProvider>)
}

it('lists its headings as contents, each linking to its section', async () => {
  renderPage('## Status\n\nText.\n\n## Trend\n\nMore.\n')
  const contents = await screen.findByRole('navigation', { name: 'Contents' })
  const links = [...contents.querySelectorAll('a')].map((a) => [a.textContent, a.getAttribute('href')])
  expect(links).toEqual([['Status', '/methodology#status'], ['Trend', '/methodology#trend']])
  expect(document.getElementById('status').textContent).toBe('Status')
})

it('scrolls to a section and stays on the page', async () => {
  // The served page carries a <base href>, so a bare "#status" would resolve against it and leave the page.
  Element.prototype.scrollIntoView = vi.fn()
  renderPage('## Status\n\nText.\n')
  fireEvent.click(await screen.findByRole('link', { name: 'Status' }))
  expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
  expect(screen.getByTestId('where').textContent).toBe('/methodology#status')
})

it('marks a value taken from the settings', async () => {
  renderPage('The year starts at week `hs:21`.\n')
  const value = await screen.findByText('21')
  expect(value.closest('[data-setting]')).toBeTruthy()
})

it('names a label value in the reader language, mid-sentence', async () => {
  renderPage('Waves end below the `hs:t:level.medium` level.\n')
  expect((await screen.findByText('medium')).closest('[data-setting]')).toBeTruthy()
})

it('typesets maths', async () => {
  const { container } = renderPage('A weekly change of $e^{r} - 1$.\n')
  await screen.findByText(/A weekly change of/)
  expect(container.querySelector('.katex')).toBeTruthy()
})

it('never renders raw HTML', async () => {
  const { container } = renderPage('Plain <b>bold</b> text.\n')
  await screen.findByText(/Plain/)
  expect(container.querySelector('b')).toBeNull()
})

function Where({ testId }) {
  const location = useLocation()
  return <output data-testid={testId}>{location.pathname + location.search + location.hash}</output>
}

it('sends the old configuration address to the methodology page', async () => {
  initI18n({ defaultLocale: 'en', locales: ['en'] })
  fetchMethodology.mockReturnValue(new Promise(() => {}))
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/config']}>
    <AppRoutes view={{ targets: [] }} /><Where />
  </MemoryRouter></QueryClientProvider>)
  expect(await screen.findByText('/methodology')).toBeTruthy()
})

it('shows the method selected in the header', async () => {
  renderPage('## MEM\n', '/methodology?method=mem')
  await screen.findByRole('heading', { name: 'MEM' })
  await waitFor(() => expect(fetchMethodology).toHaveBeenLastCalledWith('en', 'mem'))
})

it("links a heading with inline markup to the heading's own anchor", async () => {
  renderPage('## Methods [source](https://example.org) *now*\n\nText.\n')
  const contents = await screen.findByRole('navigation', { name: 'Contents' })
  const link = await vi.waitFor(() => { const a = contents.querySelector('a'); if (!a) throw new Error('no contents yet'); return a })
  const heading = document.querySelector('h2')
  expect(link.textContent).toBe(heading.textContent)
  expect(link.getAttribute('href')).toBe(`/methodology#${heading.id}`)
})

it("keeps the header's filters when following a contents link", async () => {
  Element.prototype.scrollIntoView = vi.fn()
  renderPage('## Status\n\nText.\n', '/methodology?location=Attica')
  fireEvent.click(await screen.findByRole('link', { name: 'Status' }))
  expect(screen.getByTestId('where').textContent).toBe('/methodology?location=Attica#status')
})

it('names a feed or quality the deployment gives no label by its id', async () => {
  renderPage('Feeds: `hs:t:feeds.sewage`.\n')
  expect(await screen.findByText('sewage')).toBeTruthy()
})
