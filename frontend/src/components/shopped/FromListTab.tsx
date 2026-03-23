import { useState, useMemo } from 'react'
import { useGroceryListByStore } from '../../api'
import { StorageLocation, Category, type GroceryItemResponse } from '../../api/types'
import StorageBadge from '../inventory/StorageBadge'
import PurchaseSummary from './PurchaseSummary'

interface SelectedItem {
  item: GroceryItemResponse
  storageLocation: StorageLocation
  category: Category
}

/**
 * FromListTab component - Main I Shopped flow
 *
 * Features:
 * - Fetches unchecked grocery items grouped by store
 * - Each item has checkbox and tappable StorageBadge
 * - Smart storage defaults based on category
 * - "Select all" per store section
 * - Bottom summary card with progress and confirm button
 */
export default function FromListTab() {
  const { data, isLoading, error } = useGroceryListByStore(false)
  const [selectedItems, setSelectedItems] = useState<Map<string, SelectedItem>>(new Map())

  /**
   * Determines smart default storage location based on item name keywords.
   * Priority: frozen items → refrigerated items → counter items → pantry (default)
   */
  const getStorageDefault = (item: GroceryItemResponse): StorageLocation => {
    const itemNameLower = item.item_name.toLowerCase()

    // Frozen items: ice cream, frozen vegetables, etc.
    if (itemNameLower.includes('frozen') || itemNameLower.includes('ice cream')) {
      return StorageLocation.FREEZER
    }
    if (
      itemNameLower.includes('milk') ||
      itemNameLower.includes('cheese') ||
      itemNameLower.includes('yogurt') ||
      itemNameLower.includes('butter') ||
      itemNameLower.includes('egg') ||
      itemNameLower.includes('meat') ||
      itemNameLower.includes('chicken') ||
      itemNameLower.includes('fish') ||
      itemNameLower.includes('produce')
    ) {
      return StorageLocation.FRIDGE
    }
    if (
      itemNameLower.includes('banana') ||
      itemNameLower.includes('apple') ||
      itemNameLower.includes('orange') ||
      itemNameLower.includes('tomato') ||
      itemNameLower.includes('avocado')
    ) {
      return StorageLocation.COUNTER
    }

    // Default to pantry for everything else
    return StorageLocation.PANTRY
  }

  /**
   * Infers category from item name since grocery items don't have category metadata.
   * Uses keyword matching to guess the most appropriate category.
   * Defaults to OTHER if no keywords match.
   */
  const getCategoryDefault = (item: GroceryItemResponse): Category => {
    const itemNameLower = item.item_name.toLowerCase()

    if (
      itemNameLower.includes('banana') ||
      itemNameLower.includes('apple') ||
      itemNameLower.includes('lettuce') ||
      itemNameLower.includes('tomato') ||
      itemNameLower.includes('onion')
    ) {
      return Category.PRODUCE
    }
    if (
      itemNameLower.includes('milk') ||
      itemNameLower.includes('cheese') ||
      itemNameLower.includes('yogurt') ||
      itemNameLower.includes('butter')
    ) {
      return Category.DAIRY
    }
    if (
      itemNameLower.includes('chicken') ||
      itemNameLower.includes('beef') ||
      itemNameLower.includes('pork') ||
      itemNameLower.includes('fish') ||
      itemNameLower.includes('meat')
    ) {
      return Category.PROTEIN
    }
    if (
      itemNameLower.includes('rice') ||
      itemNameLower.includes('pasta') ||
      itemNameLower.includes('bread') ||
      itemNameLower.includes('flour')
    ) {
      return Category.GRAINS
    }
    if (
      itemNameLower.includes('sauce') ||
      itemNameLower.includes('ketchup') ||
      itemNameLower.includes('mayo') ||
      itemNameLower.includes('mustard')
    ) {
      return Category.CONDIMENTS
    }
    if (itemNameLower.includes('chips') || itemNameLower.includes('cookie')) {
      return Category.SNACKS
    }
    if (
      itemNameLower.includes('juice') ||
      itemNameLower.includes('soda') ||
      itemNameLower.includes('water') ||
      itemNameLower.includes('coffee') ||
      itemNameLower.includes('tea')
    ) {
      return Category.BEVERAGES
    }
    if (itemNameLower.includes('frozen')) {
      return Category.FROZEN
    }
    if (itemNameLower.includes('can') || itemNameLower.includes('canned')) {
      return Category.CANNED
    }
    if (
      itemNameLower.includes('sugar') ||
      itemNameLower.includes('flour') ||
      itemNameLower.includes('baking')
    ) {
      return Category.BAKING
    }
    if (
      itemNameLower.includes('salt') ||
      itemNameLower.includes('pepper') ||
      itemNameLower.includes('spice')
    ) {
      return Category.SPICES
    }

    return Category.OTHER
  }

  // Toggle item selection
  const toggleItem = (item: GroceryItemResponse) => {
    setSelectedItems((prev) => {
      const newMap = new Map(prev)
      if (newMap.has(item.id)) {
        newMap.delete(item.id)
      } else {
        newMap.set(item.id, {
          item,
          storageLocation: getStorageDefault(item),
          category: getCategoryDefault(item),
        })
      }
      return newMap
    })
  }

  // Update storage location for a selected item
  const updateStorageLocation = (itemId: string, newLocation: StorageLocation) => {
    setSelectedItems((prev) => {
      const newMap = new Map(prev)
      const existing = newMap.get(itemId)
      if (existing) {
        newMap.set(itemId, {
          ...existing,
          storageLocation: newLocation,
        })
      }
      return newMap
    })
  }

  // Select all items in a store
  const selectAllInStore = (items: GroceryItemResponse[]) => {
    setSelectedItems((prev) => {
      const newMap = new Map(prev)
      items.forEach((item) => {
        if (!newMap.has(item.id)) {
          newMap.set(item.id, {
            item,
            storageLocation: getStorageDefault(item),
            category: getCategoryDefault(item),
          })
        }
      })
      return newMap
    })
  }

  // Check if all items in a store are selected
  const areAllSelectedInStore = (items: GroceryItemResponse[]): boolean => {
    return items.every((item) => selectedItems.has(item.id))
  }

  // Total count of all grocery items
  const totalItemsCount = useMemo(() => {
    if (!data) return 0
    return data.stores.reduce((sum, store) => sum + store.items.length, 0) + data.unassigned.length
  }, [data])

  if (isLoading) {
    return (
      <div className="py-8 text-center">
        <p className="text-text-secondary">Loading grocery list...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="py-8 text-center">
        <p className="text-terra">Failed to load grocery list. Please try again.</p>
      </div>
    )
  }

  if (!data || (data.stores.length === 0 && data.unassigned.length === 0)) {
    return (
      <div className="py-8 text-center">
        <p className="text-text-secondary">No items on your grocery list.</p>
        <p className="text-sm text-text-tertiary mt-2">
          Add items to your grocery list first, then come back here to check them off.
        </p>
      </div>
    )
  }

  return (
    <div className="pb-32">
      {/* By-store sections */}
      {data.stores.map((store) => (
        <div key={store.store_id} className="mb-6">
          {/* Store header with select all */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              {/* Store initial badge */}
              <div className="w-7 h-7 rounded-md bg-olive flex items-center justify-center">
                <span className="text-xs font-medium text-white">
                  {store.store_name.charAt(0).toUpperCase()}
                </span>
              </div>
              <h3 className="text-sm font-medium text-text-primary">{store.store_name}</h3>
              <span className="text-xs text-text-tertiary">
                ({store.items.length} {store.items.length === 1 ? 'item' : 'items'})
              </span>
            </div>

            {/* Select all button */}
            {!areAllSelectedInStore(store.items) && (
              <button
                onClick={() => selectAllInStore(store.items)}
                className="text-xs text-olive hover:text-olive-dark font-medium"
                type="button"
              >
                Select all
              </button>
            )}
          </div>

          {/* Items */}
          <div className="bg-white rounded-card border border-warm-border divide-y divide-warm-divider">
            {store.items.map((item) => {
              const isSelected = selectedItems.has(item.id)
              const selectedData = selectedItems.get(item.id)

              return (
                <div key={item.id} className="flex items-center gap-3 p-3 min-h-[60px]">
                  {/* Checkbox */}
                  <button
                    onClick={() => toggleItem(item)}
                    className="flex-shrink-0 p-2 -m-2 touch-manipulation"
                    aria-label={
                      isSelected ? `Unselect ${item.item_name}` : `Select ${item.item_name}`
                    }
                    type="button"
                  >
                    <div
                      className={`
                        w-[19px] h-[19px] rounded-[6px] border-2 flex items-center justify-center
                        transition-colors
                        ${
                          isSelected
                            ? 'bg-olive border-olive'
                            : 'bg-white border-warm-border'
                        }
                      `}
                    >
                      {isSelected && (
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
                    <div className="text-[15px] font-medium text-text-primary">
                      {item.item_name}{' '}
                      <span className="font-normal text-text-secondary">
                        ({item.quantity} {item.unit})
                      </span>
                    </div>
                  </div>

                  {/* Storage badge (only shown when selected) */}
                  {isSelected && selectedData && (
                    <div className="flex-shrink-0">
                      <StorageBadge
                        storageLocation={selectedData.storageLocation}
                        onCycle={(newLocation) => updateStorageLocation(item.id, newLocation)}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {/* Unassigned items */}
      {data.unassigned.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-medium text-text-primary">No store assigned</h3>
              <span className="text-xs text-text-tertiary">
                ({data.unassigned.length} {data.unassigned.length === 1 ? 'item' : 'items'})
              </span>
            </div>

            {/* Select all button */}
            {!areAllSelectedInStore(data.unassigned) && (
              <button
                onClick={() => selectAllInStore(data.unassigned)}
                className="text-xs text-olive hover:text-olive-dark font-medium"
                type="button"
              >
                Select all
              </button>
            )}
          </div>

          <div className="bg-white rounded-card border border-warm-border divide-y divide-warm-divider">
            {data.unassigned.map((item) => {
              const isSelected = selectedItems.has(item.id)
              const selectedData = selectedItems.get(item.id)

              return (
                <div key={item.id} className="flex items-center gap-3 p-3 min-h-[60px]">
                  <button
                    onClick={() => toggleItem(item)}
                    className="flex-shrink-0 p-2 -m-2 touch-manipulation"
                    aria-label={
                      isSelected ? `Unselect ${item.item_name}` : `Select ${item.item_name}`
                    }
                    type="button"
                  >
                    <div
                      className={`
                        w-[19px] h-[19px] rounded-[6px] border-2 flex items-center justify-center
                        transition-colors
                        ${
                          isSelected
                            ? 'bg-olive border-olive'
                            : 'bg-white border-warm-border'
                        }
                      `}
                    >
                      {isSelected && (
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

                  <div className="flex-1 min-w-0">
                    <div className="text-[15px] font-medium text-text-primary">
                      {item.item_name}{' '}
                      <span className="font-normal text-text-secondary">
                        ({item.quantity} {item.unit})
                      </span>
                    </div>
                  </div>

                  {isSelected && selectedData && (
                    <div className="flex-shrink-0">
                      <StorageBadge
                        storageLocation={selectedData.storageLocation}
                        onCycle={(newLocation) => updateStorageLocation(item.id, newLocation)}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Purchase summary (fixed at bottom) */}
      {selectedItems.size > 0 && (
        <PurchaseSummary
          selectedItems={selectedItems}
          totalItems={totalItemsCount}
          onSuccess={() => setSelectedItems(new Map())}
        />
      )}
    </div>
  )
}
