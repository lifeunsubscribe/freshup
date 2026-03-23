import { useState, useEffect } from 'react'
import {
  useConsumeInventoryItem,
  useFreezeInventoryItem,
  useUpdateInventoryItem,
} from '../../api'
import type { InventoryItemResponse } from '../../api/types'
import { StorageLocation } from '../../api/types'
import Pill from '../ui/Pill'
import StorageBadge from './StorageBadge'

export interface InventoryRowProps {
  item: InventoryItemResponse
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
  const consumeMutation = useConsumeInventoryItem(item.id)
  const freezeMutation = useFreezeInventoryItem(item.id)
  const updateMutation = useUpdateInventoryItem(item.id)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Track errors from mutations
  useEffect(() => {
    if (consumeMutation.isError) {
      setErrorMessage('Failed to consume item. Please try again.')
    } else if (freezeMutation.isError) {
      setErrorMessage('Failed to freeze item. Please try again.')
    } else if (updateMutation.isError) {
      setErrorMessage('Failed to update storage. Please try again.')
    } else {
      setErrorMessage(null)
    }
  }, [consumeMutation.isError, freezeMutation.isError, updateMutation.isError])

  // Auto-dismiss error after 5 seconds
  useEffect(() => {
    if (errorMessage) {
      const timer = setTimeout(() => setErrorMessage(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [errorMessage])

  // Calculate days until expiration
  const getDaysUntilExpiration = (): number | null => {
    if (!item.expiration_date) return null

    const today = new Date()
    today.setHours(0, 0, 0, 0)

    const expiryDate = new Date(item.expiration_date)
    expiryDate.setHours(0, 0, 0, 0)

    const diffTime = expiryDate.getTime() - today.getTime()
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

    return diffDays
  }

  // Format expiry badge text
  const getExpiryBadgeText = (daysUntil: number | null): string | null => {
    if (daysUntil === null) return null
    if (daysUntil < 0) return 'expired'
    if (daysUntil === 0) return 'today'
    if (daysUntil === 1) return 'tomorrow'
    if (daysUntil <= 7) return `${daysUntil}d`
    return null // Don't show badge if more than 7 days
  }

  // Check if item is low stock
  const isLowStock = (): boolean => {
    return (
      item.minimum_threshold !== null &&
      item.quantity < item.minimum_threshold
    )
  }

  // Check if should show quick actions (expiring within 3 days)
  const shouldShowQuickActions = (): boolean => {
    const daysUntil = getDaysUntilExpiration()
    return daysUntil !== null && daysUntil >= 0 && daysUntil <= 3
  }

  // Handle "Ate it" action
  const handleAteIt = () => {
    setErrorMessage(null)
    consumeMutation.mutate({
      amount: item.quantity,
      delete_when_empty: true,
    })
  }

  // Handle "Freeze" action
  const handleFreeze = () => {
    setErrorMessage(null)
    freezeMutation.mutate()
  }

  // Handle storage location cycle
  const handleStorageCycle = (newLocation: StorageLocation) => {
    setErrorMessage(null)
    updateMutation.mutate({
      storage_location: newLocation,
    })
  }

  const daysUntilExpiration = getDaysUntilExpiration()
  const expiryBadgeText = getExpiryBadgeText(daysUntilExpiration)
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
      {errorMessage && (
        <div
          className="mt-1 px-3 py-2 bg-red-50 border border-red-200 rounded-md text-sm text-red-800"
          role="alert"
        >
          {errorMessage}
        </div>
      )}
    </div>
  )
}
