/**
 * Recipe-related constants.
 *
 * This file serves as the single source of truth for recipe constants
 * in the frontend codebase. These values must be kept in sync with the
 * backend constants in src/services/import_service.py.
 */

/**
 * Sentinel value for unparseable ingredient quantities.
 *
 * This is a WORKAROUND for validation requiring quantity > 0 in RecipeIngredientCreate.
 * Unparseable ingredients (e.g., "salt to taste") have no meaningful numeric quantity,
 * but the schema validation forces us to use a non-zero value.
 *
 * IMPORTANT: This value must match UNPARSEABLE_QUANTITY_SENTINEL in the backend
 * (src/services/import_service.py). When changing this value, update both locations.
 *
 * Related: Issue #335 - Sentinel Value 0.001 Workaround
 * Parent PR: #333 - Import pipeline & deduplication
 *
 * @constant {number}
 */
export const UNPARSEABLE_QUANTITY_SENTINEL = 0.001

/**
 * Tolerance for detecting sentinel values after scaling.
 * Used to handle floating-point arithmetic imprecision when comparing scaled quantities.
 *
 * @constant {number}
 */
export const SENTINEL_TOLERANCE = 0.0001

/**
 * Check if a quantity represents an unparseable ingredient.
 * Handles scaled quantities by checking if they originated from the sentinel value.
 *
 * @param quantity - The quantity to check (may be scaled)
 * @param multiplier - The scaling multiplier applied to the original quantity (default: 1)
 * @returns true if the original (unscaled) quantity was the sentinel value
 *
 * @example
 * // Unscaled sentinel value
 * isUnparseableQuantity(0.001, 1) // => true
 *
 * // Scaled sentinel value
 * isUnparseableQuantity(0.002, 2) // => true (0.002 / 2 = 0.001)
 *
 * // Regular small quantity
 * isUnparseableQuantity(0.125, 1) // => false
 */
export function isUnparseableQuantity(quantity: number, multiplier: number = 1): boolean {
  // Guard against division by zero
  if (multiplier === 0) {
    return false
  }
  // Divide by multiplier to get the original quantity before scaling
  const originalQuantity = quantity / multiplier
  return Math.abs(originalQuantity - UNPARSEABLE_QUANTITY_SENTINEL) < SENTINEL_TOLERANCE
}
