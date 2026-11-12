import type { PantryCheckResult } from '../../utils/pantryMatcher'

interface PantryCheckProps {
  stockStatus: PantryCheckResult
  onReview: () => void
  inventoryError?: boolean
}

export default function PantryCheck({ stockStatus, onReview, inventoryError }: PantryCheckProps) {
  const { totalCount, inStockCount } = stockStatus

  if (totalCount === 0) {
    return null
  }

  if (inventoryError) {
    return (
      <div className="mt-6 p-4 bg-ingredient-pill-bg rounded-lg border border-warm-border">
        <p className="text-sm text-text-secondary">Pantry unavailable right now.</p>
      </div>
    )
  }

  return (
    <button
      onClick={onReview}
      className="mt-6 w-full p-4 bg-ingredient-pill-bg rounded-lg border border-warm-border text-left hover:bg-cream-dark transition-colors"
    >
      <p className="text-sm font-medium text-text-primary">
        {inStockCount} of {totalCount} in the pantry.
      </p>
      <p className="text-sm text-text-secondary">Tap to review before adding.</p>
    </button>
  )
}
