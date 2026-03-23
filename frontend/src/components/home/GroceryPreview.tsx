import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { useGroceryList } from '../../api'
import SectionHeader from '../ui/SectionHeader'

/**
 * GroceryPreview displays a summary of unpurchased grocery items
 *
 * Features:
 * - Fetches unpurchased items using useGroceryList with purchased: false filter
 * - Shows count of items on the grocery list
 * - Links to /grocery page for full list
 * - Empty state: friendly message when grocery list is empty
 * - Loading state: simple loading message
 * - Error state: displays error message if fetch fails
 */
export default function GroceryPreview() {
  const { data: items, isLoading, isError, error } = useGroceryList({
    purchased: false,
  })

  const itemCount = items?.length || 0

  return (
    <section>
      <SectionHeader>Grocery List</SectionHeader>

      <div className="mt-3">
        {isLoading && (
          <p className="text-sm text-text-secondary">Loading grocery list...</p>
        )}

        {isError && (
          <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-800">
            Failed to load grocery list.{' '}
            {error instanceof Error ? error.message : 'Please try again.'}
          </div>
        )}

        {!isLoading && !isError && itemCount === 0 && (
          <p className="text-sm text-text-secondary">
            Your grocery list is empty. Add items as you think of them!
          </p>
        )}

        {!isLoading && !isError && itemCount > 0 && (
          <Link
            to="/grocery"
            className="flex items-center justify-between p-4 bg-white rounded-card border border-warm-border hover:bg-[#f4f2ea] transition-colors"
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-olive flex items-center justify-center">
                <span className="text-lg font-semibold text-cream">
                  {itemCount}
                </span>
              </div>
              <div>
                <p className="text-sm font-medium text-text-primary">
                  {itemCount} {itemCount === 1 ? 'item' : 'items'} to buy
                </p>
                <p className="text-xs text-text-secondary">
                  Tap to view your list
                </p>
              </div>
            </div>
            <ChevronRight size={20} className="text-text-tertiary" />
          </Link>
        )}
      </div>
    </section>
  )
}
