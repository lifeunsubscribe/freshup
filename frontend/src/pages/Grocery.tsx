import { useState, useMemo } from 'react'
import PageContainer from '../components/layout/PageContainer'
import { PageTitle } from '../components/ui'
import GroceryItem from '../components/grocery/GroceryItem'
import {
  useGroceryListByStore,
  useGroceryList,
  useCreateGroceryItem,
  useUsers,
} from '../api'
import { useMutationErrorHandler } from '../utils/mutationErrorUtils'
import ErrorBanner from '../components/ui/ErrorBanner'
import type { GroceryItemResponse, UserListResponse } from '../api/types'

type ViewMode = 'by-store' | 'flat'

/**
 * Grocery page - Shared household shopping list
 *
 * Features:
 * - Two view modes: by-store (default) and flat list
 * - 30-second polling for real-time shared updates
 * - Add item form in bottom action bar
 * - Per-user attribution display
 * - Optimistic checkbox updates via GroceryItem component
 */
export default function Grocery() {
  const [viewMode, setViewMode] = useState<ViewMode>('by-store')
  const [showAddForm, setShowAddForm] = useState(false)
  const [itemName, setItemName] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [unit, setUnit] = useState('unit')
  const [targetStore, setTargetStore] = useState('')

  // Fetch data with 30s polling
  const {
    data: byStoreData,
    isLoading: isLoadingByStore,
    error: byStoreError,
  } = useGroceryListByStore(false, {
    refetchInterval: 30000, // 30 second polling
  })

  const {
    data: flatListData = [],
    isLoading: isLoadingFlat,
    error: flatError,
  } = useGroceryList(
    {},
    {
      refetchInterval: 30000, // 30 second polling
    }
  )

  // Fetch users for name lookup
  const { data: users = [] } = useUsers()

  // Create mutation
  const createMutation = useCreateGroceryItem()
  const { errorMessage, clearError, handleError } = useMutationErrorHandler()

  // User lookup helper
  const getUserName = (userId: string): string => {
    const user = users.find((u: UserListResponse) => u.id === userId)
    return user?.name || 'Someone'
  }

  // Calculate total item counts
  const { totalItems, checkedItems } = useMemo(() => {
    let items: GroceryItemResponse[] = []

    if (viewMode === 'by-store' && byStoreData) {
      items = [
        ...byStoreData.stores.flatMap((store) => store.items),
        ...byStoreData.unassigned,
      ]
    } else {
      items = flatListData
    }

    return {
      totalItems: items.length,
      checkedItems: items.filter((item) => item.purchased).length,
    }
  }, [viewMode, byStoreData, flatListData])

  // Handle add item
  const handleAddItem = async (e: React.FormEvent) => {
    e.preventDefault()
    clearError()

    if (!itemName.trim()) {
      handleError(new Error('Item name is required'), 'Item name is required')
      return
    }

    const quantityNum = parseFloat(quantity)
    if (isNaN(quantityNum) || quantityNum <= 0) {
      handleError(new Error('Invalid quantity'), 'Quantity must be a positive number')
      return
    }

    createMutation.mutate(
      {
        item_name: itemName.trim(),
        quantity: quantityNum,
        unit: unit.trim() || 'unit',
        source: 'manual',
        target_store: targetStore.trim() || undefined,
      },
      {
        onSuccess: () => {
          // Reset form
          setItemName('')
          setQuantity('1')
          setUnit('unit')
          setTargetStore('')
          setShowAddForm(false)
        },
        onError: (error) => handleError(error, 'Failed to add item. Please try again.'),
      }
    )
  }

  const isLoading = viewMode === 'by-store' ? isLoadingByStore : isLoadingFlat
  const error = viewMode === 'by-store' ? byStoreError : flatError

  return (
    <PageContainer>
      <div className="py-6 pb-32">
        <PageTitle>Grocery List</PageTitle>
        <p className="text-text-secondary mb-6">
          Shared shopping list for the household
        </p>

        {/* View toggle */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setViewMode('by-store')}
            className={`flex-1 py-2 px-4 rounded-lg font-medium text-sm transition-colors ${
              viewMode === 'by-store'
                ? 'bg-olive text-cream'
                : 'bg-white text-text-secondary border border-warm-border'
            }`}
          >
            By Store
          </button>
          <button
            onClick={() => setViewMode('flat')}
            className={`flex-1 py-2 px-4 rounded-lg font-medium text-sm transition-colors ${
              viewMode === 'flat'
                ? 'bg-olive text-cream'
                : 'bg-white text-text-secondary border border-warm-border'
            }`}
          >
            All Items
          </button>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="bg-white rounded-card border border-warm-border p-6">
            <p className="text-text-secondary">Loading grocery list...</p>
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="bg-white rounded-card border border-warm-border p-6">
            <p className="text-red-600">
              Failed to load grocery list. Please try again.
            </p>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !error && totalItems === 0 && (
          <div className="bg-white rounded-card border border-warm-border p-8 text-center">
            <h2 className="text-lg font-medium text-text-primary mb-2">
              Your grocery list is empty
            </h2>
            <p className="text-text-secondary mb-4">
              Add your first item to get started{viewMode === 'by-store' ? '' : '.'}
            </p>
            <button
              onClick={() => setShowAddForm(true)}
              className="text-olive font-medium hover:underline"
            >
              Add your first item.
            </button>
          </div>
        )}

        {/* By-Store View */}
        {!isLoading &&
          !error &&
          viewMode === 'by-store' &&
          byStoreData &&
          totalItems > 0 && (
            <div className="space-y-6">
              {/* Store groups */}
              {byStoreData.stores.map((store) => (
                <div key={store.store_id} className="bg-white rounded-card border border-warm-border">
                  <div className="px-4 py-3 border-b border-warm-border">
                    <h3 className="text-[15px] font-medium text-text-primary">
                      {store.store_name}
                      <span className="ml-2 text-sm text-text-secondary font-normal">
                        ({store.items.length} {store.items.length === 1 ? 'item' : 'items'})
                      </span>
                    </h3>
                  </div>
                  <div className="divide-y divide-warm-border">
                    {store.items.map((item) => (
                      <div key={item.id} className="px-4">
                        <GroceryItem
                          item={item}
                          purchaserName={item.purchased_by ? getUserName(item.purchased_by) : undefined}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ))}

              {/* Unassigned items */}
              {byStoreData.unassigned.length > 0 && (
                <div className="bg-white rounded-card border border-warm-border">
                  <div className="px-4 py-3 border-b border-warm-border">
                    <h3 className="text-[15px] font-medium text-text-primary">
                      No store
                      <span className="ml-2 text-sm text-text-secondary font-normal">
                        ({byStoreData.unassigned.length}{' '}
                        {byStoreData.unassigned.length === 1 ? 'item' : 'items'})
                      </span>
                    </h3>
                  </div>
                  <div className="divide-y divide-warm-border">
                    {byStoreData.unassigned.map((item) => (
                      <div key={item.id} className="px-4">
                        <GroceryItem
                          item={item}
                          purchaserName={item.purchased_by ? getUserName(item.purchased_by) : undefined}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

        {/* Flat View */}
        {!isLoading &&
          !error &&
          viewMode === 'flat' &&
          flatListData.length > 0 && (
            <div className="bg-white rounded-card border border-warm-border">
              <div className="divide-y divide-warm-border">
                {flatListData.map((item) => (
                  <div key={item.id} className="px-4">
                    <div className="py-1">
                      <GroceryItem
                        item={item}
                        purchaserName={item.purchased_by ? getUserName(item.purchased_by) : undefined}
                      />
                      {/* Attribution line in flat view */}
                      <p className="text-xs text-text-secondary mt-1 mb-2">
                        Added by {getUserName(item.added_by)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
      </div>

      {/* Bottom Action Bar - Fixed at bottom */}
      {!showAddForm && (
        <div className="fixed bottom-16 left-0 right-0 bg-white border-t border-warm-border">
          <div className="max-w-screen-lg mx-auto px-4 py-3 flex items-center justify-between">
            <div className="text-sm text-text-secondary">
              {totalItems} {totalItems === 1 ? 'item' : 'items'} · {checkedItems} checked
            </div>
            <button
              onClick={() => setShowAddForm(true)}
              className="px-4 py-2 bg-olive text-cream rounded-lg font-medium text-sm hover:bg-[#6b7c4b] transition-colors"
            >
              Add Item
            </button>
          </div>
        </div>
      )}

      {/* Add Item Form - Fixed at bottom */}
      {showAddForm && (
        <div className="fixed bottom-16 left-0 right-0 bg-white border-t border-warm-border shadow-lg">
          <div className="max-w-screen-lg mx-auto px-4 py-4">
            <form onSubmit={handleAddItem} className="space-y-3">
              {/* Error banner */}
              <ErrorBanner message={errorMessage} />

              {/* Item name */}
              <div>
                <label htmlFor="item-name" className="block text-sm font-medium text-text-primary mb-1">
                  Item name *
                </label>
                <input
                  id="item-name"
                  type="text"
                  value={itemName}
                  onChange={(e) => setItemName(e.target.value)}
                  placeholder="e.g., Olive oil"
                  className="w-full px-3 py-2 border border-warm-border rounded-lg focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
                  autoFocus
                />
              </div>

              {/* Quantity and Unit */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label htmlFor="quantity" className="block text-sm font-medium text-text-primary mb-1">
                    Quantity
                  </label>
                  <input
                    id="quantity"
                    type="number"
                    step="0.1"
                    min="0.1"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    className="w-full px-3 py-2 border border-warm-border rounded-lg focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
                  />
                </div>
                <div>
                  <label htmlFor="unit" className="block text-sm font-medium text-text-primary mb-1">
                    Unit
                  </label>
                  <input
                    id="unit"
                    type="text"
                    value={unit}
                    onChange={(e) => setUnit(e.target.value)}
                    placeholder="e.g., bottle, lb"
                    className="w-full px-3 py-2 border border-warm-border rounded-lg focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
                  />
                </div>
              </div>

              {/* Store (optional) */}
              <div>
                <label htmlFor="store" className="block text-sm font-medium text-text-primary mb-1">
                  Store (optional)
                </label>
                <input
                  id="store"
                  type="text"
                  value={targetStore}
                  onChange={(e) => setTargetStore(e.target.value)}
                  placeholder="e.g., Whole Foods"
                  className="w-full px-3 py-2 border border-warm-border rounded-lg focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
                />
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddForm(false)
                    clearError()
                  }}
                  className="flex-1 px-4 py-2 border border-warm-border text-text-primary rounded-lg font-medium text-sm hover:bg-cream transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="flex-1 px-4 py-2 bg-olive text-cream rounded-lg font-medium text-sm hover:bg-[#6b7c4b] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {createMutation.isPending ? 'Adding...' : 'Add'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </PageContainer>
  )
}
