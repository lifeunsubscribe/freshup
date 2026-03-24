import { describe, it, expect } from 'vitest'
import {
  SOURCE_TYPE_OPTIONS,
  COOK_TIME_OPTIONS,
  TAG_OPTIONS,
  getSourceTypeLabel,
  getCookTimeLabel,
  getTagLabel,
} from './recipeFilters'

describe('recipeFilters', () => {
  describe('SOURCE_TYPE_OPTIONS', () => {
    it('contains expected source type options', () => {
      expect(SOURCE_TYPE_OPTIONS).toHaveLength(3)
      expect(SOURCE_TYPE_OPTIONS).toEqual([
        { value: 'manual', label: 'My recipes' },
        { value: 'hellofresh_card', label: 'HelloFresh' },
        { value: 'ad_hoc', label: 'Ad-hoc' },
      ])
    })
  })

  describe('COOK_TIME_OPTIONS', () => {
    it('contains expected cook time options', () => {
      expect(COOK_TIME_OPTIONS).toHaveLength(4)
      expect(COOK_TIME_OPTIONS).toEqual([
        { value: 15, label: '15 min or less' },
        { value: 30, label: '30 min or less' },
        { value: 45, label: '45 min or less' },
        { value: 60, label: '1 hour or less' },
      ])
    })
  })

  describe('TAG_OPTIONS', () => {
    it('contains expected tag options', () => {
      expect(TAG_OPTIONS).toHaveLength(9)
      expect(TAG_OPTIONS).toEqual([
        { value: 'italian', label: 'Italian' },
        { value: 'mexican', label: 'Mexican' },
        { value: 'asian', label: 'Asian' },
        { value: 'american', label: 'American' },
        { value: 'mediterranean', label: 'Mediterranean' },
        { value: 'indian', label: 'Indian' },
        { value: 'thai', label: 'Thai' },
        { value: 'vegan', label: 'Vegan' },
        { value: 'vegetarian', label: 'Vegetarian' },
      ])
    })
  })

  describe('getSourceTypeLabel', () => {
    it('returns correct label for known source types', () => {
      expect(getSourceTypeLabel('manual')).toBe('My recipes')
      expect(getSourceTypeLabel('hellofresh_card')).toBe('HelloFresh')
      expect(getSourceTypeLabel('ad_hoc')).toBe('Ad-hoc')
    })

    it('returns the input value as fallback for unknown source types', () => {
      expect(getSourceTypeLabel('unknown')).toBe('unknown')
      expect(getSourceTypeLabel('custom_source')).toBe('custom_source')
      expect(getSourceTypeLabel('imported')).toBe('imported')
    })

    it('handles empty string', () => {
      expect(getSourceTypeLabel('')).toBe('')
    })

    it('is case-sensitive', () => {
      expect(getSourceTypeLabel('Manual')).toBe('Manual')
      expect(getSourceTypeLabel('MANUAL')).toBe('MANUAL')
    })
  })

  describe('getCookTimeLabel', () => {
    describe('with numeric input', () => {
      it('returns correct label for known cook times', () => {
        expect(getCookTimeLabel(15)).toBe('15 min or less')
        expect(getCookTimeLabel(30)).toBe('30 min or less')
        expect(getCookTimeLabel(45)).toBe('45 min or less')
        expect(getCookTimeLabel(60)).toBe('1 hour or less')
      })

      it('returns fallback format for unknown cook times', () => {
        expect(getCookTimeLabel(10)).toBe('10 min')
        expect(getCookTimeLabel(20)).toBe('20 min')
        expect(getCookTimeLabel(90)).toBe('90 min')
        expect(getCookTimeLabel(120)).toBe('120 min')
      })

      it('handles zero', () => {
        expect(getCookTimeLabel(0)).toBe('0 min')
      })

      it('handles negative numbers', () => {
        expect(getCookTimeLabel(-5)).toBe('-5 min')
      })
    })

    describe('with string input', () => {
      it('converts string to number and returns correct label for known cook times', () => {
        expect(getCookTimeLabel('15')).toBe('15 min or less')
        expect(getCookTimeLabel('30')).toBe('30 min or less')
        expect(getCookTimeLabel('45')).toBe('45 min or less')
        expect(getCookTimeLabel('60')).toBe('1 hour or less')
      })

      it('converts string to number and returns fallback for unknown cook times', () => {
        expect(getCookTimeLabel('10')).toBe('10 min')
        expect(getCookTimeLabel('90')).toBe('90 min')
      })

      it('handles string zero', () => {
        expect(getCookTimeLabel('0')).toBe('0 min')
      })

      it('handles invalid numeric strings gracefully', () => {
        expect(getCookTimeLabel('invalid')).toBe('invalid')
        expect(getCookTimeLabel('abc')).toBe('abc')
      })

      it('handles empty string', () => {
        expect(getCookTimeLabel('')).toBe('0 min')
      })

      it('handles decimal strings', () => {
        expect(getCookTimeLabel('15.5')).toBe('15.5 min')
        expect(getCookTimeLabel('30.7')).toBe('30.7 min')
      })
    })

    describe('type coercion edge cases', () => {
      it('handles whitespace in strings', () => {
        expect(getCookTimeLabel(' 15 ')).toBe('15 min or less')
        expect(getCookTimeLabel('  30  ')).toBe('30 min or less')
      })

      it('handles scientific notation strings', () => {
        expect(getCookTimeLabel('1e2')).toBe('100 min')
      })

      it('handles Infinity', () => {
        expect(getCookTimeLabel(Infinity)).toBe('Infinity')
        expect(getCookTimeLabel(-Infinity)).toBe('-Infinity')
      })
    })
  })

  describe('getTagLabel', () => {
    it('returns correct label for known tags', () => {
      expect(getTagLabel('italian')).toBe('Italian')
      expect(getTagLabel('mexican')).toBe('Mexican')
      expect(getTagLabel('asian')).toBe('Asian')
      expect(getTagLabel('american')).toBe('American')
      expect(getTagLabel('mediterranean')).toBe('Mediterranean')
      expect(getTagLabel('indian')).toBe('Indian')
      expect(getTagLabel('thai')).toBe('Thai')
      expect(getTagLabel('vegan')).toBe('Vegan')
      expect(getTagLabel('vegetarian')).toBe('Vegetarian')
    })

    it('returns the input value as fallback for unknown tags', () => {
      expect(getTagLabel('french')).toBe('french')
      expect(getTagLabel('chinese')).toBe('chinese')
      expect(getTagLabel('custom-tag')).toBe('custom-tag')
    })

    it('handles empty string', () => {
      expect(getTagLabel('')).toBe('')
    })

    it('is case-sensitive', () => {
      expect(getTagLabel('Italian')).toBe('Italian')
      expect(getTagLabel('VEGAN')).toBe('VEGAN')
    })

    it('preserves capitalization of unknown tags', () => {
      expect(getTagLabel('French Cuisine')).toBe('French Cuisine')
      expect(getTagLabel('Gluten-Free')).toBe('Gluten-Free')
    })
  })
})
