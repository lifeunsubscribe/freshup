import { describe, it, expect } from 'vitest'
import {
  SOURCE_TYPE_OPTIONS,
  TAG_OPTIONS,
  getSourceTypeLabel,
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
