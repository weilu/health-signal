import { describe, expect, it, vi } from 'vitest'
import { pickResources } from './i18n.js'

describe('pickResources', () => {
  it('registers only configured locales', () => {
    expect(Object.keys(pickResources({ en: {}, el: {} }, ['en']))).toEqual(['en'])
  })
  it('skips a configured locale with no catalog, with a warning', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(pickResources({ en: {} }, ['en', 'fr'])).toEqual({ en: { translation: {} } })
    expect(warn).toHaveBeenCalledOnce()
  })
})
