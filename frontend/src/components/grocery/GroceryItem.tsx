import { usePurchaseGroceryItem, useUnpurchaseGroceryItem } from '../../api'
import Pill from '../ui/Pill'
import ErrorBanner from '../ui/ErrorBanner'
import type { GroceryItemResponse } from '../../api/types'
import { useMutationErrorHandler } from '../../utils/mutationErrorUtils'

export interface GroceryItemProps {
  item: GroceryItemResponse
  purchaserName?: string
}

/**
 * GroceryItem component for grocery lists and shopping flows
 *
 * Features:
 * - Checkbox (18-20px) with 5-6px border radius
 * - Checked state: olive fill, strikethrough item name with tertiary text
 * - Item name and quantity inline: "Olive oil (1 bottle)"
 * - Context chip on right: recipe name, "staple restock", or "manual" source
 * - Shows purchaser name when checked: "Sarah" in secondary text
 * - Optimistic updates: immediate visual feedback, API call in background
 * - Touch target: minimum 44px for mobile usability
 */
export default function GroceryItem({ item, purchaserName }: GroceryItemProps) {
  const purchaseMutation = usePurchaseGroceryItem()
  const unpurchaseMutation = useUnpurchaseGroceryItem()
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

  // Check if either mutation is pending to prevent double-clicks
  const isPending = purchaseMutation.isPending || unpurchaseMutation.isPending

  // Map source to readable label for context chip
  const getSourceLabel = (): string => {
    switch (item.source) {
      case 'recipe':
        return 'recipe'
      case 'low_stock':
        return 'staple restock'
      case 'manual':
      default:
        return 'manual'
    }
  }

  // Determine pill variant based on source
  const getSourceVariant = (): 'default' | 'success' | 'warning' | 'alert' => {
    switch (item.source) {
      case 'recipe':
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
      <div className="flex items-center gap-3 py-2 min-h-[44px]">
        {/* Checkbox with touch target */}
        <button
          onClick={handleCheckboxClick}
          disabled={isPending}
          className="flex-shrink-0 p-2 -m-2 touch-manipulation disabled:opacity-50 disabled:cursor-not-allowed"
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
            {/* Checkmark when purchased */}
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

        {/* Item name and quantity */}
        <div className="flex-1 min-w-0">
          <div
            className={`
              text-[15px] font-medium
              ${item.purchased ? 'line-through text-text-tertiary' : 'text-text-primary'}
            `}
          >
            {item.item_name}{' '}
            <span className="font-normal text-text-secondary">
              ({item.quantity} {item.unit})
            </span>
          </div>

          {/* Purchased by line (only shown when checked) */}
          {item.purchased && purchaserName && (
            <div className="text-xs text-text-secondary mt-0.5">
              {purchaserName}
            </div>
          )}
        </div>

        {/* Context chip on right */}
        <div className="flex-shrink-0">
          <Pill variant={getSourceVariant()}>{getSourceLabel()}</Pill>
        </div>
      </div>

      {/* Error message banner */}
      <ErrorBanner message={errorMessage} />
    </div>
  )
}
