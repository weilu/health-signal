import { describe, expect, it } from 'vitest'
import { panelParams, rangePresets, selectedLocation, selectedRange, updateSearch, withFilters, yearLabel } from './filters.js'

const filter = { default: 'Greece', options: [{ value: 'Greece' }, { value: 'Attica' }] }

describe('selectedLocation', () => {
  it('reads a configured location from the URL', () => expect(selectedLocation(filter, '?location=Attica')).toBe('Attica'))
  it('falls back to the default when absent or not offered', () => {
    expect(selectedLocation(filter, '')).toBe('Greece')
    expect(selectedLocation(filter, '?location=Narnia')).toBe('Greece')
  })
  it('is null when no location filter is configured', () => expect(selectedLocation(null, '?location=Attica')).toBeNull())
})

describe('withFilters', () => {
  it('carries the filter params onto a link and drops the rest', () =>
    expect(withFilters('/covid', '?location=Central+Macedonia&range=all&tab=2')).toBe('/covid?location=Central+Macedonia&range=all'))
  it('leaves the path alone without filters', () => expect(withFilters('/covid', '')).toBe('/covid'))
})

describe('updateSearch', () => {
  it('sets and removes params', () => expect(updateSearch('?location=Attica&from=2025-W01', { from: null, range: 'all' })).toBe('?location=Attica&range=all'))
  it('is empty once nothing is left', () => expect(updateSearch('?range=all', { range: null })).toBe(''))
})

const periods = { first: '2023-W40', last: '2025-W42' }
const calendar = { default_weeks: 52, year_start_week: 1 }
const respiratory = { default_weeks: 52, year_start_week: 21 }

describe('rangePresets', () => {
  it('offers the trailing window, all history, then each year newest first', () =>
    expect(rangePresets(calendar, periods)).toEqual(['last', 'all', 'year:2025', 'year:2024', 'year:2023']))
  it('names a W21-W20 year by its start, so early weeks belong to the year before', () =>
    expect(rangePresets(respiratory, { first: '2023-W10', last: '2025-W10' })).toEqual(['last', 'all', 'year:2024', 'year:2023', 'year:2022']))
  it('drops the trailing window when all history is the default', () =>
    expect(rangePresets({ ...calendar, default_weeks: 'all' }, periods)[0]).toBe('all'))
})

describe('selectedRange', () => {
  it('defaults to the trailing window counted back from the latest week', () =>
    expect(selectedRange(calendar, periods, '')).toEqual({ preset: 'last', from: '2024-W43', to: '2025-W42' }))
  it('stops a trailing window longer than the data at its first week', () =>
    expect(selectedRange({ ...calendar, default_weeks: 520 }, periods, '').from).toBe('2023-W40'))
  it('opens on all history when configured', () =>
    expect(selectedRange({ ...calendar, default_weeks: 'all' }, periods, '')).toEqual({ preset: 'all', from: '2023-W40', to: '2025-W42' }))
  it('bounds a year preset, clamped to the data', () => {
    expect(selectedRange(calendar, periods, '?range=year:2024')).toMatchObject({ from: '2024-W01', to: '2024-W52' })
    expect(selectedRange(calendar, periods, '?range=year:2025')).toMatchObject({ from: '2025-W01', to: '2025-W42' })
    expect(selectedRange(respiratory, periods, '?range=year:2024')).toMatchObject({ from: '2024-W21', to: '2025-W20' })
  })
  it('ends a calendar year on W53 when it has one', () =>
    expect(selectedRange(calendar, { first: '2020-W01', last: '2021-W10' }, '?range=year:2020').to).toBe('2020-W53'))
  it('reads a custom range, ordered and clamped to the data', () =>
    expect(selectedRange(calendar, periods, '?from=2025-W10&to=2020-W01')).toEqual({ preset: 'custom', from: '2023-W40', to: '2025-W10' }))
  it('falls back to the default for anything it cannot read', () => {
    for (const search of ['?range=year:1999', '?range=forever', '?from=2025-W53&to=2025-W10', '?from=2025-W10']) {
      expect(selectedRange(calendar, periods, search).preset).toBe('last')
    }
  })
  it('is null with no data to range over', () => expect(selectedRange(calendar, null, '')).toBeNull())
})

describe('yearLabel', () => {
  it('is the plain year for calendar years and a span otherwise', () => {
    expect(yearLabel(2025, 1)).toBe('2025')
    expect(yearLabel(2024, 21)).toBe('2024–25')
  })
})

describe('panelParams', () => {
  const query = { feed: 'clinical', indicator: 'positivity', dimensions: { survtype: 'SARI virological', pathogen: 'RSV' } }
  it('flattens the feed, indicator, dimensions, location and range into /api/data params', () =>
    expect(panelParams(query, 'Attica', { from: '2024-W43', to: '2025-W42' })).toEqual({
      feed: 'clinical', indicator: 'positivity', survtype: 'SARI virological', pathogen: 'RSV', location: 'Attica', week_from: '2024-W43', week_to: '2025-W42',
    }))
  it('omits filters that are not set', () => expect(panelParams({ feed: 'clinical', indicator: 'deaths' }, null, null)).toEqual({ feed: 'clinical', indicator: 'deaths' }))
})
