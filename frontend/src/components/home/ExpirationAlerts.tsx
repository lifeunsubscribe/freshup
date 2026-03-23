import { useInventoryList } from '../../api'
import type { InventoryItemResponse } from '../../api/types'
import InventoryRow from '../inventory/InventoryRow'
import SectionHeader from '../ui/SectionHeader'

/**
 * ExpirationAlerts displays inventory items expiring within 3 days
 *
 * Features:
 * - Fetches items using useInventoryList with expiring_within_days filter
 * - Shows each item with InventoryRow component (includes inline actions)
 * - Empty state: friendly message when no items are expiring
 * - Loading state: simple loading message
 * - Error state: displays error message if fetch fails
 *
 * Note: The list API returns InventoryItemListResponse (lighter payload),
 * but InventoryRow handles missing fields gracefully. We type-assert here
 * since the component checks for null/undefined before using optional fields.
 */
export default function ExpirationAlerts() {
  const { data: items, isLoading, isError, error } = useInventoryList({
    expiring_within_days: 3,
  })

  return (
    <section>
      <SectionHeader>Expiring Soon</SectionHeader>

      <div className="mt-3">
        {isLoading && (
          <p className="text-sm text-text-secondary">Loading expiring items...</p>
        )}

        {isError && (
          <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-800">
            Failed to load expiring items.{' '}
            {error instanceof Error ? error.message : 'Please try again.'}
          </div>
        )}

        {!isLoading && !isError && items && items.length === 0 && (
          <p className="text-sm text-text-secondary">
            No items expiring soon. You're all set!
          </p>
        )}

        {!isLoading && !isError && items && items.length > 0 && (
          <div className="space-y-1">
            {items.map((item) => (
              <InventoryRow
                key={item.id}
                item={item as unknown as InventoryItemResponse}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
