import { useRecipeList, type RecipeListFilters } from '../../api'
import RecipeCard from './RecipeCard'
import SectionHeader from '../ui/SectionHeader'
import { ChevronRight } from 'lucide-react'

interface RecipeCarouselProps {
  title: string
  filters: RecipeListFilters
  onSeeAll: () => void
  sectionId?: string
}

/**
 * RecipeCarousel displays a horizontal scrollable row of recipe cards
 *
 * Features:
 * - Section header with olive period
 * - "See all →" link on right
 * - Horizontal scroll of RecipeCard components in carousel variant
 * - Last visible card has opacity 0.7 to hint scrollability
 * - Loading and error states
 * - Empty state when no recipes match filters
 */
export default function RecipeCarousel({ title, filters, onSeeAll, sectionId }: RecipeCarouselProps) {
  const { data: recipes, isLoading, isError, error } = useRecipeList(filters)

  return (
    <section id={sectionId} className="scroll-mt-24">
      {/* Header with title and "See all" link */}
      <div className="flex items-center justify-between mb-3">
        <SectionHeader>{title}</SectionHeader>
        <button
          onClick={onSeeAll}
          className="flex items-center gap-1 text-sm text-olive hover:text-olive/80 transition-colors font-medium"
          aria-label={`See all ${title.toLowerCase()}`}
        >
          See all
          <ChevronRight size={16} />
        </button>
      </div>

      {/* Content */}
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
          <p className="text-sm text-text-secondary">
            No recipes found for this category.
          </p>
        )}

        {!isLoading && !isError && recipes && recipes.length > 0 && (
          <div
            className="flex gap-3 overflow-x-auto pb-2 -mx-4 px-4 scrollbar-hide"
            role="list"
            aria-label={`${title} carousel`}
          >
            {recipes.map((recipe, index) => (
              <RecipeCard
                key={recipe.id}
                recipe={recipe}
                variant="carousel"
                isLastVisible={index === recipes.length - 1}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
