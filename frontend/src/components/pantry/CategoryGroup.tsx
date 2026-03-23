import { useState } from 'react'
import InventoryRow from '../inventory/InventoryRow'
import type { InventoryItemListResponse } from '../../api/types'

interface CategoryGroupProps {
  category: string
  items: InventoryItemListResponse[]
}

/**
 * CategoryGroup component for collapsible inventory sections by category
 *
 * Features:
 * - Collapsed state: shows category name and item count
 * - Expanded state: shows InventoryRow for each item
 * - Chevron icon rotates on expand/collapse
 * - Click header to toggle collapse state
 */
export default function CategoryGroup({ category, items }: CategoryGroupProps) {
  const [isExpanded, setIsExpanded] = useState(true)

  // Format category name: capitalize first letter, replace underscores with spaces
  const formatCategoryName = (cat: string): string => {
    return cat
      .split('_')
      .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }

  return (
    <div className="bg-cream-dark rounded-card border border-warm-border mb-4">
      {/* Header: clickable to expand/collapse */}
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-cream transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-text-primary">
            {formatCategoryName(category)}
          </span>
          <span className="text-xs text-text-secondary">
            ({items.length} {items.length === 1 ? 'item' : 'items'})
          </span>
        </div>

        {/* Chevron icon */}
        <svg
          className={`w-5 h-5 text-text-secondary transition-transform duration-200 ${
            isExpanded ? 'rotate-180' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {/* Expanded content: InventoryRow list */}
      {isExpanded && (
        <div className="px-6 pb-4 space-y-1 border-t border-warm-border pt-3">
          {items.map((item) => (
            <InventoryRow key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}
