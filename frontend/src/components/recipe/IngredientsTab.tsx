import type { RecipeIngredientResponse } from '../../api/types'

interface IngredientsTabProps {
  ingredients: RecipeIngredientResponse[]
  servingsMultiplier: number
}

/**
 * Formats a quantity for display, handling fractions and decimals appropriately
 * Uses tolerance-based matching to handle floating-point arithmetic edge cases
 * - Converts common fractions to readable format (0.25 -> 1/4, 0.33 -> 1/3, etc.)
 * - Matches fractional values within ±0.01 tolerance to account for floating-point errors
 * - Rounds to 2 decimal places for values that don't match common fractions
 */
function formatQuantity(quantity: number): string {
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
 * - Grouped presentation (can be enhanced with categories later)
 * - Quantities scaled by servingsMultiplier
 */
export default function IngredientsTab({ ingredients, servingsMultiplier }: IngredientsTabProps) {
  if (ingredients.length === 0) {
    return (
      <div className="text-center py-8 text-text-secondary">
        No ingredients listed for this recipe.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {ingredients.map((ingredient) => {
        const scaledQuantity = ingredient.quantity * servingsMultiplier
        const formattedQuantity = formatQuantity(scaledQuantity)

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
          </div>
        )
      })}
    </div>
  )
}
