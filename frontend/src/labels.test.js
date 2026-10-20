import { describe, expect, it } from 'vitest'
import { configLabel, weekStamp } from './labels.js'

const t = (key, opts) => (key === 'targets.covid' ? 'COVID-19' : opts?.defaultValue ?? '')

describe('configLabel', () => {
  it('translates a known key', () => expect(configLabel(t, 'targets.covid', 'covid')).toBe('COVID-19'))
  it('falls back to the id for an untranslated key', () => expect(configLabel(t, 'targets.flu', 'flu')).toBe('flu'))
  it('uses the id when no key is configured', () => {
    expect(configLabel(t, null, 'rsv')).toBe('rsv')
    expect(configLabel(t, undefined, 'rsv')).toBe('rsv')
  })
})

describe('weekStamp', () => {
  it('passes the week and year to the translation', () => {
    const t = (key, vars) => `${key}:${vars.week}/${vars.year}`
    expect(weekStamp(t, '2025-W07')).toBe('range.week:07/2025')
  })
})
