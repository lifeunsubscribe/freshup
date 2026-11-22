import { useHaveGroceryItem, usePurchaseGroceryItem, useUnpurchaseGroceryItem } from '../../api'
import Pill from '../ui/Pill'
import ErrorBanner from '../ui/ErrorBanner'
import type { GroceryItemResponse } from '../../api/types'
import { useMutationErrorHandler } from '../../utils/mutationErrorUtils'
import { formatAmount, shortRecipeName } from '../../utils/amount'
import { Link } from 'react-router-dom'

export interface GroceryItemProps {
  item: GroceryItemResponse
  purchaserName?: string
  /** Leave out the recipe chip, for a list already grouped under the recipe. */
  hideRecipe?: boolean
  /** Who put it on the list, shown under the chip. */
  addedBy?: string
}

/**
 * GroceryItem component for grocery lists and shopping flows
 *
 * Features:
 * - Checkbox (18-20px) with 5-6px border radius
 * - Checked state: olive fill, strikethrough item name with tertiary text
 * - Amount in its own column ("2 tsp"), so amounts line up down the list
 * - Context chip on right: the recipe the item is for (short name, links to the
 *   recipe), "staple restock", or "manual"; who added it underneath
 * - "Have it" on an unbought item takes it off the list: it is already in the house
 * - Shows purchaser name when checked: "Sarah" in secondary text
 * - Optimistic updates: immediate visual feedback, API call in background
 * - Touch target: minimum 44px for mobile usability
 */
export default function GroceryItem({ item, purchaserName, hideRecipe = false, addedBy }: GroceryItemProps) {
  const purchaseMutation = usePurchaseGroceryItem()
  const unpurchaseMutation = useUnpurchaseGroceryItem()
  const haveMutation = useHaveGroceryItem()
  const { errorMessage, clearError, handleError } = useMutationErrorHandler()

  const handleCheckboxClick = () => {
    // Clear any existing error immediately when user retries to prevent stale error messages
    clearError()

    // Mutations use optimistic updates configured in the hooks
    // (see useGrocery.ts lines 200-241 for purchase, 257-286 for unpurchase)
    // Error handling is done via onError callbacks to avoid timing issues
    if (item.purchased) {
      unpurchaseMutation.mutate(item.id, {
        onError: (error) => handleError(error, 'Failed to unmark item. Please try again.'),
      })
    } else {
      purchaseMutation.mutate(item.id, {
        onError: (error) => handleError(error, 'Failed to mark item as purchased. Please try again.'),
      })
    }
  }

  const handleHaveClick = () => {
    clearError()
    haveMutation.mutate(item.id, {
      onError: (error) => handleError(error, 'Could not take this off the list. Please try again.'),
    })
  }

  // The recipes this item is for: several when dinners share an ingredient.
  const recipes: { id: string; name: string }[] = item.recipes?.length
    ? item.recipes
    : item.linked_recipe && item.recipe_name
      ? [{ id: item.linked_recipe, name: item.recipe_name }]
      : []

  // Check if any mutation is pending to prevent double-clicks
  const isPending =
    purchaseMutation.isPending || unpurchaseMutation.isPending || haveMutation.isPending

  // Map source to readable label for context chip
  const getSourceLabel = (): string => {
    switch (item.source) {
      case 'recipe':
        return 'recipe'
      case 'low_stock':
        return 'staple restock'
      case 'meal_plan':
        return 'meal plan'
      case 'manual':
      default:
        return 'manual'
    }
  }

  // Determine pill variant based on source
  const getSourceVariant = (): 'default' | 'success' | 'warning' | 'alert' => {
    switch (item.source) {
      case 'recipe':
      case 'meal_plan':
        return 'success' // Olive - from a recipe
      case 'low_stock':
        return 'warning' // Mocha - needs restocking
      case 'manual':
      default:
        return 'default' // Cream - manually added
    }
  }

  return (
    <div>
      <div className="flex items-start gap-3 py-2 min-h-[44px]">
        {/* Checkbox with touch target */}
        <button
          onClick={handleCheckboxClick}
          disabled={isPending}
          className="flex-shrink-0 p-2 -m-2 mt-[3px] touch-manipulation disabled:opacity-50 disabled:cursor-not-allowed"
          aria-label={
            item.purchased
              ? `Unmark ${item.item_name} as purchased`
              : `Mark ${item.item_name} as purchased`
          }
          aria-pressed={item.purchased}
          type="button"
        >
          {/* Custom checkbox: 19px size, 6px border radius */}
          <div
            className={`
              w-[19px] h-[19px] rounded-[6px] border-2 flex items-center justify-center
              transition-colors
              ${
                item.purchased
                  ? 'bg-olive border-olive'
                  : 'bg-white border-warm-border'
              }
            `}
          >
            {item.purchased && (
              <svg
                width="12"
                height="10"
                viewBox="0 0 12 10"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="text-cream"
              >
                <path
                  d="M1 5L4.5 8.5L11 1.5"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </div>
        </button>

        {/* Amount: its own column, so amounts line up down the list */}
        <span
          data-testid="grocery-amount"
          className={`flex-shrink-0 w-[68px] pt-[1px] text-[14px] tabular-nums ${
            item.purchased ? 'text-text-tertiary' : 'text-text-secondary'
          }`}
        >
          {formatAmount(item.quantity, item.unit)}
        </span>

        {/* Item name */}
        <div className="flex-1 min-w-0">
          <div
            className={`
              text-[15px] font-medium leading-snug
              ${item.purchased ? 'line-through text-text-tertiary' : 'text-text-primary'}
            `}
          >
            {item.item_name}
          </div>

          {/* Purchased by line (only shown when checked) */}
          {item.purchased && purchaserName && (
            <div className="text-xs text-text-secondary mt-0.5">
              {purchaserName}
            </div>
          )}
        </div>

        {/* "I have this": not needed after all, it is already in the house */}
        {!item.purchased && (
          <button
            onClick={handleHaveClick}
            disabled={isPending}
            aria-label={`I already have ${item.item_name}`}
            type="button"
            className="flex-shrink-0 px-1 -my-2 min-h-[44px] text-[13px] text-olive disabled:opacity-50"
          >
            Have it
          </button>
        )}

        {/* Right column: what the item is for, and who added it beneath */}
        <div className="flex-shrink-0 flex flex-col items-end gap-1 max-w-[42%]">
          {recipes.length > 0 ? (
            !hideRecipe && (
              <span className="flex items-center gap-1 max-w-full">
                <Link
                  to={`/recipes/${recipes[0].id}`}
                  title={`For ${recipes.map((r) => r.name).join(', ')}`}
                  aria-label={`For ${recipes.map((r) => r.name).join(' and ')}: open ${recipes[0].name}`}
                  className="inline-block max-w-full truncate px-2.5 py-1 text-tiny font-medium rounded-pill bg-olive text-cream hover:bg-olive-dark"
                >
                  {shortRecipeName(recipes[0].name)}
                </Link>
                {recipes.length > 1 && (
                  <span className="text-tiny font-medium text-olive-dark">+{recipes.length - 1}</span>
                )}
              </span>
            )
          ) : (
            <Pill variant={getSourceVariant()}>{getSourceLabel()}</Pill>
          )}
          {addedBy && <span className="text-xs text-text-secondary">Added by {addedBy}</span>}
        </div>
      </div>

      {/* Error message banner */}
      <ErrorBanner message={errorMessage} />
    </div>
  )
}
