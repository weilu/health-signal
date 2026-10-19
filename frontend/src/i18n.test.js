// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { initI18n, setLocale } from './i18n.js'

const catalogs = import.meta.glob('./locales/*.json', { eager: true, import: 'default' })

function keys(obj, prefix = '') {
  return Object.entries(obj).flatMap(([k, v]) => (typeof v === 'object' ? keys(v, `${prefix}${k}.`) : [`${prefix}${k}`]))
}

describe('locale catalogs', () => {
  // A key missing from one catalog silently falls back to the default language mid-page.
  it('all define the same keys', () => {
    const [[firstPath, first], ...rest] = Object.entries(catalogs)
    for (const [path, catalog] of rest) {
      expect(keys(catalog).sort(), `${path} vs ${firstPath}`).toEqual(keys(first).sort())
    }
  })
})

// initI18n configures i18next's shared instance, so each test re-initialises it from a clean store.
describe('initI18n', () => {
  beforeEach(() => localStorage.clear())
  afterEach(() => vi.restoreAllMocks())

  it('starts in the config default and marks <html lang> with it', () => {
    const i18n = initI18n({ defaultLocale: 'el', locales: ['en', 'el'] })
    expect(i18n.language).toBe('el')
    expect(document.documentElement.lang).toBe('el')
  })
  it('prefers a remembered choice over the config default', () => {
    setLocale('el')
    expect(initI18n({ defaultLocale: 'en', locales: ['en', 'el'] }).language).toBe('el')
  })
  it('ignores a remembered choice the config no longer offers', () => {
    localStorage.setItem('hs.locale', 'el')
    expect(initI18n({ defaultLocale: 'en', locales: ['en'] }).language).toBe('en')
  })
  it('registers only configured locales, warning about one with no catalog', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const i18n = initI18n({ defaultLocale: 'en', locales: ['en', 'fr'] })
    expect(i18n.hasResourceBundle('el', 'translation')).toBe(false)
    expect(i18n.hasResourceBundle('fr', 'translation')).toBe(false)
    expect(warn).toHaveBeenCalledWith(expect.stringContaining('"fr"'))
  })
  it('switching language updates <html lang> and is remembered', () => {
    initI18n({ defaultLocale: 'en', locales: ['en', 'el'] })
    setLocale('el')
    expect(document.documentElement.lang).toBe('el')
    expect(localStorage.getItem('hs.locale')).toBe('el')
  })
})
