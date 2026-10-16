import { describe, expect, it } from 'vitest'
import { boundaryState } from './boundary.js'

describe('boundaryState', () => {
  it('loads while pending', () => expect(boundaryState({ isPending: true })).toBe('loading'))
  it('redirects on 401, even with cached data', () =>
    expect(boundaryState({ error: { status: 401 }, data: { x: 1 } })).toBe('unauth'))
  it('keeps cached data when a background refetch fails', () =>
    expect(boundaryState({ isError: true, error: { status: 503 }, data: [] })).toBe('ok'))
  it('errors when there is nothing to show', () =>
    expect(boundaryState({ isError: true, error: { status: 500 } })).toBe('error'))
})
