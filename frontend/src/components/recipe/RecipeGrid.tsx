import { useState, useEffect } from 'react'
import { useRecipeList, type RecipeListFilters } from '../../api'
import type { RecipeListResponse } from '../../api/types'
import RecipeCard from './RecipeCard'
import FilterChips, { type RecipeFilters } from './FilterChips'
import { ArrowLeft } from 'lucide-react'

interface RecipeGridProps {
  searchQuery: string
  filters: RecipeFilters
  onFilterChange: (filters: RecipeFilters) => void
  onBack: () => void
}

const RECIPES_PER_PAGE = 100

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
 * - Pagination with "Load More" button
 */
export default function RecipeGrid({ searchQuery, filters, onFilterChange, onBack }: RecipeGridProps) {
  const [offset, setOffset] = useState(0)
  const [allRecipes, setAllRecipes] = useState<RecipeListResponse[]>([])
  const [hasMore, setHasMore] = useState(true)

  // Combine search query and filters for API request
  const apiFilters: RecipeListFilters = {
    limit: RECIPES_PER_PAGE,
    offset,
    search: searchQuery || undefined,
    source_type: filters.source_type,
    tag: filters.tag,
    max_cook_time: filters.max_cook_time,
  }

  const { data: recipes, isLoading, isError, error } = useRecipeList(apiFilters)

  // Accumulate recipes and track if there are more to load
  useEffect(() => {
    if (recipes && recipes.length > 0) {
      if (offset === 0) {
        // First load - replace all recipes
        setAllRecipes(recipes)
      } else {
        // Subsequent loads - append new recipes
        setAllRecipes((prev) => [...prev, ...recipes])
      }
      // If we got fewer recipes than requested, there are no more to load
      setHasMore(recipes.length === RECIPES_PER_PAGE)
    } else if (offset === 0 && recipes) {
      // First load returned empty - reset state
      setAllRecipes([])
      setHasMore(false)
    }
  }, [recipes, offset])

  // Reset pagination when search query or filters change
  useEffect(() => {
    setOffset(0)
    setAllRecipes([])
    setHasMore(true)
  }, [searchQuery, filters.source_type, filters.tag, filters.max_cook_time])

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
      {!isLoading && !isError && allRecipes.length > 0 && (
        <p className="text-sm text-text-secondary" aria-live="polite">
          {allRecipes.length} {allRecipes.length === 1 ? 'recipe' : 'recipes'} found
        </p>
      )}

      {/* Grid content */}
      <div>
        {isLoading && offset === 0 && (
          <p className="text-sm text-text-secondary">Loading recipes...</p>
        )}

        {isError && (
          <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-md text-sm text-red-800">
            Failed to load recipes.{' '}
            {error instanceof Error ? error.message : 'Please try again.'}
          </div>
        )}

        {!isLoading && !isError && allRecipes.length === 0 && (
          <div className="text-center py-12">
            <p className="text-text-secondary mb-2">No recipes found</p>
            <p className="text-sm text-text-tertiary">
              Try adjusting your search or filters
            </p>
          </div>
        )}

        {!isLoading && !isError && allRecipes.length > 0 && (
          <div className="grid grid-cols-2 gap-3">
            {allRecipes.map((recipe) => (
              <RecipeCard
                key={recipe.id}
                recipe={recipe}
                variant="grid"
              />
            ))}
          </div>
        )}

        {/* Load More button */}
        {hasMore && !isLoading && allRecipes.length > 0 && (
          <div className="flex justify-center mt-6">
            <button
              onClick={() => setOffset((prev) => prev + RECIPES_PER_PAGE)}
              className="px-6 py-2 bg-white border border-warm-border rounded-md text-sm font-medium text-text-primary hover:bg-gray-50 transition-colors"
            >
              Load More Recipes
            </button>
          </div>
        )}

        {/* Loading indicator for pagination */}
        {isLoading && offset > 0 && (
          <div className="flex justify-center mt-6">
            <p className="text-sm text-text-secondary">Loading more recipes...</p>
          </div>
        )}
      </div>
    </div>
  )
}
