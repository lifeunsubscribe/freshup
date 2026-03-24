import { usePreparedFoodList } from '../../api'
import type { PreparedFoodListResponse } from '../../api/types'
import SectionHeader from '../ui/SectionHeader'
import Pill from '../ui/Pill'
import { formatRelativeDate } from '../../utils/dateUtils'

/**
 * ReadyToEat displays a horizontal carousel of prepared food items
 *
 * Features:
 * - Fetches prepared foods using usePreparedFoodList
 * - Horizontal scrollable carousel of prepared food cards
 * - Each card shows: name, type, servings remaining, date prepared
 * - Empty state: friendly message when no prepared foods
 * - Loading state: simple loading message
 * - Error state: displays error message if fetch fails
 * - ARIA attributes for screen reader accessibility (role="region", aria-roledescription="carousel")
 */
export default function ReadyToEat() {
  const { data: items, isLoading, isError, error } = usePreparedFoodList()

  return (
    <section
      role="region"
      aria-roledescription="carousel"
      aria-label="Ready to Eat"
    >
      <SectionHeader>Ready to Eat</SectionHeader>

      <div className="mt-3">
        {isLoading && (
          <p className="text-sm text-text-secondary">Loading prepared foods...</p>
        )}

        {isError && (
          <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-800">
            Failed to load prepared foods.{' '}
            {error instanceof Error ? error.message : 'Please try again.'}
          </div>
        )}

        {!isLoading && !isError && items && items.length === 0 && (
          <p className="text-sm text-text-secondary">
            No prepared foods ready. Cook something delicious!
          </p>
        )}

        {!isLoading && !isError && items && items.length > 0 && (
          <div
            className="flex gap-3 overflow-x-auto pb-2 -mx-4 px-4 scrollbar-hide"
            role="list"
            aria-label="Prepared foods carousel"
          >
            {items.map((item) => (
              <PreparedFoodCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

interface PreparedFoodCardProps {
  item: PreparedFoodListResponse
}

function PreparedFoodCard({ item }: PreparedFoodCardProps) {
  return (
    <div
      className="flex-shrink-0 w-[240px] bg-white rounded-card p-4 border border-warm-border"
      role="listitem"
    >
      <div className="flex items-start justify-between mb-2">
        <h3 className="text-sm font-medium text-text-primary line-clamp-2">
          {item.name}
        </h3>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <Pill variant="default">{item.type}</Pill>
          {item.shareability === 'shared' && (
            <Pill variant="success">shared</Pill>
          )}
          {item.shareability === 'reserved' && (
            <Pill variant="warning">reserved</Pill>
          )}
        </div>

        <div className="text-xs text-text-secondary">
          <p>{item.servings_remaining} {item.servings_remaining === 1 ? 'serving' : 'servings'} left</p>
          <p>Prepared {formatRelativeDate(item.date_prepared)}</p>
        </div>
      </div>
    </div>
  )
}
