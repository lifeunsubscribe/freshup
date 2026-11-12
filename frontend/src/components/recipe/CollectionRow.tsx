import { useRef, useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, ChevronLeft } from 'lucide-react'
import SectionHeader from '../ui/SectionHeader'
import CatalogCard from './CatalogCard'
import { useCollection } from '../../api/hooks/useCatalog'
import type { CollectionSummary } from '../../api/types'

interface CollectionRowProps {
  collection: CollectionSummary
}

export default function CollectionRow({ collection }: CollectionRowProps) {
  // inView flips true once the row is within 200px of the viewport and never resets.
  const [inView, setInView] = useState(false)
  const sentinelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = sentinelRef.current
    if (!el || inView) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setInView(true)
          observer.disconnect()
        }
      },
      { rootMargin: '200px' }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [inView])

  // Rows with stored cards skip the network fetch on first paint; empty rows let the
  // default staleness logic decide whether to hit HelloFresh.
  const fresh = collection.card_count > 0 ? false : undefined

  const { data, isLoading, isFetching } = useCollection('hellofresh_web', collection.slug, {
    enabled: inView,
    fresh,
  })

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
  }, [data, inView])

  const subtitle =
    collection.card_count > 0
      ? `${collection.card_count} recipe${collection.card_count === 1 ? '' : 's'}`
      : inView && !isLoading && !isFetching && data
        ? `${data.cards.length} recipe${data.cards.length === 1 ? '' : 's'}`
        : 'Not loaded yet'

  const cards = data?.cards.slice(0, 10) ?? []
  const fetchError = data?.fetch_error ?? null
  const isLoadingRow = inView && (isLoading || isFetching)
  const browseUrl = `/browse/hellofresh/${collection.slug}`

  return (
    <section
      id={`hellofresh-${collection.slug}`}
      className="scroll-mt-24"
      role="region"
      aria-label={collection.name}
    >
      {/* Sentinel element the IntersectionObserver watches */}
      <div ref={sentinelRef} aria-hidden="true" />

      <div className="flex items-center justify-between mb-3">
        <SectionHeader subtitle={subtitle}>{collection.name}</SectionHeader>
        <Link
          to={browseUrl}
          className="flex items-center gap-1 text-sm text-olive hover:text-olive/80 transition-colors font-medium"
          aria-label={`See all ${collection.name}`}
        >
          See all
          <ChevronRight size={16} />
        </Link>
      </div>

      {/* Not yet triggered — reserve height so nav doesn't jump */}
      {!inView && (
        <div className="h-48 rounded-card bg-warm-gray/30" aria-hidden="true" />
      )}

      {/* Loading skeleton */}
      {inView && isLoadingRow && cards.length === 0 && (
        <p className="text-sm text-text-secondary">Loading…</p>
      )}

      {/* Cards */}
      {inView && cards.length > 0 && (
        <div className="relative px-12">
          {showControls && (
            <button
              onClick={() => scroll('left')}
              disabled={!canScrollLeft}
              className={`absolute -left-1 top-1/2 -translate-y-1/2 z-10 w-11 h-11 flex items-center justify-center rounded-full bg-white shadow-md transition-all ${
                canScrollLeft ? 'opacity-100 hover:bg-warm-gray cursor-pointer' : 'opacity-40 cursor-not-allowed'
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
            aria-label={`${collection.name} carousel`}
          >
            {cards.map((card) => (
              <div key={card.id} role="listitem" className="flex-shrink-0 w-[160px]">
                <CatalogCard card={card} collectionSlug={collection.slug} />
              </div>
            ))}
          </div>

          {showControls && (
            <button
              onClick={() => scroll('right')}
              disabled={!canScrollRight}
              className={`absolute -right-1 top-1/2 -translate-y-1/2 z-10 w-11 h-11 flex items-center justify-center rounded-full bg-white shadow-md transition-all ${
                canScrollRight ? 'opacity-100 hover:bg-warm-gray cursor-pointer' : 'opacity-40 cursor-not-allowed'
              }`}
              aria-label="Scroll right"
            >
              <ChevronRight size={20} className="text-text-primary" />
            </button>
          )}

          {/* fetch_error with stored cards: show cards (above) plus error note */}
          {fetchError && (
            <p className="text-xs text-mocha mt-2">Could not bring in more right now.</p>
          )}
        </div>
      )}

      {/* fetch_error with no stored cards */}
      {inView && !isLoadingRow && cards.length === 0 && fetchError && (
        <p className="text-xs text-mocha">Could not bring in more right now.</p>
      )}

      {/* Empty — no error, no cards */}
      {inView && !isLoadingRow && cards.length === 0 && !fetchError && data && (
        <p className="text-sm text-text-secondary">Nothing here yet.</p>
      )}
    </section>
  )
}
