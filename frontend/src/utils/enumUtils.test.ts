import { describe, it, expect } from 'vitest'
import { getEnumValues, formatEnumLabel, getEnumOptions } from './enumUtils'
import { Category, StorageLocation } from '../api/types'

describe('enumUtils', () => {
  describe('getEnumValues', () => {
    it('should extract all values from an enum', () => {
      enum TestEnum {
        FIRST = 'first',
        SECOND = 'second',
        THIRD = 'third',
      }

      const values = getEnumValues(TestEnum)

      expect(values).toEqual(['first', 'second', 'third'])
      expect(values).toHaveLength(3)
    })

    it('should work with Category enum', () => {
      const values = getEnumValues(Category)

      expect(values).toContain(Category.PRODUCE)
      expect(values).toContain(Category.DAIRY)
      expect(values).toContain(Category.PROTEIN)
      expect(values).toContain(Category.GRAINS)
      expect(values).toContain(Category.CONDIMENTS)
      expect(values).toContain(Category.SNACKS)
      expect(values).toContain(Category.BEVERAGES)
      expect(values).toContain(Category.FROZEN)
      expect(values).toContain(Category.CANNED)
      expect(values).toContain(Category.BAKING)
      expect(values).toContain(Category.SPICES)
      expect(values).toContain(Category.OTHER)
      expect(values).toHaveLength(12)
    })

    it('should work with StorageLocation enum', () => {
      const values = getEnumValues(StorageLocation)

      expect(values).toContain(StorageLocation.PANTRY)
      expect(values).toContain(StorageLocation.FRIDGE)
      expect(values).toContain(StorageLocation.FREEZER)
      expect(values).toContain(StorageLocation.COUNTER)
      expect(values).toHaveLength(4)
    })
  })

  describe('formatEnumLabel', () => {
    it('should format UPPER_CASE to Title Case', () => {
      expect(formatEnumLabel('GLUTEN_FREE')).toBe('Gluten Free')
      expect(formatEnumLabel('STORAGE_LOCATION')).toBe('Storage Location')
      expect(formatEnumLabel('DAIRY_FREE')).toBe('Dairy Free')
    })

    it('should format single words', () => {
      expect(formatEnumLabel('PRODUCE')).toBe('Produce')
      expect(formatEnumLabel('DAIRY')).toBe('Dairy')
      expect(formatEnumLabel('PROTEIN')).toBe('Protein')
    })

    it('should format lowercase words', () => {
      expect(formatEnumLabel('produce')).toBe('Produce')
      expect(formatEnumLabel('dairy')).toBe('Dairy')
    })

    it('should handle snake_case', () => {
      expect(formatEnumLabel('gluten_free')).toBe('Gluten Free')
      expect(formatEnumLabel('storage_location')).toBe('Storage Location')
    })

    it('should format actual Category enum keys', () => {
      expect(formatEnumLabel('PRODUCE')).toBe('Produce')
      expect(formatEnumLabel('DAIRY')).toBe('Dairy')
      expect(formatEnumLabel('PROTEIN')).toBe('Protein')
      expect(formatEnumLabel('GRAINS')).toBe('Grains')
      expect(formatEnumLabel('CONDIMENTS')).toBe('Condiments')
      expect(formatEnumLabel('SNACKS')).toBe('Snacks')
      expect(formatEnumLabel('BEVERAGES')).toBe('Beverages')
      expect(formatEnumLabel('FROZEN')).toBe('Frozen')
      expect(formatEnumLabel('CANNED')).toBe('Canned')
      expect(formatEnumLabel('BAKING')).toBe('Baking')
      expect(formatEnumLabel('SPICES')).toBe('Spices')
      expect(formatEnumLabel('OTHER')).toBe('Other')
    })

    it('should format actual StorageLocation enum keys', () => {
      expect(formatEnumLabel('PANTRY')).toBe('Pantry')
      expect(formatEnumLabel('FRIDGE')).toBe('Fridge')
      expect(formatEnumLabel('FREEZER')).toBe('Freezer')
      expect(formatEnumLabel('COUNTER')).toBe('Counter')
    })
  })

  describe('getEnumOptions', () => {
    it('should return array of value/label objects', () => {
      enum TestEnum {
        FIRST_OPTION = 'first',
        SECOND_OPTION = 'second',
      }

      const options = getEnumOptions(TestEnum)

      expect(options).toEqual([
        { value: 'first', label: 'First Option' },
        { value: 'second', label: 'Second Option' },
      ])
    })

    it('should work with Category enum', () => {
      const options = getEnumOptions(Category)

      expect(options).toHaveLength(12)
      expect(options).toContainEqual({ value: 'produce', label: 'Produce' })
      expect(options).toContainEqual({ value: 'dairy', label: 'Dairy' })
      expect(options).toContainEqual({ value: 'protein', label: 'Protein' })
      expect(options).toContainEqual({ value: 'grains', label: 'Grains' })
      expect(options).toContainEqual({ value: 'condiments', label: 'Condiments' })
      expect(options).toContainEqual({ value: 'snacks', label: 'Snacks' })
      expect(options).toContainEqual({ value: 'beverages', label: 'Beverages' })
      expect(options).toContainEqual({ value: 'frozen', label: 'Frozen' })
      expect(options).toContainEqual({ value: 'canned', label: 'Canned' })
      expect(options).toContainEqual({ value: 'baking', label: 'Baking' })
      expect(options).toContainEqual({ value: 'spices', label: 'Spices' })
      expect(options).toContainEqual({ value: 'other', label: 'Other' })
    })

    it('should work with StorageLocation enum', () => {
      const options = getEnumOptions(StorageLocation)

      expect(options).toHaveLength(4)
      expect(options).toContainEqual({ value: 'pantry', label: 'Pantry' })
      expect(options).toContainEqual({ value: 'fridge', label: 'Fridge' })
      expect(options).toContainEqual({ value: 'freezer', label: 'Freezer' })
      expect(options).toContainEqual({ value: 'counter', label: 'Counter' })
    })

    it('should preserve enum value types', () => {
      const options = getEnumOptions(Category)
      const firstOption = options[0]

      // Value should be the actual enum value
      expect(typeof firstOption.value).toBe('string')
      expect(Object.values(Category)).toContain(firstOption.value)
    })
  })
})
