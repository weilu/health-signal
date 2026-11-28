// @vitest-environment jsdom
import { afterEach, expect, it } from 'vitest'
import { act, cleanup, render, screen } from '@testing-library/react'
import { EmbedFrame, embedSrc } from './EmbedFrame.jsx'

afterEach(cleanup)

it('hands the frame the language and filters in its address', () => {
  const src = embedSrc('forecast/index.html', { lang: 'el', location: 'Attica', range: { preset: '52w', from: '2025-W45', to: '2026-W44' } })
  const url = new URL(src, 'http://x')
  expect(url.pathname).toBe('/embeds/forecast/index.html')
  expect(Object.fromEntries(url.searchParams)).toEqual({ lang: 'el', location: 'Attica', from: '2025-W45', to: '2026-W44' })
})

it("keeps a file name's # or ? in its path rather than reading them as the address's own", () => {
  const url = new URL(embedSrc('forecast/report#1?.html', { lang: 'en', location: null, range: null }), 'http://x')
  expect(url.pathname).toBe('/embeds/forecast/report%231%3F.html')
  expect(url.hash).toBe('')
})

it('leaves out a filter the dashboard does not have', () => {
  expect(embedSrc('f.html', { lang: 'en', location: null, range: null })).toBe('/embeds/f.html?lang=en')
})

it('takes the height its own page reports, and no other window', () => {
  render(<EmbedFrame src="/embeds/f.html" title="Forecast" />)
  const frame = screen.getByTitle('Forecast')
  act(() => window.dispatchEvent(new MessageEvent('message', { data: { type: 'health-signal:height', height: 900 }, source: window })))
  expect(frame.style.height).not.toBe('900px')
  act(() => window.dispatchEvent(new MessageEvent('message', { data: { type: 'health-signal:height', height: 900 }, source: frame.contentWindow })))
  expect(frame.style.height).toBe('900px')
})
