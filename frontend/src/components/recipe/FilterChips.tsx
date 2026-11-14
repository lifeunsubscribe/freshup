import { X } from 'lucide-react'
import {
  SOURCE_TYPE_OPTIONS,
  TAG_OPTIONS,
  getSourceTypeLabel,
  getTagLabel,
} from '../../constants/recipeFilters'

export interface RecipeFilters {
  source_type?: string
  tag?: string
  /** Maximum time in minutes; set by the time slider. */
  max_cook_time?: number
  /** Only the current user's liked recipes — set by "See all" on Your favorites. */
  liked?: boolean
  saved_only?: boolean
  /** Catalog card tag keys that must all be present (in-list tag filter). */
  card_tags?: string[]
  /** Catalog card tag keys that must all be absent ("no Chicken"). */
  card_tags_excluded?: string[]
}

/** Bounds for the time slider, in minutes. */
export interface TimeRange {
  min: number
  max: number
}

const DEFAULT_TIME_RANGE: TimeRange = { min: 10, max: 90 }
const TIME_STEP = 5
/** Where the slider lands when the time filter is first switched on. */
const DEFAULT_MAX_TIME = 30

interface FilterChipsProps {
  filters: RecipeFilters
  onFilterChange: (filters: RecipeFilters) => void
  /** Show the "Saved only" chip. */
  enableBooleanChips?: boolean
  /**
   * Show the source / cuisine dropdowns. Turn off where they cannot apply:
   * a single-source list, or catalog cards, which carry no source or tags.
   */
  showSource?: boolean
  showCuisine?: boolean
  /** Slider bounds; pass the list's own min/max times when known. Null hides the time filter. */
  timeRange?: TimeRange | null
}

/**
 * FilterChips component for recipe grid view filtering
 *
 * Features:
 * - "Saved only" chip (optional)
 * - One time control: a "Max time" toggle that reveals a slider
 * - Source and cuisine dropdowns where they make sense, with removable chips
 * - Filters combine with AND logic
 */
export default function FilterChips({
  filters,
  onFilterChange,
  enableBooleanChips = false,
  showSource = true,
  showCuisine = true,
  timeRange = DEFAULT_TIME_RANGE,
}: FilterChipsProps) {
  const removeFilter = (key: keyof RecipeFilters) => {
    const newFilters = { ...filters }
    delete newFilters[key]
    onFilterChange(newFilters)
  }

  const setFilter = (key: keyof RecipeFilters, value: string | number | boolean | undefined) => {
    if (value === undefined || value === '') {
      removeFilter(key)
    } else {
      onFilterChange({ ...filters, [key]: value })
    }
  }

  const chipClass = (on: boolean) =>
    `px-3 py-1 rounded-full text-xs border transition-colors ${
      on
        ? 'bg-olive text-cream border-olive'
        : 'bg-white text-text-primary border-warm-border hover:bg-warm-gray/30'
    }`

  const selectClass =
    'px-3 py-1.5 rounded-full border border-warm-border bg-white text-xs text-text-primary focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent'

  const timeOn = filters.max_cook_time !== undefined
  const toggleTime = () => {
    if (timeOn || !timeRange) {
      removeFilter('max_cook_time')
    } else {
      const start = Math.min(Math.max(DEFAULT_MAX_TIME, timeRange.min), timeRange.max)
      setFilter('max_cook_time', start)
    }
  }

  const showDropdowns = showSource || showCuisine

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {enableBooleanChips && (
          <button
            onClick={() => (filters.saved_only ? removeFilter('saved_only') : setFilter('saved_only', true))}
            className={chipClass(!!filters.saved_only)}
            aria-pressed={!!filters.saved_only}
          >
            Saved only
          </button>
        )}

        {timeRange && (
          <>
            <button onClick={toggleTime} className={chipClass(timeOn)} aria-pressed={timeOn}>
              Max time
            </button>
            {timeOn && (
              <label className="inline-flex items-center gap-2 text-xs text-text-primary">
                <input
                  type="range"
                  min={timeRange.min}
                  max={timeRange.max}
                  step={TIME_STEP}
                  value={filters.max_cook_time}
                  onChange={(e) => setFilter('max_cook_time', Number(e.target.value))}
                  aria-label="Maximum time in minutes"
                  className="w-40 accent-olive"
                />
                <span className="tabular-nums w-20">up to {filters.max_cook_time} min</span>
              </label>
            )}
          </>
        )}

        {showSource && (
          <select
            value={filters.source_type || ''}
            onChange={(e) => setFilter('source_type', e.target.value)}
            className={selectClass}
          >
            <option value="">All sources</option>
            {SOURCE_TYPE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}

        {showCuisine && (
          <select
            value={filters.tag || ''}
            onChange={(e) => setFilter('tag', e.target.value)}
            className={selectClass}
          >
            <option value="">All cuisines</option>
            {TAG_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
      </div>

      {/* Active dropdown filters as removable chips */}
      {showDropdowns && ((showSource && filters.source_type) || (showCuisine && filters.tag)) && (
        <div className="flex flex-wrap gap-2">
          {showSource && filters.source_type && (
            <FilterChip
              label={`Source: ${getSourceTypeLabel(filters.source_type)}`}
              onRemove={() => removeFilter('source_type')}
            />
          )}
          {showCuisine && filters.tag && (
            <FilterChip
              label={`Cuisine: ${getTagLabel(filters.tag)}`}
              onRemove={() => removeFilter('tag')}
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
