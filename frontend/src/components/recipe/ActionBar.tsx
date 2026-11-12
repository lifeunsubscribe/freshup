import { ShoppingCart } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import { useCreateGroceryItem, useGroceryList } from '../../api/hooks/useGrocery'
import type { IngredientStockStatus } from '../../utils/pantryMatcher'
import { batchPromises } from '../../utils/batchPromises'

interface ActionBarProps {
  onCookThis: () => Promise<void>
  onAddToPlan: () => void
  isLoading?: boolean
  missingIngredients?: IngredientStockStatus[]
}

/**
 * ActionBar component for recipe detail actions
 *
 * Features:
 * - Fixed bottom bar (mobile-friendly)
 * - "Add missing to list" button (pantry cross-reference; moves to #550)
 * - "I cooked this" button (posts cook event)
 * - "Add to plan" button (opens AddToPlanSheet)
 */
export default function ActionBar({
  onCookThis,
  onAddToPlan,
  isLoading = false,
  missingIngredients = [],
}: ActionBarProps) {
  const createGroceryItem = useCreateGroceryItem()
  const { data: existingGroceryItems = [], refetch: refetchGroceryList } = useGroceryList({ purchased: false })
  const [isAddingToList, setIsAddingToList] = useState(false)
  const [addToListError, setAddToListError] = useState<string | null>(null)
  const [addToListSuccess, setAddToListSuccess] = useState(false)
  const [isCooking, setIsCooking] = useState(false)
  const [cookSuccess, setCookSuccess] = useState(false)
  const errorTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const successTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const cookSuccessTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const addedItemsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    return () => {
      if (errorTimeoutRef.current) clearTimeout(errorTimeoutRef.current)
      if (successTimeoutRef.current) clearTimeout(successTimeoutRef.current)
      if (cookSuccessTimeoutRef.current) clearTimeout(cookSuccessTimeoutRef.current)
    }
  }, [])

  useEffect(() => {
    const currentItemNames = new Set(
      existingGroceryItems.map(item => item.item_name.toLowerCase())
    )
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

    if (errorTimeoutRef.current) {
      clearTimeout(errorTimeoutRef.current)
      errorTimeoutRef.current = null
    }

    try {
      const { data: latestGroceryItems } = await refetchGroceryList()
      const currentGroceryItems = latestGroceryItems || existingGroceryItems

      const existingItemNames = new Set(
        currentGroceryItems.map(item => item.item_name.toLowerCase())
      )

      const ingredientsToAdd = missingIngredients.filter(
        ({ ingredient }) => {
          const itemNameLower = ingredient.ingredient_name.toLowerCase()
          return !existingItemNames.has(itemNameLower) && !addedItemsRef.current.has(itemNameLower)
        }
      )

      if (ingredientsToAdd.length === 0) {
        setAddToListSuccess(true)
        successTimeoutRef.current = setTimeout(() => {
          setAddToListSuccess(false)
          successTimeoutRef.current = null
        }, 3000)
        setIsAddingToList(false)
        return
      }

      const promiseFns = ingredientsToAdd.map(({ ingredient }) => () =>
        createGroceryItem.mutateAsync({
          item_name: ingredient.ingredient_name,
          quantity: ingredient.quantity,
          unit: ingredient.unit,
          source: 'recipe',
        })
      )
      const results = await batchPromises(promiseFns, 5)

      const successCount = results.filter(r => r.status === 'fulfilled').length
      const failureCount = results.filter(r => r.status === 'rejected').length
      const skippedCount = missingIngredients.length - ingredientsToAdd.length

      if (successCount > 0) {
        results.forEach((result, index) => {
          if (result.status === 'fulfilled') {
            const itemNameLower = ingredientsToAdd[index].ingredient.ingredient_name.toLowerCase()
            addedItemsRef.current.add(itemNameLower)
          }
        })
      }

      if (failureCount === 0) {
        setAddToListSuccess(true)
        successTimeoutRef.current = setTimeout(() => {
          setAddToListSuccess(false)
          successTimeoutRef.current = null
        }, 3000)
      } else if (successCount > 0) {
        console.error('Some ingredients failed to add:', results.filter(r => r.status === 'rejected'))
        const totalToAdd = ingredientsToAdd.length
        setAddToListError(`Added ${successCount} of ${totalToAdd} new ingredients. Some failed to add.${skippedCount > 0 ? ` ${skippedCount} already in list.` : ''}`)
        errorTimeoutRef.current = setTimeout(() => {
          setAddToListError(null)
          errorTimeoutRef.current = null
        }, 5000)
      } else {
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

  const handleCookThis = async () => {
    if (isCooking || cookSuccess) return
    setIsCooking(true)
    try {
      await onCookThis()
      setCookSuccess(true)
      // Reset to normal after 2 s (#549 rating offer picks up after this)
      cookSuccessTimeoutRef.current = setTimeout(() => {
        setCookSuccess(false)
        cookSuccessTimeoutRef.current = null
      }, 2000)
    } finally {
      setIsCooking(false)
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
          {/* Add missing to list button (pantry cross-reference; moves to #550) */}
          <button
            onClick={handleAddMissingToList}
            disabled={isLoading || isAddingToList || allInStock || addToListSuccess}
            className="flex-shrink-0 p-3 rounded-button border-2 border-warm-border bg-cream hover:bg-cream-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            title={allInStock ? 'All ingredients are in stock' : addToListSuccess ? 'Ingredients added to list' : `Add ${missingCount} missing ingredient${missingCount === 1 ? '' : 's'} to grocery list`}
            aria-label={allInStock ? 'All ingredients in stock' : `Add ${missingCount} missing to list`}
          >
            <ShoppingCart size={20} />
          </button>

          {/* I cooked this */}
          <button
            onClick={handleCookThis}
            disabled={isLoading || isCooking}
            className="flex-1 bg-cream text-text-primary font-medium py-3 px-4 rounded-button border-2 border-warm-border hover:bg-cream-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {cookSuccess ? 'Cooked!' : 'I cooked this'}
          </button>

          {/* Add to plan */}
          <button
            onClick={onAddToPlan}
            disabled={isLoading}
            className="flex-1 bg-olive text-cream font-medium py-3 px-4 rounded-button hover:bg-olive-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Add to plan
          </button>
        </div>
      </div>
    </>
  )
}
