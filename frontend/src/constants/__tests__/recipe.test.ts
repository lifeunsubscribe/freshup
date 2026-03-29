import { describe, it, expect } from 'vitest'
import {
  UNPARSEABLE_QUANTITY_SENTINEL,
  SENTINEL_TOLERANCE,
  isUnparseableQuantity,
} from '../recipe'

describe('recipe constants', () => {
  describe('UNPARSEABLE_QUANTITY_SENTINEL', () => {
    it('should have the expected value', () => {
      expect(UNPARSEABLE_QUANTITY_SENTINEL).toBe(0.001)
    })
  })

  describe('SENTINEL_TOLERANCE', () => {
    it('should have the expected value', () => {
      expect(SENTINEL_TOLERANCE).toBe(0.0001)
    })
  })

  describe('isUnparseableQuantity', () => {
    it('detects exact sentinel value', () => {
      expect(isUnparseableQuantity(0.001, 1)).toBe(true)
    })

    it('detects scaled sentinel value', () => {
      expect(isUnparseableQuantity(0.002, 2)).toBe(true)
      expect(isUnparseableQuantity(0.003, 3)).toBe(true)
      expect(isUnparseableQuantity(0.0005, 0.5)).toBe(true)
    })

    it('detects sentinel value within tolerance', () => {
      expect(isUnparseableQuantity(0.00105, 1)).toBe(true)
      expect(isUnparseableQuantity(0.00095, 1)).toBe(true)
    })

    it('rejects non-sentinel values', () => {
      expect(isUnparseableQuantity(0.125, 1)).toBe(false)
      expect(isUnparseableQuantity(1.0, 1)).toBe(false)
      expect(isUnparseableQuantity(0.5, 1)).toBe(false)
    })

    it('handles multiplier = 0 without division by zero', () => {
      expect(isUnparseableQuantity(0.001, 0)).toBe(false)
      expect(isUnparseableQuantity(1.0, 0)).toBe(false)
    })

    it('uses default multiplier of 1 when not provided', () => {
      expect(isUnparseableQuantity(0.001)).toBe(true)
      expect(isUnparseableQuantity(0.125)).toBe(false)
    })

    it('correctly identifies sentinel value after complex scaling', () => {
      // Simulate recipe scaled up then checked
      const originalQuantity = 0.001
      const scaledQuantity = originalQuantity * 2.5
      expect(isUnparseableQuantity(scaledQuantity, 2.5)).toBe(true)
    })

    it('distinguishes sentinel from similar small values', () => {
      // 0.001 is sentinel
      expect(isUnparseableQuantity(0.001, 1)).toBe(true)

      // 0.002 is NOT sentinel (unless scaled by 2)
      expect(isUnparseableQuantity(0.002, 1)).toBe(false)

      // 0.0009 is close but outside tolerance
      expect(isUnparseableQuantity(0.0009, 1)).toBe(false)

      // 0.125 (1/8 tsp) is definitely not sentinel
      expect(isUnparseableQuantity(0.125, 1)).toBe(false)
    })
  })

  describe('value synchronization with backend', () => {
    it('documents the need to keep values in sync', () => {
      // This is a documentation test to remind developers that these values
      // must match the backend constants in src/services/import_service.py
      //
      // UNPARSEABLE_QUANTITY_SENTINEL must match backend Python constant
      // SENTINEL_TOLERANCE must match backend tolerance in is_unparseable_quantity
      //
      // If tests fail after changing these values, ensure backend is also updated.
      expect(UNPARSEABLE_QUANTITY_SENTINEL).toBe(0.001)
      expect(SENTINEL_TOLERANCE).toBe(0.0001)
    })
  })
})
