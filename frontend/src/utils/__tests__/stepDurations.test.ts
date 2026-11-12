import { describe, it, expect } from 'vitest'
import { durationsInStep, formatStartLabel } from '../stepDurations'

describe('durationsInStep', () => {
  describe('ranges', () => {
    it('returns the upper bound for "N-M minutes"', () => {
      expect(durationsInStep('roast for 20-25 minutes')).toEqual([25])
    })

    it('handles em-dash range "N–M minutes"', () => {
      expect(durationsInStep('cook for 10–15 minutes')).toEqual([15])
    })

    it('does not double-count the upper bound when range text is present', () => {
      // 25 should appear only once
      expect(durationsInStep('roast for 20-25 minutes')).toHaveLength(1)
    })
  })

  describe('hours', () => {
    it('converts integer hours to minutes', () => {
      expect(durationsInStep('simmer for 2 hours')).toEqual([120])
    })

    it('converts "1 hour" to 60', () => {
      expect(durationsInStep('bake for 1 hour')).toEqual([60])
    })

    it('converts "hrs" abbreviation', () => {
      expect(durationsInStep('cook for 3 hrs')).toEqual([180])
    })

    it('converts "h" abbreviation', () => {
      expect(durationsInStep('rest for 2 h')).toEqual([120])
    })

    it('converts decimal hours: "1.5 hours" → 90', () => {
      expect(durationsInStep('simmer for 1.5 hours')).toEqual([90])
    })

    it('converts unicode fraction: "1½ hours" → 90', () => {
      expect(durationsInStep('simmer 1½ hours')).toEqual([90])
    })

    it('converts "1,5 hours" (comma decimal) → 90', () => {
      expect(durationsInStep('cook 1,5 hours')).toEqual([90])
    })
  })

  describe('minutes', () => {
    it('returns N for "N minutes"', () => {
      expect(durationsInStep('cook for 15 minutes')).toEqual([15])
    })

    it('returns N for "N min"', () => {
      expect(durationsInStep('simmer for 30 min')).toEqual([30])
    })

    it('handles "minute" (singular)', () => {
      expect(durationsInStep('cook for 1 minute')).toEqual([1])
    })
  })

  describe('seconds', () => {
    it('rounds up any N seconds to 1 minute', () => {
      expect(durationsInStep('blend for 30 seconds')).toEqual([1])
    })

    it('handles "secs" abbreviation', () => {
      expect(durationsInStep('stir for 10 secs')).toEqual([1])
    })
  })

  describe('ignored patterns', () => {
    it('returns [] for "a minute or two" (no leading number)', () => {
      expect(durationsInStep('a minute or two')).toEqual([])
    })

    it('returns [] for plain "minutes" with no number', () => {
      expect(durationsInStep('cook until tender, about minutes depending on size')).toEqual([])
    })

    it('returns [] for a step with no time reference', () => {
      expect(durationsInStep('Chop the onions and set aside')).toEqual([])
    })
  })

  describe('multiple durations', () => {
    it('returns multiple distinct durations sorted ascending', () => {
      expect(durationsInStep('cook for 10 minutes then simmer for 20 minutes')).toEqual([10, 20])
    })

    it('deduplicates equal durations', () => {
      expect(durationsInStep('cook 15 minutes; rest 15 minutes')).toEqual([15])
    })
  })

  describe('case insensitivity', () => {
    it('matches "MINUTES" in upper case', () => {
      expect(durationsInStep('Cook for 5 MINUTES')).toEqual([5])
    })

    it('matches "Hours" with mixed case', () => {
      expect(durationsInStep('Bake for 2 Hours')).toEqual([120])
    })
  })
})

describe('formatStartLabel', () => {
  it('formats sub-hour durations as "Start N min"', () => {
    expect(formatStartLabel(15)).toBe('Start 15 min')
    expect(formatStartLabel(1)).toBe('Start 1 min')
    expect(formatStartLabel(59)).toBe('Start 59 min')
  })

  it('formats exact hours as "Start N hr"', () => {
    expect(formatStartLabel(60)).toBe('Start 1 hr')
    expect(formatStartLabel(120)).toBe('Start 2 hr')
  })

  it('formats hours+minutes as "Start N hr M min"', () => {
    expect(formatStartLabel(90)).toBe('Start 1 hr 30 min')
    expect(formatStartLabel(75)).toBe('Start 1 hr 15 min')
  })
})
