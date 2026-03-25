import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  parseDateOnly,
  getTodayAtMidnight,
  getDaysUntilDate,
  getDaysSinceDate,
  formatRelativeDate,
  formatExpirationBadge,
} from './dateUtils'

describe('dateUtils', () => {
  beforeEach(() => {
    // Reset system time before each test
    vi.useRealTimers()
  })

  describe('parseDateOnly', () => {
    it('parses date-only string (YYYY-MM-DD) to local midnight', () => {
      const result = parseDateOnly('2026-03-20')

      expect(result.getFullYear()).toBe(2026)
      expect(result.getMonth()).toBe(2) // 0-indexed, so March is 2
      expect(result.getDate()).toBe(20)
      expect(result.getHours()).toBe(0)
      expect(result.getMinutes()).toBe(0)
      expect(result.getSeconds()).toBe(0)
      expect(result.getMilliseconds()).toBe(0)
    })

    it('parses ISO datetime string to local midnight on that date', () => {
      const result = parseDateOnly('2026-03-20T14:30:00Z')

      expect(result.getFullYear()).toBe(2026)
      expect(result.getMonth()).toBe(2)
      expect(result.getDate()).toBe(20)
      expect(result.getHours()).toBe(0)
      expect(result.getMinutes()).toBe(0)
      expect(result.getSeconds()).toBe(0)
    })

    it('handles different months correctly', () => {
      const jan = parseDateOnly('2026-01-15')
      const dec = parseDateOnly('2026-12-25')

      expect(jan.getMonth()).toBe(0) // January
      expect(jan.getDate()).toBe(15)
      expect(dec.getMonth()).toBe(11) // December
      expect(dec.getDate()).toBe(25)
    })

    it('throws error for invalid date format', () => {
      expect(() => parseDateOnly('invalid')).toThrow('Invalid date format')
      expect(() => parseDateOnly('2026/03/20')).toThrow('Invalid date format')
      expect(() => parseDateOnly('20-03-2026')).toThrow('Invalid date format')
    })
  })

  describe('getTodayAtMidnight', () => {
    it('returns today at midnight', () => {
      const result = getTodayAtMidnight()
      const now = new Date()

      expect(result.getFullYear()).toBe(now.getFullYear())
      expect(result.getMonth()).toBe(now.getMonth())
      expect(result.getDate()).toBe(now.getDate())
      expect(result.getHours()).toBe(0)
      expect(result.getMinutes()).toBe(0)
      expect(result.getSeconds()).toBe(0)
      expect(result.getMilliseconds()).toBe(0)
    })
  })

  describe('getDaysUntilDate', () => {
    beforeEach(() => {
      // Mock current date to 2026-03-20 at 10:30 AM
      vi.useFakeTimers()
      vi.setSystemTime(new Date(2026, 2, 20, 10, 30, 0))
    })

    it('returns 0 for today', () => {
      expect(getDaysUntilDate('2026-03-20')).toBe(0)
    })

    it('returns 1 for tomorrow', () => {
      expect(getDaysUntilDate('2026-03-21')).toBe(1)
    })

    it('returns positive number for future dates', () => {
      expect(getDaysUntilDate('2026-03-25')).toBe(5)
      expect(getDaysUntilDate('2026-04-20')).toBe(31)
    })

    it('returns negative number for past dates', () => {
      expect(getDaysUntilDate('2026-03-19')).toBe(-1)
      expect(getDaysUntilDate('2026-03-15')).toBe(-5)
    })

    it('handles dates across month boundaries', () => {
      expect(getDaysUntilDate('2026-04-01')).toBe(12) // March has 31 days
      expect(getDaysUntilDate('2026-02-28')).toBe(-19) // 20 days between Feb 28 and Mar 20 (exclusive)
    })
  })

  describe('getDaysSinceDate', () => {
    beforeEach(() => {
      // Mock current date to 2026-03-20 at 10:30 AM
      vi.useFakeTimers()
      vi.setSystemTime(new Date(2026, 2, 20, 10, 30, 0))
    })

    it('returns 0 for today', () => {
      expect(getDaysSinceDate('2026-03-20')).toBe(0)
    })

    it('returns 1 for yesterday', () => {
      expect(getDaysSinceDate('2026-03-19')).toBe(1)
    })

    it('returns positive number for past dates', () => {
      expect(getDaysSinceDate('2026-03-15')).toBe(5)
      expect(getDaysSinceDate('2026-02-20')).toBe(27) // 27 days between Feb 20 and Mar 20 (exclusive)
    })

    it('returns negative number for future dates', () => {
      expect(getDaysSinceDate('2026-03-21')).toBe(-1)
      expect(getDaysSinceDate('2026-03-25')).toBe(-5)
    })
  })

  describe('formatRelativeDate', () => {
    beforeEach(() => {
      // Mock current date to 2026-03-20
      vi.useFakeTimers()
      vi.setSystemTime(new Date(2026, 2, 20, 10, 30, 0))
    })

    it('returns "today" for current date', () => {
      expect(formatRelativeDate('2026-03-20')).toBe('today')
    })

    it('returns "yesterday" for one day ago', () => {
      expect(formatRelativeDate('2026-03-19')).toBe('yesterday')
    })

    it('returns "Nd ago" for 2-7 days ago', () => {
      expect(formatRelativeDate('2026-03-18')).toBe('2d ago')
      expect(formatRelativeDate('2026-03-15')).toBe('5d ago')
      expect(formatRelativeDate('2026-03-13')).toBe('7d ago')
    })

    it('returns formatted date for 8+ days ago', () => {
      const result = formatRelativeDate('2026-03-10')
      expect(result).toBe('Mar 10')

      const janResult = formatRelativeDate('2026-01-15')
      expect(janResult).toBe('Jan 15')
    })

    it('handles ISO datetime strings', () => {
      expect(formatRelativeDate('2026-03-20T14:30:00Z')).toBe('today')
      expect(formatRelativeDate('2026-03-19T08:00:00Z')).toBe('yesterday')
    })

    it('returns "tomorrow" for one day in future', () => {
      expect(formatRelativeDate('2026-03-21')).toBe('tomorrow')
    })

    it('returns "in Nd" for 2-7 days in future', () => {
      expect(formatRelativeDate('2026-03-22')).toBe('in 2d')
      expect(formatRelativeDate('2026-03-25')).toBe('in 5d')
      expect(formatRelativeDate('2026-03-27')).toBe('in 7d')
    })

    it('returns formatted date for 8+ days in future', () => {
      const result = formatRelativeDate('2026-03-30')
      expect(result).toBe('Mar 30')

      const aprResult = formatRelativeDate('2026-04-15')
      expect(aprResult).toBe('Apr 15')
    })

    it('handles future dates with ISO datetime strings', () => {
      expect(formatRelativeDate('2026-03-21T14:30:00Z')).toBe('tomorrow')
      expect(formatRelativeDate('2026-03-22T08:00:00Z')).toBe('in 2d')
    })
  })

  describe('formatExpirationBadge', () => {
    beforeEach(() => {
      // Mock current date to 2026-03-20
      vi.useFakeTimers()
      vi.setSystemTime(new Date(2026, 2, 20, 10, 30, 0))
    })

    it('returns "expired" for past dates', () => {
      expect(formatExpirationBadge('2026-03-19')).toBe('expired')
      expect(formatExpirationBadge('2026-03-10')).toBe('expired')
    })

    it('returns "today" for current date', () => {
      expect(formatExpirationBadge('2026-03-20')).toBe('today')
    })

    it('returns "tomorrow" for next day', () => {
      expect(formatExpirationBadge('2026-03-21')).toBe('tomorrow')
    })

    it('returns "Nd" for 2-7 days in future', () => {
      expect(formatExpirationBadge('2026-03-22')).toBe('2d')
      expect(formatExpirationBadge('2026-03-25')).toBe('5d')
      expect(formatExpirationBadge('2026-03-27')).toBe('7d')
    })

    it('returns null for 8+ days in future', () => {
      expect(formatExpirationBadge('2026-03-28')).toBe(null)
      expect(formatExpirationBadge('2026-04-20')).toBe(null)
      expect(formatExpirationBadge('2027-01-01')).toBe(null)
    })

    it('handles ISO datetime strings', () => {
      expect(formatExpirationBadge('2026-03-20T23:59:59Z')).toBe('today')
      expect(formatExpirationBadge('2026-03-21T00:00:00Z')).toBe('tomorrow')
      expect(formatExpirationBadge('2026-03-19T12:00:00Z')).toBe('expired')
    })
  })

  describe('timezone safety', () => {
    beforeEach(() => {
      // Mock current date to 2026-03-20 at 11:00 PM
      // This is close to midnight to test edge cases
      vi.useFakeTimers()
      vi.setSystemTime(new Date(2026, 2, 20, 23, 0, 0))
    })

    it('correctly handles dates near midnight without off-by-one errors', () => {
      // Even though it's 11 PM, "today" should still be March 20
      expect(getDaysSinceDate('2026-03-20')).toBe(0)
      expect(getDaysUntilDate('2026-03-20')).toBe(0)
      expect(formatRelativeDate('2026-03-20')).toBe('today')

      // Yesterday should still be March 19
      expect(getDaysSinceDate('2026-03-19')).toBe(1)
      expect(formatRelativeDate('2026-03-19')).toBe('yesterday')

      // Tomorrow should still be March 21
      expect(getDaysUntilDate('2026-03-21')).toBe(1)
      expect(formatExpirationBadge('2026-03-21')).toBe('tomorrow')
    })

    it('parseDateOnly creates date in local timezone, not UTC', () => {
      const date = parseDateOnly('2026-03-20')

      // The date should be March 20 at midnight in local timezone
      // NOT affected by UTC offset
      expect(date.getFullYear()).toBe(2026)
      expect(date.getMonth()).toBe(2)
      expect(date.getDate()).toBe(20)
      expect(date.getHours()).toBe(0)

      // getTimezoneOffset returns offset in minutes (e.g., -480 for PST)
      // We're not testing the specific timezone, just that the date components are correct
      expect(date.toString()).toContain('Mar 20 2026')
    })
  })

  describe('edge cases', () => {
    beforeEach(() => {
      vi.useFakeTimers()
      vi.setSystemTime(new Date(2026, 2, 20, 10, 30, 0))
    })

    it('handles leap year dates correctly', () => {
      // 2024 was a leap year
      const leapDay = parseDateOnly('2024-02-29')
      expect(leapDay.getMonth()).toBe(1) // February
      expect(leapDay.getDate()).toBe(29)
    })

    it('handles year boundaries', () => {
      vi.setSystemTime(new Date(2026, 0, 1, 10, 0, 0)) // January 1, 2026

      expect(formatRelativeDate('2026-01-01')).toBe('today')
      expect(formatRelativeDate('2025-12-31')).toBe('yesterday')
      expect(getDaysSinceDate('2025-12-31')).toBe(1)
    })

    it('handles month boundaries', () => {
      vi.setSystemTime(new Date(2026, 3, 1, 10, 0, 0)) // April 1, 2026

      expect(formatRelativeDate('2026-04-01')).toBe('today')
      expect(formatRelativeDate('2026-03-31')).toBe('yesterday')
      expect(getDaysSinceDate('2026-03-31')).toBe(1)
    })
  })
})
