import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useBulkPurchaseGroceryItems } from '../../api'
import type { GroceryItemResponse, StorageLocation, Category } from '../../api/types'

interface SelectedItem {
  item: GroceryItemResponse
  storageLocation: StorageLocation
  category: Category
}

interface PurchaseSummaryProps {
  selectedItems: Map<string, SelectedItem>
  totalItems: number
  onSuccess: () => void
}

/**
 * PurchaseSummary component - Fixed bottom card with progress and confirm
 *
 * Features:
 * - Shows "X of Y items checked"
 * - Progress bar visualization
 * - "Done — add X items to pantry" button
 * - Calls bulk-purchase endpoint with create_inventory_item=true
 * - Success: shows confirmation, navigates to /pantry
 * - Error handling with user-friendly messages
 */
export default function PurchaseSummary({
  selectedItems,
  totalItems,
  onSuccess,
}: PurchaseSummaryProps) {
  const navigate = useNavigate()
  const bulkPurchaseMutation = useBulkPurchaseGroceryItems()
  const [showSuccess, setShowSuccess] = useState(false)

  const selectedCount = selectedItems.size
  const progressPercentage = totalItems > 0 ? (selectedCount / totalItems) * 100 : 0

  /**
   * Handles bulk purchase confirmation by grouping items and calling the API.
   *
   * The backend bulk-purchase endpoint requires all items in a request to share
   * the same storage_location and category for inventory creation. Therefore,
   * we group selected items by storage+category combination and make separate
   * API calls for each group.
   *
   * On success, shows confirmation toast and navigates to /pantry.
   */
  const handleConfirm = async () => {
    // Group items by storage location + category combination (backend constraint)
    const groups = new Map<string, SelectedItem[]>()
    selectedItems.forEach((selectedItem) => {
      const key = `${selectedItem.storageLocation}:${selectedItem.category}`
      if (!groups.has(key)) {
        groups.set(key, [])
      }
      groups.get(key)!.push(selectedItem)
    })

    // Execute bulk purchase for each group
    try {
      for (const [key, items] of groups.entries()) {
        const [storageLocation, category] = key.split(':')
        const itemIds = items.map((item) => item.item.id)

        await bulkPurchaseMutation.mutateAsync({
          item_ids: itemIds,
          create_inventory_item: true,
          storage_location: storageLocation,
          category: category,
        })
      }

      // Success: show confirmation and navigate
      setShowSuccess(true)
      onSuccess()

      // Navigate to pantry after short delay
      setTimeout(() => {
        navigate('/pantry')
      }, 1500)
    } catch (error) {
      // Error handling is done by the mutation's error state
      console.error('Bulk purchase failed:', error)
    }
  }

  // Auto-dismiss success message
  useEffect(() => {
    if (showSuccess) {
      const timer = setTimeout(() => setShowSuccess(false), 2000)
      return () => clearTimeout(timer)
    }
  }, [showSuccess])

  return (
    <>
      {/* Success toast */}
      {showSuccess && (
        <div
          className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 bg-olive text-white px-6 py-3 rounded-button shadow-lg"
          role="alert"
        >
          <p className="text-sm font-medium">
            {selectedCount} {selectedCount === 1 ? 'item' : 'items'} added to pantry!
          </p>
        </div>
      )}

      {/* Fixed bottom card */}
      <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-warm-border p-4 shadow-lg z-40">
        <div className="max-w-2xl mx-auto">
          {/* Progress text */}
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-text-primary">
              {selectedCount} of {totalItems} items checked
            </p>
            <p className="text-xs text-text-secondary">{Math.round(progressPercentage)}%</p>
          </div>

          {/* Progress bar */}
          <div className="w-full h-2 bg-cream rounded-full mb-4">
            <div
              className="h-full bg-olive rounded-full transition-all duration-300"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>

          {/* Confirm button */}
          <button
            onClick={handleConfirm}
            disabled={bulkPurchaseMutation.isPending || selectedCount === 0}
            className="w-full py-3 bg-olive text-white rounded-button font-medium hover:bg-olive-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            type="button"
          >
            {bulkPurchaseMutation.isPending
              ? 'Adding to pantry...'
              : `Done — add ${selectedCount} ${selectedCount === 1 ? 'item' : 'items'} to pantry`}
          </button>

          {/* Error message */}
          {bulkPurchaseMutation.isError && (
            <div
              className="mt-3 px-3 py-2 bg-red-50 border border-red-200 rounded-md text-sm text-red-800"
              role="alert"
            >
              Failed to add items. Please try again.
            </div>
          )}
        </div>
      </div>
    </>
  )
}
