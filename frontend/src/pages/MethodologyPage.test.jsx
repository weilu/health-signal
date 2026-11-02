// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { fetchMethodology } from '../api.js'
import { initI18n } from '../i18n.js'
import { AppRoutes } from '../App.jsx'
import MethodologyPage from './MethodologyPage.jsx'

vi.mock('../api.js', async (original) => ({ ...(await original()), fetchMethodology: vi.fn() }))
afterEach(() => { cleanup(); vi.resetAllMocks() })

function renderPage(markdown) {
  initI18n({ defaultLocale: 'en', locales: ['en', 'el'] })
  fetchMethodology.mockResolvedValue({ markdown, blocks: {} })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter><MethodologyPage /></MemoryRouter></QueryClientProvider>)
}

it('lists its headings as contents, each linking to its section', async () => {
  renderPage('## Status\n\nText.\n\n## Trend\n\nMore.\n')
  const contents = await screen.findByRole('navigation', { name: 'Contents' })
  const links = [...contents.querySelectorAll('a')].map((a) => [a.textContent, a.getAttribute('href')])
  expect(links).toEqual([['Status', '#status'], ['Trend', '#trend']])
  expect(document.getElementById('status').textContent).toBe('Status')
})

it('marks a value taken from the settings', async () => {
  renderPage('The year starts at week `hs:21`.\n')
  const value = await screen.findByText('21')
  expect(value.closest('[data-setting]')).toBeTruthy()
})

it('names a label value in the reader language', async () => {
  renderPage('Waves end below the `hs:t:level.medium` level.\n')
  expect((await screen.findByText('Medium')).closest('[data-setting]')).toBeTruthy()
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

function Where() {
  return <output>{useLocation().pathname}</output>
}

it('sends the old configuration address to the methodology page', async () => {
  initI18n({ defaultLocale: 'en', locales: ['en'] })
  fetchMethodology.mockReturnValue(new Promise(() => {}))
  render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={['/config']}>
    <AppRoutes view={{ targets: [] }} /><Where />
  </MemoryRouter></QueryClientProvider>)
  expect(await screen.findByText('/methodology')).toBeTruthy()
})
