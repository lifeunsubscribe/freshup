import type { RecipeIngredientResponse } from '../../api/types'

interface IngredientsTabProps {
  ingredients: RecipeIngredientResponse[]
  servingsMultiplier: number
}

/**
 * Formats a quantity for display, handling fractions and decimals appropriately
 * - Rounds to 2 decimal places for readability
 * - Converts common fractions to readable format (0.25 -> 1/4, 0.33 -> 1/3, etc.)
 */
function formatQuantity(quantity: number): string {
  // Handle whole numbers
  if (Number.isInteger(quantity)) {
    return quantity.toString()
  }

  // Common fractions for cooking
  const fractions: Record<string, string> = {
    '0.25': '1/4',
    '0.33': '1/3',
    '0.5': '1/2',
    '0.67': '2/3',
    '0.75': '3/4',
  }

  // For other decimals, check if the fractional part matches a common fraction
  const wholePart = Math.floor(quantity)
  const fractionalPart = quantity - wholePart

  // Convert fractional part to string with 2 decimals, then remove trailing zeros
  const fractionalStr = fractionalPart.toFixed(2).replace(/\.?0+$/, '')

  if (fractions[fractionalStr]) {
    return wholePart > 0 ? `${wholePart} ${fractions[fractionalStr]}` : fractions[fractionalStr]
  }

  // Round to 2 decimal places for readability
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
