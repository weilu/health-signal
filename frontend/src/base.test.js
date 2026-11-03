// @vitest-environment jsdom
import { afterEach, expect, test } from 'vitest'
import { url } from './base.js'

afterEach(() => document.head.querySelector('base')?.remove())

test('paths resolve under the base the server injects', () => {
  const base = document.createElement('base')
  base.setAttribute('href', '/content/abc/')
  document.head.append(base)
  expect(url('/api/config')).toBe('/content/abc/api/config')
  expect(url('/')).toBe('/content/abc/')
})

test('paths stay at the root without a base', () => {
  expect(url('/api/config')).toBe('/api/config')
})
