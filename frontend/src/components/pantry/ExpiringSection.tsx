import InventoryRow from '../inventory/InventoryRow'
import { SectionHeader } from '../ui'
import type { InventoryItemListResponse } from '../../api/types'

interface ExpiringSectionProps {
  items: InventoryItemListResponse[]
}

/**
 * ExpiringSection component showing items expiring within 3 days
 *
 * Features:
 * - Displays items sorted by expiration date (soonest first)
 * - Uses InventoryRow component with inline actions
 * - Empty state: "Nothing expiring soon"
 * - Section header with olive period
 */
export default function ExpiringSection({ items }: ExpiringSectionProps) {
  // Sort items by expiration date (soonest first)
  const sortedItems = [...items].sort((a, b) => {
    if (!a.expiration_date) return 1
    if (!b.expiration_date) return -1
    return new Date(a.expiration_date).getTime() - new Date(b.expiration_date).getTime()
  })

  return (
    <div className="bg-cream-dark rounded-card border border-warm-border p-6 mb-6">
      <SectionHeader>Expiring Soon</SectionHeader>

      {sortedItems.length === 0 ? (
        <p className="text-text-secondary mt-4">Nothing expiring soon</p>
      ) : (
        <div className="mt-4 space-y-1">
          {sortedItems.map((item) => (
            <InventoryRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}
