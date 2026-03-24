import { X } from 'lucide-react'
import {
  SOURCE_TYPE_OPTIONS,
  COOK_TIME_OPTIONS,
  TAG_OPTIONS,
  getSourceTypeLabel,
  getCookTimeLabel,
  getTagLabel,
} from '../../constants/recipeFilters'

export interface RecipeFilters {
  source_type?: string
  tag?: string
  max_cook_time?: number
}

interface FilterChipsProps {
  filters: RecipeFilters
  onFilterChange: (filters: RecipeFilters) => void
}

/**
 * FilterChips component for recipe grid view filtering
 *
 * Features:
 * - Displays active filters as removable chips
 * - Filter dropdowns for source_type, tag, and cook_time
 * - Each chip has X button to remove filter
 * - Filters combine with AND logic
 */
export default function FilterChips({ filters, onFilterChange }: FilterChipsProps) {
  const removeFilter = (key: keyof RecipeFilters) => {
    const newFilters = { ...filters }
    delete newFilters[key]
    onFilterChange(newFilters)
  }

  const setFilter = (key: keyof RecipeFilters, value: string | number | undefined) => {
    if (value === undefined || value === '') {
      removeFilter(key)
    } else {
      onFilterChange({ ...filters, [key]: value })
    }
  }

  return (
    <div className="space-y-3">
      {/* Filter dropdowns */}
      <div className="flex flex-wrap gap-2">
        {/* Source type filter */}
        <select
          value={filters.source_type || ''}
          onChange={(e) => setFilter('source_type', e.target.value)}
          className="px-3 py-1.5 rounded-full border border-warm-border bg-white text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
        >
          <option value="">All sources</option>
          {SOURCE_TYPE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        {/* Cook time filter */}
        <select
          value={filters.max_cook_time || ''}
          onChange={(e) => setFilter('max_cook_time', e.target.value ? Number(e.target.value) : undefined)}
          className="px-3 py-1.5 rounded-full border border-warm-border bg-white text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
        >
          <option value="">Any time</option>
          {COOK_TIME_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        {/* Tag filter */}
        <select
          value={filters.tag || ''}
          onChange={(e) => setFilter('tag', e.target.value)}
          className="px-3 py-1.5 rounded-full border border-warm-border bg-white text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
        >
          <option value="">All cuisines</option>
          {TAG_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {/* Active filter chips */}
      {(filters.source_type || filters.tag || filters.max_cook_time) && (
        <div className="flex flex-wrap gap-2">
          {filters.source_type && (
            <FilterChip
              label={`Source: ${getSourceTypeLabel(filters.source_type)}`}
              onRemove={() => removeFilter('source_type')}
            />
          )}
          {filters.tag && (
            <FilterChip
              label={`Cuisine: ${getTagLabel(filters.tag)}`}
              onRemove={() => removeFilter('tag')}
            />
          )}
          {filters.max_cook_time && (
            <FilterChip
              label={`Max ${getCookTimeLabel(filters.max_cook_time)}`}
              onRemove={() => removeFilter('max_cook_time')}
            />
          )}
        </div>
      )}
    </div>
  )
}

interface FilterChipProps {
  label: string
  onRemove: () => void
}

function FilterChip({ label, onRemove }: FilterChipProps) {
  return (
    <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-olive/10 text-xs text-olive border border-olive/20">
      <span>{label}</span>
      <button
        onClick={onRemove}
        className="hover:bg-olive/20 rounded-full p-0.5 transition-colors"
        aria-label={`Remove ${label} filter`}
      >
        <X size={12} />
      </button>
    </div>
  )
}

