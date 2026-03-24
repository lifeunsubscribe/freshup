import { useState, useMemo, useEffect } from 'react'
import PageContainer from '../components/layout/PageContainer'
import { PageTitle } from '../components/ui'
import StorageTabs from '../components/pantry/StorageTabs'
import StatCards from '../components/pantry/StatCards'
import ExpiringSection from '../components/pantry/ExpiringSection'
import LowStockSection from '../components/pantry/LowStockSection'
import CategoryGroup from '../components/pantry/CategoryGroup'
import { useInventoryList, useLowStockAlerts } from '../api'
import { StorageLocation, type InventoryItemListResponse } from '../api/types'

type StorageTab = 'all' | StorageLocation

const ITEMS_PER_PAGE = 100

export default function Pantry() {
  const [activeTab, setActiveTab] = useState<StorageTab>('all')
  const [offset, setOffset] = useState(0)
  const [allItems, setAllItems] = useState<InventoryItemListResponse[]>([])
  const [hasMore, setHasMore] = useState(true)

  // Fetch inventory with storage filter
  const storageFilter = activeTab === 'all' ? undefined : activeTab
  const { data: inventoryItems = [], isLoading: isLoadingInventory, error: inventoryError } = useInventoryList({
    storage_location: storageFilter,
    limit: ITEMS_PER_PAGE,
    offset,
  })

  // Accumulate items and track if there are more to load
  useEffect(() => {
    if (inventoryItems.length > 0) {
      if (offset === 0) {
        // First load - replace all items
        setAllItems(inventoryItems)
      } else {
        // Subsequent loads - append new items
        setAllItems((prev) => [...prev, ...inventoryItems])
      }
      // If we got fewer items than requested, there are no more to load
      setHasMore(inventoryItems.length === ITEMS_PER_PAGE)
    } else if (offset === 0) {
      // First load returned empty - reset state
      setAllItems([])
      setHasMore(false)
    }
  }, [inventoryItems, offset])

  // Reset pagination when tab changes
  useEffect(() => {
    setOffset(0)
    setAllItems([])
    setHasMore(true)
  }, [activeTab])

  // Fetch low stock alerts
  const { data: lowStockItems = [], isLoading: isLoadingLowStock, error: lowStockError } = useLowStockAlerts()

  // Calculate expiring items (within 3 days)
  const expiringItems = useMemo(() => {
    const now = new Date()
    const threeDaysFromNow = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000)

    return allItems.filter((item) => {
      if (!item.expiration_date) return false
      const expiryDate = new Date(item.expiration_date)
      return expiryDate >= now && expiryDate <= threeDaysFromNow
    })
  }, [allItems])

  // Group remaining items by category (exclude expiring items)
  const categoryGroups = useMemo(() => {
    const expiringIds = new Set(expiringItems.map((item) => item.id))
    const remainingItems = allItems.filter((item) => !expiringIds.has(item.id))

    // Group by category
    const groups = remainingItems.reduce(
      (acc, item) => {
        if (!acc[item.category]) {
          acc[item.category] = []
        }
        acc[item.category].push(item)
        return acc
      },
      {} as Record<string, typeof remainingItems>
    )

    // Sort categories alphabetically
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
  }, [allItems, expiringItems])

  // Loading state
  if (isLoadingInventory || isLoadingLowStock) {
    return (
      <PageContainer>
        <div className="py-8">
          <PageTitle>Pantry</PageTitle>
          <p className="text-text-secondary mt-4">Loading inventory...</p>
        </div>
      </PageContainer>
    )
  }

  // Error state
  if (inventoryError || lowStockError) {
    return (
      <PageContainer>
        <div className="py-8">
          <PageTitle>Pantry</PageTitle>
          <div className="bg-red-50 border border-red-200 rounded-card p-6 mt-4">
            <p className="text-red-800 font-medium">Failed to load inventory data</p>
            <p className="text-red-600 text-sm mt-2">
              {inventoryError?.message || lowStockError?.message || 'An unexpected error occurred. Please try again later.'}
            </p>
          </div>
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      <div className="py-8">
        <PageTitle>Pantry</PageTitle>
        <p className="text-text-secondary mb-6 mt-2">
          Manage your kitchen inventory
        </p>

        {/* Storage filter tabs */}
        <StorageTabs activeTab={activeTab} onTabChange={setActiveTab} />

        {/* Statistics cards */}
        <StatCards
          totalItems={allItems.length}
          expiringSoonCount={expiringItems.length}
          lowStockCount={lowStockItems.length}
        />

        {/* Triage sections: Expiring Soon */}
        <ExpiringSection items={expiringItems} />

        {/* Triage sections: Low Stock */}
        <LowStockSection items={lowStockItems} />

        {/* Category groups (collapsible) */}
        {categoryGroups.length > 0 ? (
          <div>
            {categoryGroups.map(([category, items]) => (
              <CategoryGroup key={category} category={category} items={items} />
            ))}
          </div>
        ) : (
          <div className="bg-white rounded-card border border-warm-border p-6">
            <p className="text-text-secondary">
              {allItems.length === 0
                ? 'No items in pantry yet. Add items to get started!'
                : 'All items are expiring soon. Check the triage sections above.'}
            </p>
          </div>
        )}

        {/* Load More button */}
        {hasMore && !isLoadingInventory && (
          <div className="flex justify-center mt-6">
            <button
              onClick={() => setOffset((prev) => prev + ITEMS_PER_PAGE)}
              className="px-6 py-2 bg-white border border-warm-border rounded-md text-sm font-medium text-text-primary hover:bg-gray-50 transition-colors"
            >
              Load More Items
            </button>
          </div>
        )}

        {/* Loading indicator for pagination */}
        {isLoadingInventory && offset > 0 && (
          <div className="flex justify-center mt-6">
            <p className="text-sm text-text-secondary">Loading more items...</p>
          </div>
        )}
      </div>
    </PageContainer>
  )
}
