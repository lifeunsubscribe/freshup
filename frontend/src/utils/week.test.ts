import { describe, it, expect } from 'vitest'
import {
  addDays,
  formatDuration,
  formatMonthDay,
  formatWeekRange,
  weekDates,
  weekStartOf,
  weekStartOfDateStr,
  weekTitle,
  weekdayName,
} from './week'

describe('week helpers', () => {
  it('finds the Sunday that starts the week holding any day', () => {
    expect(weekStartOf(new Date(2026, 10, 15))).toBe('2026-11-15') // Sunday starts its own week
    expect(weekStartOf(new Date(2026, 10, 18))).toBe('2026-11-15') // Wednesday
    expect(weekStartOf(new Date(2026, 10, 21))).toBe('2026-11-15') // Saturday ends it
    expect(weekStartOf(new Date(2026, 10, 22))).toBe('2026-11-22') // the next Sunday starts the next
    expect(weekStartOf(new Date(2027, 0, 1))).toBe('2026-12-27') // across a year end
  })

  it('reads a week from a day written as text, and rejects what is not a date', () => {
    expect(weekStartOfDateStr('2026-11-19')).toBe('2026-11-15')
    expect(weekStartOfDateStr('soon')).toBeNull()
    expect(weekStartOfDateStr('2026-11-1')).toBeNull()
  })

  it('names weeks by where they are', () => {
    expect(weekTitle('2026-11-15', '2026-11-15')).toBe('This week')
    expect(weekTitle('2026-11-22', '2026-11-15')).toBe('Next week')
    expect(weekTitle('2026-11-08', '2026-11-15')).toBe('Last week')
    expect(weekTitle('2026-11-29', '2026-11-15')).toBe('Week of Nov 29')
  })

  it('writes durations', () => {
    expect(formatDuration(45)).toBe('45 min')
    expect(formatDuration(180)).toBe('3 h')
    expect(formatDuration(185)).toBe('3 h 5 min')
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
    expect(formatWeekRange('2026-11-15')).toBe('Nov 15 – 21')
    expect(formatWeekRange('2026-11-29')).toBe('Nov 29 – Dec 5')
  })
})
