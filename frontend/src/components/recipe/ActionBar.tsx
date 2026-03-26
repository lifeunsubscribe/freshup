import { Heart, ShoppingCart } from 'lucide-react'
import { useState, useRef } from 'react'
import { useCreateGroceryItem } from '../../api/hooks/useGrocery'
import type { IngredientStockStatus } from '../../utils/pantryMatcher'

interface ActionBarProps {
  isFavorited: boolean
  onFavoriteToggle: () => void
  onAddToMealPlan: () => void
  isLoading?: boolean
  missingIngredients?: IngredientStockStatus[]
}

/**
 * ActionBar component for recipe detail actions
 *
 * Features:
 * - Fixed bottom bar (mobile-friendly)
 * - "Add missing to list" button (pantry cross-reference)
 * - "Add to meal plan" button (Phase 2 feature)
 * - Favorite heart toggle (filled when favorited)
 * - Shows count of missing ingredients
 * - Disabled when all ingredients in stock
 * - Sticky positioning with shadow for visibility
 */
export default function ActionBar({
  isFavorited,
  onFavoriteToggle,
  onAddToMealPlan,
  isLoading = false,
  missingIngredients = [],
}: ActionBarProps) {
  const createGroceryItem = useCreateGroceryItem()
  const [isAddingToList, setIsAddingToList] = useState(false)
  const [addToListError, setAddToListError] = useState<string | null>(null)
  const [addToListSuccess, setAddToListSuccess] = useState(false)
  const errorTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const successTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  const missingCount = missingIngredients.length
  const allInStock = missingCount === 0

  const handleAddMissingToList = async () => {
    if (missingCount === 0 || addToListSuccess) return

    setIsAddingToList(true)
    setAddToListError(null)

    // Clear any existing error timeout
    if (errorTimeoutRef.current) {
      clearTimeout(errorTimeoutRef.current)
      errorTimeoutRef.current = null
    }

    try {
      // Add all missing ingredients to grocery list in parallel
      await Promise.all(
        missingIngredients.map(({ ingredient }) =>
          createGroceryItem.mutateAsync({
            item_name: ingredient.ingredient_name,
            quantity: ingredient.quantity,
            unit: ingredient.unit,
            source: 'recipe',
          })
        )
      )

      // Show success feedback
      setAddToListSuccess(true)
      successTimeoutRef.current = setTimeout(() => {
        setAddToListSuccess(false)
        successTimeoutRef.current = null
      }, 3000)
    } catch (error) {
      console.error('Failed to add ingredients to grocery list:', error)
      setAddToListError('Failed to add ingredients. Please try again.')
      errorTimeoutRef.current = setTimeout(() => {
        setAddToListError(null)
        errorTimeoutRef.current = null
      }, 5000)
    } finally {
      setIsAddingToList(false)
    }
  }

  return (
    <>
      {addToListError && (
        <div className="fixed bottom-20 left-4 right-4 bg-red-50 border border-red-200 rounded-lg p-3 shadow-lg z-40">
          <p className="text-sm text-red-800">{addToListError}</p>
        </div>
      )}
      {addToListSuccess && (
        <div className="fixed bottom-20 left-4 right-4 bg-green-50 border border-green-200 rounded-lg p-3 shadow-lg z-40">
          <p className="text-sm text-green-800">Ingredients added to grocery list!</p>
        </div>
      )}
      <div className="fixed bottom-0 left-0 right-0 bg-cream border-t border-warm-border shadow-lg z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
          {/* Add missing to list button (pantry cross-reference) */}
          <button
            onClick={handleAddMissingToList}
            disabled={isLoading || isAddingToList || allInStock || addToListSuccess}
            className="flex-1 bg-olive text-cream font-medium py-3 px-4 rounded-button hover:bg-olive-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            title={allInStock ? 'All ingredients are in stock' : addToListSuccess ? 'Ingredients added to list' : `Add ${missingCount} missing ingredient${missingCount === 1 ? '' : 's'} to grocery list`}
          >
            <ShoppingCart size={18} />
            <span>
              {allInStock
                ? 'All ingredients in stock'
                : `Add ${missingCount} missing to list`}
            </span>
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
    </>
  )
}
