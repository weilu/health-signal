import { describe, expect, it } from 'vitest'
import { activePage } from './nav.js'

const targets = [
  { id: 'covid', pages: [{ id: 'c', path: '/covid' }] },
  { id: 'flu', pages: [{ id: 'f1', path: '/influenza' }, { id: 'f2', path: '/influenza/hospital' }] },
]

describe('activePage', () => {
  it('finds the page and its target', () => {
    expect(activePage(targets, '/covid')).toEqual({ target: targets[0], page: targets[0].pages[0] })
  })
  it("activates a target from any of its pages", () => {
    expect(activePage(targets, '/influenza/hospital')?.target.id).toBe('flu')
    expect(activePage(targets, '/influenza/hospital')?.page.id).toBe('f2')
  })
  it('matches as the router does: any case, optional trailing slash', () => {
    expect(activePage(targets, '/Influenza/Hospital/')?.page.id).toBe('f2')
  })
  it('is null off the configured pages', () => {
    expect(activePage(targets, '/config')).toBeNull()
    expect(activePage(targets, '/nowhere')).toBeNull()
  })
})
