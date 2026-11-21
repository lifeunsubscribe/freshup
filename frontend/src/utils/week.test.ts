import { describe, it, expect } from 'vitest'
import { addDays, formatMonthDay, formatWeekRange, mondayOf, weekDates, weekdayName } from './week'

describe('week helpers', () => {
  it('finds the Monday of a week from any day in it', () => {
    expect(mondayOf(new Date(2026, 10, 16))).toBe('2026-11-16') // Monday
    expect(mondayOf(new Date(2026, 10, 18))).toBe('2026-11-16') // Wednesday
    expect(mondayOf(new Date(2026, 10, 22))).toBe('2026-11-16') // Sunday belongs to the week before it ends
    expect(mondayOf(new Date(2027, 0, 1))).toBe('2026-12-28') // across a year end
  })

  it('adds days across month and year ends', () => {
    expect(addDays('2026-11-28', 7)).toBe('2026-12-05')
    expect(addDays('2027-01-03', -7)).toBe('2026-12-27')
  })

  it('lists the seven days of a week', () => {
    expect(weekDates('2026-11-30')).toEqual([
      '2026-11-30', '2026-12-01', '2026-12-02', '2026-12-03', '2026-12-04', '2026-12-05', '2026-12-06',
    ])
  })

  it('formats days and ranges', () => {
    expect(formatMonthDay('2026-11-16')).toBe('Nov 16')
    expect(weekdayName('2026-11-21')).toBe('Saturday')
    expect(formatWeekRange('2026-11-16')).toBe('Nov 16 – 22')
    expect(formatWeekRange('2026-11-30')).toBe('Nov 30 – Dec 6')
  })
})
