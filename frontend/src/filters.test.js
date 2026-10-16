import { describe, expect, it } from 'vitest'
import { panelParams, selectedLocation, withLocation } from './filters.js'

const filter = { default: 'Greece', options: [{ value: 'Greece' }, { value: 'Attica' }] }

describe('selectedLocation', () => {
  it('reads a configured location from the URL', () => expect(selectedLocation(filter, '?location=Attica')).toBe('Attica'))
  it('falls back to the default when absent or not offered', () => {
    expect(selectedLocation(filter, '')).toBe('Greece')
    expect(selectedLocation(filter, '?location=Narnia')).toBe('Greece')
  })
  it('is null when no location filter is configured', () => expect(selectedLocation(null, '?location=Attica')).toBeNull())
})

describe('withLocation', () => {
  it('carries the selection on a link', () => expect(withLocation('/covid', 'Attica')).toBe('/covid?location=Attica'))
  it('encodes it', () => expect(withLocation('/covid', 'Central Macedonia')).toBe('/covid?location=Central+Macedonia'))
  it('leaves the path alone without one', () => expect(withLocation('/covid', null)).toBe('/covid'))
})

describe('panelParams', () => {
  const query = { indicator: 'positivity', dimensions: { survtype: 'SARI virological', pathogen: 'RSV' } }
  it('flattens the indicator, dimensions and selected location into /api/data params', () =>
    expect(panelParams(query, 'Attica')).toEqual({ indicator: 'positivity', survtype: 'SARI virological', pathogen: 'RSV', location: 'Attica' }))
  it('omits location when none is selected', () => expect(panelParams(query, null)).not.toHaveProperty('location'))
  it('handles a panel with no dimensions', () => expect(panelParams({ indicator: 'deaths' }, null)).toEqual({ indicator: 'deaths' }))
})
