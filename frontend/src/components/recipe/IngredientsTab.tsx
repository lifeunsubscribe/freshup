import type { RecipeIngredientResponse } from '../../api/types'

interface IngredientsTabProps {
  ingredients: RecipeIngredientResponse[]
  servingsMultiplier: number
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

        return (
          <div
            key={ingredient.id}
            className="flex items-start gap-3 py-3 border-b border-warm-border last:border-b-0"
          >
            <div className="flex-shrink-0 w-20 text-sm font-medium text-text-primary">
              {scaledQuantity} {ingredient.unit}
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
