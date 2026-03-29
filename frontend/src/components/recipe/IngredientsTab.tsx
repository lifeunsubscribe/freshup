import type { RecipeIngredientResponse, InventoryItemListResponse } from '../../api/types'
import type { PantryCheckResult } from '../../utils/pantryMatcher'
import PantryCheck from './PantryCheck'
import Pill from '../ui/Pill'
import {
  UNPARSEABLE_QUANTITY_SENTINEL,
  SENTINEL_TOLERANCE,
  isUnparseableQuantity,
} from '../../constants/recipe'

/**
 * Props for IngredientsTab component
 *
 * Performance optimization: Inventory data and stock status are passed from parent
 * component to avoid duplicate hook calls and calculations. Previously, both
 * RecipeDetail and IngredientsTab called useInventoryList() independently.
 */
interface IngredientsTabProps {
  ingredients: RecipeIngredientResponse[]
  servingsMultiplier: number
  /** Inventory items fetched by parent component */
  inventoryItems: InventoryItemListResponse[]
  /** Pre-calculated stock status from parent component */
  stockStatus: PantryCheckResult
  /** Error state from inventory API call */
  inventoryError: boolean
}

/**
 * Note: UNPARSEABLE_QUANTITY_SENTINEL, SENTINEL_TOLERANCE, and isUnparseableQuantity
 * are now imported from ../../constants/recipe.ts to maintain a single source of truth.
 */

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
 *
 * Performance: Receives inventory data and stock status as props from parent
 * to avoid duplicate API calls and calculations.
 */
export default function IngredientsTab({
  ingredients,
  servingsMultiplier,
  inventoryItems,
  stockStatus,
  inventoryError,
}: IngredientsTabProps) {

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
