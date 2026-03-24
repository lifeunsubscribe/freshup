import { useRecipeList, type RecipeListFilters } from '../../api'
import RecipeCard from './RecipeCard'
import FilterChips, { type RecipeFilters } from './FilterChips'
import { ArrowLeft } from 'lucide-react'

interface RecipeGridProps {
  searchQuery: string
  filters: RecipeFilters
  onFilterChange: (filters: RecipeFilters) => void
  onBack: () => void
}

/**
 * RecipeGrid displays recipes in a 2-column grid layout
 *
 * Features:
 * - Back button to return to carousel view
 * - FilterChips for source_type, tag, and cook_time
 * - 2-column responsive grid
 * - RecipeCard components in grid variant
 * - Loading, error, and empty states
 * - Combines search query with filters
 */
export default function RecipeGrid({ searchQuery, filters, onFilterChange, onBack }: RecipeGridProps) {
  // Combine search query and filters for API request
  // Using limit of 100 (backend maximum) to show more results in grid view
  const apiFilters: RecipeListFilters = {
    limit: 100,
    search: searchQuery || undefined,
    source_type: filters.source_type,
    tag: filters.tag,
    max_cook_time: filters.max_cook_time,
  }

  const { data: recipes, isLoading, isError, error } = useRecipeList(apiFilters)

  return (
    <div className="space-y-4">
      {/* Back button */}
      <button
        onClick={onBack}
        className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
        aria-label="Back to browse view"
      >
        <ArrowLeft size={16} />
        Back to browse
      </button>

      {/* Filter chips */}
      <FilterChips filters={filters} onFilterChange={onFilterChange} />

      {/* Results count */}
      {!isLoading && !isError && recipes && (
        <p className="text-sm text-text-secondary" aria-live="polite">
          {recipes.length} {recipes.length === 1 ? 'recipe' : 'recipes'} found
        </p>
      )}

      {/* Grid content */}
      <div>
        {isLoading && (
          <p className="text-sm text-text-secondary">Loading recipes...</p>
        )}

        {isError && (
          <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-800">
            Failed to load recipes.{' '}
            {error instanceof Error ? error.message : 'Please try again.'}
          </div>
        )}

        {!isLoading && !isError && recipes && recipes.length === 0 && (
          <div className="text-center py-12">
            <p className="text-text-secondary mb-2">No recipes found</p>
            <p className="text-sm text-text-tertiary">
              Try adjusting your search or filters
            </p>
          </div>
        )}

        {!isLoading && !isError && recipes && recipes.length > 0 && (
          <div className="grid grid-cols-2 gap-3">
            {recipes.map((recipe) => (
              <RecipeCard
                key={recipe.id}
                recipe={recipe}
                variant="grid"
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
