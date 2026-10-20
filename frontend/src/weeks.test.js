import { describe, expect, it } from 'vitest'
import { addWeeks, isWeek, weekRange } from './weeks.js'

describe('weekRange', () => {
  it('crosses ISO years, including 53-week ones', () => {
    expect(weekRange('2020-W52', '2021-W01')).toEqual(['2020-W52', '2020-W53', '2021-W01'])
    expect(weekRange('2024-W52', '2025-W01')).toEqual(['2024-W52', '2025-W01'])
  })
  it('maps weeks whose Monday falls in the previous calendar year', () => {
    expect(weekRange('2025-W01', '2025-W01')).toEqual(['2025-W01'])  // Monday 2024-12-30
  })
})

describe('addWeeks', () => {
  it('steps across ISO years in both directions', () => {
    expect(addWeeks('2020-W53', 1)).toBe('2021-W01')
    expect(addWeeks('2025-W01', -1)).toBe('2024-W52')
  })
})

describe('isWeek', () => {
  it('accepts real weeks only', () => {
    expect(isWeek('2020-W53')).toBe(true)
    expect(['2025-W53', '2025-W00', '2025-W5', 'last', null].map(isWeek)).toEqual([false, false, false, false, false])
  })
})
