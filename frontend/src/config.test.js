// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest'
import { getConfig, siteTitle } from './config.js'

afterEach(() => { delete window.__HS_CONFIG__ })

describe('siteTitle', () => {
  it("is the deployment's title in the current language", () => {
    window.__HS_CONFIG__ = { title: 'Surveillance', titles: { el: 'Επιτήρηση' } }
    expect(siteTitle(getConfig(), 'el')).toBe('Επιτήρηση')
  })
  it('falls back to the configured title for a language without one', () => {
    window.__HS_CONFIG__ = { title: 'Surveillance', titles: { el: 'Επιτήρηση' } }
    expect(siteTitle(getConfig(), 'en')).toBe('Surveillance')
    window.__HS_CONFIG__ = { title: 'Surveillance' }
    expect(siteTitle(getConfig(), 'el')).toBe('Surveillance')
  })
})
