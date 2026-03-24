import { Heart } from 'lucide-react'

interface ActionBarProps {
  isFavorited: boolean
  onFavoriteToggle: () => void
  onAddToMealPlan: () => void
  isLoading?: boolean
}

/**
 * ActionBar component for recipe detail actions
 *
 * Features:
 * - Fixed bottom bar (mobile-friendly)
 * - "Add to meal plan" primary button
 * - Favorite heart toggle (filled when favorited)
 * - Sticky positioning with shadow for visibility
 */
export default function ActionBar({
  isFavorited,
  onFavoriteToggle,
  onAddToMealPlan,
  isLoading = false,
}: ActionBarProps) {
  return (
    <div className="fixed bottom-0 left-0 right-0 bg-cream border-t border-warm-border shadow-lg z-10">
      <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
        {/* Add to meal plan button */}
        <button
          onClick={onAddToMealPlan}
          disabled={isLoading}
          className="flex-1 bg-olive text-cream font-medium py-3 px-4 rounded-button hover:bg-olive-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Add to meal plan
        </button>

        {/* Favorite toggle button */}
        <button
          onClick={onFavoriteToggle}
          disabled={isLoading}
          className="flex-shrink-0 p-3 rounded-button border-2 border-warm-border bg-cream hover:bg-cream-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label={isFavorited ? 'Remove from favorites' : 'Add to favorites'}
        >
          <Heart
            size={24}
            className={isFavorited ? 'fill-mocha stroke-mocha' : 'stroke-mocha'}
            strokeWidth={2}
          />
        </button>
      </div>
    </div>
  )
}
