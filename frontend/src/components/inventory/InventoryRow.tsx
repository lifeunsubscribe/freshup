import {
  useConsumeInventoryItem,
  useFreezeInventoryItem,
  useUpdateInventoryItem,
} from '../../api'
import type { InventoryItemResponse, InventoryItemListResponse } from '../../api/types'
import { StorageLocation } from '../../api/types'
import Pill from '../ui/Pill'
import ErrorBanner from '../ui/ErrorBanner'
import StorageBadge from './StorageBadge'
import { getDaysUntilDate, formatExpirationBadge } from '../../utils/dateUtils'
import { useMutationErrorHandler } from '../../utils/mutationErrorUtils'

export interface InventoryRowProps {
  item: InventoryItemResponse | InventoryItemListResponse
}

/**
 * InventoryRow component for pantry category lists and snack checklists
 *
 * Features:
 * - Item name: 14px primary text
 * - Expiry badge: relative time ("3d", "tomorrow", "today") in mocha pill
 * - Low stock badge: "low" in terra pill (when below minimum_threshold)
 * - Quantity: right-aligned secondary text (e.g., "2.5 lb")
 * - StorageBadge: tappable, cycles through fridge/freezer/pantry/counter
 * - Quick actions for expiring items: "Ate it", "Freeze" buttons
 * - Optimistic updates with error handling
 */
export default function InventoryRow({ item }: InventoryRowProps) {
  const consumeMutation = useConsumeInventoryItem()
  const freezeMutation = useFreezeInventoryItem()
  const updateMutation = useUpdateInventoryItem()
  const { errorMessage, clearError, handleError } = useMutationErrorHandler()

  // Calculate days until expiration using timezone-safe utility
  const getDaysUntilExpiration = (): number | null => {
    if (!item.expiration_date) return null
    return getDaysUntilDate(item.expiration_date)
  }

  // Format expiry badge text using timezone-safe utility
  const getExpiryBadgeText = (): string | null => {
    if (!item.expiration_date) return null
    return formatExpirationBadge(item.expiration_date)
  }

  // Check if item is low stock
  const isLowStock = (): boolean => {
    // minimum_threshold only exists on InventoryItemResponse, not InventoryItemListResponse
    const threshold = 'minimum_threshold' in item ? item.minimum_threshold : null
    return (
      threshold !== null &&
      item.quantity < threshold
    )
  }

  // Check if should show quick actions (expiring within 3 days)
  const shouldShowQuickActions = (): boolean => {
    const daysUntil = getDaysUntilExpiration()
    return daysUntil !== null && daysUntil >= 0 && daysUntil <= 3
  }

  // Handle "Ate it" action
  const handleAteIt = () => {
    // Clear any existing error immediately when user retries to prevent stale error messages
    clearError()
    consumeMutation.mutate(
      {
        id: item.id,
        data: {
          amount: item.quantity,
          delete_when_empty: true,
        },
      },
      {
        onError: (error) => handleError(error, 'Failed to consume item. Please try again.'),
      }
    )
  }

  // Handle "Freeze" action
  const handleFreeze = () => {
    // Clear any existing error immediately when user retries to prevent stale error messages
    clearError()
    freezeMutation.mutate(item.id, {
      onError: (error) => handleError(error, 'Failed to freeze item. Please try again.'),
    })
  }

  // Handle storage location cycle
  const handleStorageCycle = (newLocation: StorageLocation) => {
    // Clear any existing error immediately when user retries to prevent stale error messages
    clearError()
    updateMutation.mutate(
      {
        id: item.id,
        data: {
          storage_location: newLocation,
        },
      },
      {
        onError: (error) => handleError(error, 'Failed to update storage. Please try again.'),
      }
    )
  }

  const daysUntilExpiration = getDaysUntilExpiration()
  const expiryBadgeText = getExpiryBadgeText()
  const showQuickActions = shouldShowQuickActions()
  const lowStock = isLowStock()

  // Check if any mutation is pending
  const isPending =
    consumeMutation.isPending ||
    freezeMutation.isPending ||
    updateMutation.isPending

  return (
    <div>
      <div className="flex items-center gap-3 py-2 min-h-[44px]">
        {/* Item name and badges */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            {/* Item name: 14px primary text */}
            <span className="text-[14px] font-normal text-text-primary">
              {item.name}
            </span>

            {/* Expiry badge: mocha pill */}
            {expiryBadgeText && (
              <Pill variant="warning">{expiryBadgeText}</Pill>
            )}

            {/* Low stock badge: terra pill */}
            {lowStock && <Pill variant="alert">low</Pill>}
          </div>

          {/* Quick actions for expiring items */}
          {showQuickActions && (
            <div className="flex gap-2 mt-2">
              <button
                onClick={handleAteIt}
                disabled={isPending}
                className="px-3 py-1 text-xs font-medium text-olive bg-white border border-olive rounded-[6px] hover:bg-olive hover:text-cream transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                type="button"
              >
                Ate it
              </button>
              <button
                onClick={handleFreeze}
                disabled={isPending || item.storage_location === StorageLocation.FREEZER}
                className="px-3 py-1 text-xs font-medium text-mocha bg-white border border-mocha rounded-[6px] hover:bg-mocha hover:text-cream transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                type="button"
              >
                Freeze
              </button>
            </div>
          )}
        </div>

        {/* Storage badge */}
        <div className="flex-shrink-0">
          <StorageBadge
            storageLocation={item.storage_location}
            onCycle={handleStorageCycle}
            disabled={isPending}
          />
        </div>

        {/* Quantity: right-aligned secondary text */}
        <div className="flex-shrink-0 text-right min-w-[60px]">
          <span className="text-sm text-text-secondary">
            {item.quantity} {item.unit}
          </span>
        </div>
      </div>

      {/* Error message banner */}
      <ErrorBanner message={errorMessage} />
    </div>
  )
}
