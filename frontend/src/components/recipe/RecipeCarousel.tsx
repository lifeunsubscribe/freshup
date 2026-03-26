import { useRecipeList, type RecipeListFilters } from '../../api'
import RecipeCard from './RecipeCard'
import SectionHeader from '../ui/SectionHeader'
import { ChevronRight, ChevronLeft } from 'lucide-react'
import { useRef, useState, useEffect } from 'react'

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
 * - Navigation controls (left/right arrow buttons) for accessibility
 * - Last visible card has opacity 0.7 to hint scrollability
 * - Loading and error states
 * - Empty state when no recipes match filters
 * - ARIA attributes for screen reader accessibility (role="region", aria-roledescription="carousel")
 */
export default function RecipeCarousel({ title, filters, onSeeAll, sectionId }: RecipeCarouselProps) {
  const { data: recipes, isLoading, isError, error } = useRecipeList(filters)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)
  const [showControls, setShowControls] = useState(false)

  // Update scroll button states based on scroll position
  const updateScrollButtons = () => {
    const container = scrollContainerRef.current
    if (!container) return

    const { scrollLeft, scrollWidth, clientWidth } = container
    // Enable left button if not at start (scrollLeft > 0)
    setCanScrollLeft(scrollLeft > 0)
    // Enable right button if not at end (using -1 for rounding tolerance)
    setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 1)
    // Only show controls if content overflows (scrollWidth > visible width)
    setShowControls(scrollWidth > clientWidth)
  }

  // Handle scroll navigation
  const scroll = (direction: 'left' | 'right') => {
    const container = scrollContainerRef.current
    if (!container) return

    // Scroll by 80% of visible width for smooth, predictable navigation
    const scrollAmount = container.clientWidth * 0.8
    const newScrollLeft = direction === 'left'
      ? container.scrollLeft - scrollAmount
      : container.scrollLeft + scrollAmount

    container.scrollTo({
      left: newScrollLeft,
      behavior: 'smooth',
    })
  }

  // Set up scroll event listener and initial state
  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return

    // Initialize button states on mount and when recipes change
    updateScrollButtons()

    // Update button states when user scrolls or window resizes
    container.addEventListener('scroll', updateScrollButtons)
    window.addEventListener('resize', updateScrollButtons)

    // Cleanup listeners on unmount
    return () => {
      container.removeEventListener('scroll', updateScrollButtons)
      window.removeEventListener('resize', updateScrollButtons)
    }
  }, [recipes])

  return (
    <section
      id={sectionId}
      className="scroll-mt-24"
      role="region"
      aria-roledescription="carousel"
      aria-label={title}
    >
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
          <div className="relative px-12">
            {/* Left navigation button */}
            {showControls && (
              <button
                onClick={() => scroll('left')}
                disabled={!canScrollLeft}
                className={`absolute -left-1 top-1/2 -translate-y-1/2 z-10 w-11 h-11 flex items-center justify-center rounded-full bg-white shadow-md transition-all ${
                  canScrollLeft
                    ? 'opacity-100 hover:bg-warm-gray cursor-pointer'
                    : 'opacity-40 cursor-not-allowed'
                }`}
                aria-label="Scroll left"
              >
                <ChevronLeft size={20} className="text-text-primary" />
              </button>
            )}

            {/* Carousel container */}
            <div
              ref={scrollContainerRef}
              className="flex gap-[10px] overflow-x-auto pb-2 -mx-4 px-4 scrollbar-hide"
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

            {/* Right navigation button */}
            {showControls && (
              <button
                onClick={() => scroll('right')}
                disabled={!canScrollRight}
                className={`absolute -right-1 top-1/2 -translate-y-1/2 z-10 w-11 h-11 flex items-center justify-center rounded-full bg-white shadow-md transition-all ${
                  canScrollRight
                    ? 'opacity-100 hover:bg-warm-gray cursor-pointer'
                    : 'opacity-40 cursor-not-allowed'
                }`}
                aria-label="Scroll right"
              >
                <ChevronRight size={20} className="text-text-primary" />
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  )
}
