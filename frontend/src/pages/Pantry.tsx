import { useState, useMemo } from 'react'
import PageContainer from '../components/layout/PageContainer'
import { PageTitle } from '../components/ui'
import StorageTabs from '../components/pantry/StorageTabs'
import StatCards from '../components/pantry/StatCards'
import ExpiringSection from '../components/pantry/ExpiringSection'
import LowStockSection from '../components/pantry/LowStockSection'
import CategoryGroup from '../components/pantry/CategoryGroup'
import { useInventoryList, useLowStockAlerts } from '../api'
import { StorageLocation } from '../api/types'

type StorageTab = 'all' | StorageLocation

export default function Pantry() {
  const [activeTab, setActiveTab] = useState<StorageTab>('all')

  // Fetch inventory with storage filter
  const storageFilter = activeTab === 'all' ? undefined : activeTab
  const { data: inventoryItems = [], isLoading: isLoadingInventory, error: inventoryError } = useInventoryList({
    storage_location: storageFilter,
    limit: 100,
  })

  // Fetch low stock alerts
  const { data: lowStockItems = [], isLoading: isLoadingLowStock, error: lowStockError } = useLowStockAlerts()

  // Calculate expiring items (within 3 days)
  const expiringItems = useMemo(() => {
    const now = new Date()
    const threeDaysFromNow = new Date(now.getTime() + 3 * 24 * 60 * 60 * 1000)

    return inventoryItems.filter((item) => {
      if (!item.expiration_date) return false
      const expiryDate = new Date(item.expiration_date)
      return expiryDate >= now && expiryDate <= threeDaysFromNow
    })
  }, [inventoryItems])

  // Group remaining items by category (exclude expiring items)
  const categoryGroups = useMemo(() => {
    const expiringIds = new Set(expiringItems.map((item) => item.id))
    const remainingItems = inventoryItems.filter((item) => !expiringIds.has(item.id))

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
  }, [inventoryItems, expiringItems])

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
          totalItems={inventoryItems.length}
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
              {inventoryItems.length === 0
                ? 'No items in pantry yet. Add items to get started!'
                : 'All items are expiring soon. Check the triage sections above.'}
            </p>
          </div>
        )}
      </div>
    </PageContainer>
  )
}
