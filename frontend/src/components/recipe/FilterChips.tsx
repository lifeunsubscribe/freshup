import { X } from 'lucide-react'

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
          <option value="manual">My recipes</option>
          <option value="hellofresh_card">HelloFresh</option>
          <option value="ad_hoc">Ad-hoc</option>
        </select>

        {/* Cook time filter */}
        <select
          value={filters.max_cook_time || ''}
          onChange={(e) => setFilter('max_cook_time', e.target.value ? Number(e.target.value) : undefined)}
          className="px-3 py-1.5 rounded-full border border-warm-border bg-white text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
        >
          <option value="">Any time</option>
          <option value="15">15 min or less</option>
          <option value="30">30 min or less</option>
          <option value="45">45 min or less</option>
          <option value="60">1 hour or less</option>
        </select>

        {/* Tag filter */}
        <select
          value={filters.tag || ''}
          onChange={(e) => setFilter('tag', e.target.value)}
          className="px-3 py-1.5 rounded-full border border-warm-border bg-white text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
        >
          <option value="">All cuisines</option>
          <option value="italian">Italian</option>
          <option value="mexican">Mexican</option>
          <option value="asian">Asian</option>
          <option value="american">American</option>
          <option value="mediterranean">Mediterranean</option>
          <option value="indian">Indian</option>
          <option value="thai">Thai</option>
          <option value="vegan">Vegan</option>
          <option value="vegetarian">Vegetarian</option>
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
              label={`Cuisine: ${filters.tag}`}
              onRemove={() => removeFilter('tag')}
            />
          )}
          {filters.max_cook_time && (
            <FilterChip
              label={`Max ${filters.max_cook_time} min`}
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

function getSourceTypeLabel(sourceType: string): string {
  switch (sourceType) {
    case 'manual':
      return 'My recipes'
    case 'hellofresh_card':
      return 'HelloFresh'
    case 'ad_hoc':
      return 'Ad-hoc'
    default:
      return sourceType
  }
}
