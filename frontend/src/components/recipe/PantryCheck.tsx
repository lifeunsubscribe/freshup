import type { PantryCheckResult } from '../../utils/pantryMatcher'

interface PantryCheckProps {
  stockStatus: PantryCheckResult
}

/**
 * PantryCheck component displays pantry cross-reference summary
 *
 * Features:
 * - Shows "X of Y ingredients in stock"
 * - Lists in-stock ingredient names (passive voice per design system)
 * - Shows count of missing ingredients
 * - Olive/cream color scheme
 * - Positioned at bottom of IngredientsTab
 *
 * Design System: Section 7.3 - Pantry Cross-Reference
 */
export default function PantryCheck({ stockStatus }: PantryCheckProps) {
  const { inStock, outOfStock, totalCount, inStockCount } = stockStatus

  // Don't show if no ingredients
  if (totalCount === 0) {
    return null
  }

  const missingCount = outOfStock.length

  // Format in-stock ingredient names for display
  const inStockNames = inStock.map((item) => item.ingredient.ingredient_name)

  return (
    <div className="mt-6 p-4 bg-ingredient-pill-bg rounded-lg border border-warm-border">
      {/* Summary heading */}
      <div className="text-sm font-medium text-text-primary mb-2">
        {inStockCount} of {totalCount} {totalCount === 1 ? 'ingredient' : 'ingredients'} in stock
      </div>

      {/* In-stock ingredients list (passive voice) */}
      {inStockNames.length > 0 && (
        <p className="text-sm text-text-secondary mb-1">
          {inStockNames.join(', ')}{' '}
          {inStockNames.length === 1 ? 'is' : 'are'} in stock.
        </p>
      )}

      {/* Missing ingredients count */}
      {missingCount > 0 && (
        <p className="text-sm text-text-secondary">
          {missingCount} {missingCount === 1 ? 'ingredient' : 'ingredients'} needed from the store.
        </p>
      )}

      {/* All ingredients in stock message */}
      {missingCount === 0 && inStockCount > 0 && (
        <p className="text-sm text-olive font-medium">
          All ingredients are in stock!
        </p>
      )}
    </div>
  )
}
