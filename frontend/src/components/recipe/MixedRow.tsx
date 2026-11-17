import { useRef, useState, useEffect } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import SectionHeader from '../ui/SectionHeader'
import CatalogCard from './CatalogCard'
import ConnectedRecipeCard from './ConnectedRecipeCard'
import type { RecommendedItem } from '../../api/types'

interface MixedRowProps {
  title: string
  subtitle?: string
  items: RecommendedItem[]
}

/**
 * A horizontally scrollable row that mixes CatalogCards and ConnectedRecipeCards.
 *
 * Used for the "For you" recommendations row on the main Recipes page and for
 * related-recipe rows on detail pages. Renders nothing when items is empty.
 */
export default function MixedRow({ title, subtitle, items }: MixedRowProps) {
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(false)
  const [showControls, setShowControls] = useState(false)

  const updateScrollButtons = () => {
    const container = scrollContainerRef.current
    if (!container) return
    const { scrollLeft, scrollWidth, clientWidth } = container
    setCanScrollLeft(scrollLeft > 0)
    setCanScrollRight(scrollLeft < scrollWidth - clientWidth - 1)
    setShowControls(scrollWidth > clientWidth)
  }

  const scroll = (direction: 'left' | 'right') => {
    const container = scrollContainerRef.current
    if (!container) return
    const amount = container.clientWidth * 0.8
    container.scrollTo({
      left: direction === 'left' ? container.scrollLeft - amount : container.scrollLeft + amount,
      behavior: 'smooth',
    })
  }

  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return
    updateScrollButtons()
    container.addEventListener('scroll', updateScrollButtons)
    window.addEventListener('resize', updateScrollButtons)
    return () => {
      container.removeEventListener('scroll', updateScrollButtons)
      window.removeEventListener('resize', updateScrollButtons)
    }
  }, [items])

  if (items.length === 0) return null

  return (
    <section
      className="scroll-mt-24"
      role="region"
      aria-label={title}
    >
      <div className="flex items-center justify-between mb-3">
        <SectionHeader subtitle={subtitle}>{title}</SectionHeader>
      </div>

      <div className="relative px-12">
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

        <div
          ref={scrollContainerRef}
          className="flex gap-[10px] overflow-x-auto pb-2 -mx-4 px-4 scrollbar-hide"
          role="list"
          aria-label={`${title} row`}
        >
          {items.map((item, index) => (
            <div
              key={item.kind === 'card' ? item.card.id : item.recipe.id}
              role="listitem"
              className="flex-shrink-0 w-[160px]"
            >
              {item.kind === 'card' ? (
                // collectionSlug is used only for cache invalidation after open;
                // recommendations have no specific collection to invalidate.
                <CatalogCard card={item.card} collectionSlug="" />
              ) : (
                <ConnectedRecipeCard
                  recipe={item.recipe}
                  variant="carousel"
                  isLastVisible={index === items.length - 1}
                />
              )}
            </div>
          ))}
        </div>

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
    </section>
  )
}
