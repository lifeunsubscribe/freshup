import { Heart, ShoppingCart } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { useCreateGroceryItem, useGroceryList } from '../../api/hooks/useGrocery'
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
  const { data: existingGroceryItems = [], refetch: refetchGroceryList } = useGroceryList({ purchased: false })
  const [isAddingToList, setIsAddingToList] = useState(false)
  const [addToListError, setAddToListError] = useState<string | null>(null)
  const [addToListSuccess, setAddToListSuccess] = useState(false)
  const errorTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const successTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const addedItemsRef = useRef<Set<string>>(new Set())

  // Cleanup timeouts on component unmount
  useEffect(() => {
    return () => {
      if (errorTimeoutRef.current) {
        clearTimeout(errorTimeoutRef.current)
      }
      if (successTimeoutRef.current) {
        clearTimeout(successTimeoutRef.current)
      }
    }
  }, [])

  // Sync addedItemsRef with the current grocery list
  // Remove items from the ref that are no longer in the grocery list
  // This prevents the race condition where removed items cannot be re-added
  useEffect(() => {
    const currentItemNames = new Set(
      existingGroceryItems.map(item => item.item_name.toLowerCase())
    )

    // Remove items from addedItemsRef that are no longer in the grocery list
    addedItemsRef.current.forEach(itemName => {
      if (!currentItemNames.has(itemName)) {
        addedItemsRef.current.delete(itemName)
      }
    })
  }, [existingGroceryItems])

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
      // Refetch grocery list to ensure we have the latest data before checking for duplicates
      const { data: latestGroceryItems } = await refetchGroceryList()
      const currentGroceryItems = latestGroceryItems || existingGroceryItems

      // Filter out ingredients already in the grocery list (case-insensitive match by name)
      // Also filter out items that were added in this session (to prevent duplicates from rapid clicks)
      const existingItemNames = new Set(
        currentGroceryItems.map(item => item.item_name.toLowerCase())
      )

      const ingredientsToAdd = missingIngredients.filter(
        ({ ingredient }) => {
          const itemNameLower = ingredient.ingredient_name.toLowerCase()
          return !existingItemNames.has(itemNameLower) && !addedItemsRef.current.has(itemNameLower)
        }
      )

      // If all ingredients are already in the list, show success message
      if (ingredientsToAdd.length === 0) {
        setAddToListSuccess(true)
        successTimeoutRef.current = setTimeout(() => {
          setAddToListSuccess(false)
          successTimeoutRef.current = null
        }, 3000)
        setIsAddingToList(false)
        return
      }

      // Add only new ingredients to grocery list in parallel
      const results = await Promise.allSettled(
        ingredientsToAdd.map(({ ingredient }) =>
          createGroceryItem.mutateAsync({
            item_name: ingredient.ingredient_name,
            quantity: ingredient.quantity,
            unit: ingredient.unit,
            source: 'recipe',
          })
        )
      )

      // Count successes and failures
      const successCount = results.filter(r => r.status === 'fulfilled').length
      const failureCount = results.filter(r => r.status === 'rejected').length
      const skippedCount = missingIngredients.length - ingredientsToAdd.length

      // Track successfully added items to prevent duplicates from rapid clicks
      if (successCount > 0) {
        results.forEach((result, index) => {
          if (result.status === 'fulfilled') {
            const itemNameLower = ingredientsToAdd[index].ingredient.ingredient_name.toLowerCase()
            addedItemsRef.current.add(itemNameLower)
          }
        })
      }

      if (failureCount === 0) {
        // All new ingredients added successfully
        setAddToListSuccess(true)
        successTimeoutRef.current = setTimeout(() => {
          setAddToListSuccess(false)
          successTimeoutRef.current = null
        }, 3000)
      } else if (successCount > 0) {
        // Partial success
        console.error('Some ingredients failed to add:', results.filter(r => r.status === 'rejected'))
        const totalToAdd = ingredientsToAdd.length
        setAddToListError(`Added ${successCount} of ${totalToAdd} new ingredients. Some failed to add.${skippedCount > 0 ? ` ${skippedCount} already in list.` : ''}`)
        errorTimeoutRef.current = setTimeout(() => {
          setAddToListError(null)
          errorTimeoutRef.current = null
        }, 5000)
      } else {
        // Complete failure
        console.error('Failed to add ingredients to grocery list:', results.filter(r => r.status === 'rejected'))
        setAddToListError('Failed to add ingredients. Please try again.')
        errorTimeoutRef.current = setTimeout(() => {
          setAddToListError(null)
          errorTimeoutRef.current = null
        }, 5000)
      }
    } catch (error) {
      console.error('Unexpected error adding ingredients to grocery list:', error)
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
