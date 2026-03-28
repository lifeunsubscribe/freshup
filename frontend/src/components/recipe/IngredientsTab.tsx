import type { RecipeIngredientResponse } from '../../api/types'
import { useInventoryList } from '../../api/hooks/useInventory'
import { checkIngredientAvailability } from '../../utils/pantryMatcher'
import PantryCheck from './PantryCheck'
import Pill from '../ui/Pill'

interface IngredientsTabProps {
  ingredients: RecipeIngredientResponse[]
  servingsMultiplier: number
}

/**
 * Sentinel value for unparseable ingredient quantities.
 * This matches the backend constant UNPARSEABLE_QUANTITY_SENTINEL in import_service.py.
 *
 * This is a WORKAROUND for validation requiring quantity > 0 in RecipeIngredientCreate.
 * Unparseable ingredients (e.g., "salt to taste") have no meaningful numeric quantity.
 *
 * Related: Issue #335 - Sentinel Value 0.001 Workaround
 */
const UNPARSEABLE_QUANTITY_SENTINEL = 0.001

/**
 * Tolerance for detecting sentinel values after scaling.
 * Used to handle floating-point arithmetic imprecision when comparing scaled quantities.
 */
const SENTINEL_TOLERANCE = 0.0001

/**
 * Check if a quantity represents an unparseable ingredient.
 * Handles scaled quantities by checking if they originated from the sentinel value.
 *
 * @param quantity - The quantity to check (may be scaled)
 * @param multiplier - The scaling multiplier applied to the original quantity
 * @returns true if the original (unscaled) quantity was the sentinel value
 */
function isUnparseableQuantity(quantity: number, multiplier: number = 1): boolean {
  // Guard against division by zero
  if (multiplier === 0) {
    return false
  }
  // Divide by multiplier to get the original quantity before scaling
  const originalQuantity = quantity / multiplier
  return Math.abs(originalQuantity - UNPARSEABLE_QUANTITY_SENTINEL) < SENTINEL_TOLERANCE
}

/**
 * Formats a quantity for display, handling fractions and decimals appropriately
 * Uses tolerance-based matching to handle floating-point arithmetic edge cases
 * - Returns empty string for unparseable quantities (sentinel value)
 * - Converts common fractions to readable format (0.25 -> 1/4, 0.33 -> 1/3, etc.)
 * - Matches fractional values within ±0.01 tolerance to account for floating-point errors
 * - Rounds to 2 decimal places for values that don't match common fractions
 *
 * @param quantity - The quantity to format (may be scaled)
 * @param multiplier - The scaling multiplier applied to the original quantity
 */
function formatQuantity(quantity: number, multiplier: number = 1): string {
  // Handle sentinel value for unparseable ingredients
  if (isUnparseableQuantity(quantity, multiplier)) {
    return ''
  }
  // Handle whole numbers (with small tolerance for floating-point errors)
  // Use stricter tolerance (0.001) for whole numbers to avoid matching values like 1.008
  if (Math.abs(quantity - Math.round(quantity)) < 0.001) {
    return Math.round(quantity).toString()
  }

  // Common fractions for cooking with their decimal equivalents
  // Ordered by precision to match the most accurate fraction first
  const fractions = [
    { decimal: 1 / 3, display: '1/3' },
    { decimal: 2 / 3, display: '2/3' },
    { decimal: 1 / 4, display: '1/4' },
    { decimal: 3 / 4, display: '3/4' },
    { decimal: 1 / 2, display: '1/2' },
    { decimal: 1 / 8, display: '1/8' },
    { decimal: 3 / 8, display: '3/8' },
    { decimal: 5 / 8, display: '5/8' },
    { decimal: 7 / 8, display: '7/8' },
  ]

  // Tolerance for matching fractions (accounts for floating-point arithmetic)
  const TOLERANCE = 0.01

  // Extract whole and fractional parts
  const wholePart = Math.floor(quantity)
  const fractionalPart = quantity - wholePart

  // Try to match the fractional part to a common fraction
  for (const fraction of fractions) {
    if (Math.abs(fractionalPart - fraction.decimal) < TOLERANCE) {
      return wholePart > 0 ? `${wholePart} ${fraction.display}` : fraction.display
    }
  }

  // If no fraction matches, round to 2 decimal places for readability
  return quantity.toFixed(2)
}

/**
 * IngredientsTab component displays all recipe ingredients
 *
 * Features:
 * - Lists all ingredients with scaled quantities
 * - Shows quantity, unit, and ingredient name
 * - Pantry cross-reference: "In stock" badges for available ingredients
 * - PantryCheck summary card at bottom
 * - Quantities scaled by servingsMultiplier
 */
export default function IngredientsTab({ ingredients, servingsMultiplier }: IngredientsTabProps) {
  // Fetch pantry inventory for cross-reference
  const { data: inventoryItems = [], isError: inventoryError } = useInventoryList({})

  // Check ingredient availability against pantry
  const stockStatus = checkIngredientAvailability(ingredients, inventoryItems)

  if (ingredients.length === 0) {
    return (
      <div className="text-center py-8 text-text-secondary">
        No ingredients listed for this recipe.
      </div>
    )
  }

  // Create a map for quick lookup of stock status
  const stockStatusMap = new Map<string, boolean>()
  stockStatus.inStock.forEach((item) => {
    stockStatusMap.set(item.ingredient.id, true)
  })

  return (
    <div className="space-y-3">
      {inventoryError && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 mb-3">
          <p className="text-sm text-yellow-800">
            Unable to load pantry inventory. Stock status may not be accurate.
          </p>
        </div>
      )}
      {ingredients.map((ingredient) => {
        const scaledQuantity = ingredient.quantity * servingsMultiplier
        const formattedQuantity = formatQuantity(scaledQuantity, servingsMultiplier)
        const isInStock = stockStatusMap.has(ingredient.id)

        return (
          <div
            key={ingredient.id}
            className="flex items-start gap-3 py-3 border-b border-warm-border last:border-b-0"
          >
            <div className="flex-shrink-0 w-20 text-sm font-medium text-text-primary">
              {formattedQuantity} {ingredient.unit}
            </div>
            <div className="flex-1 text-sm text-text-primary">
              {ingredient.ingredient_name}
            </div>
            {isInStock && (
              <div className="flex-shrink-0">
                <Pill variant="success">
                  <span className="text-xs">In stock</span>
                </Pill>
              </div>
            )}
          </div>
        )
      })}

      {/* PantryCheck summary card */}
      <PantryCheck stockStatus={stockStatus} />
    </div>
  )
}
