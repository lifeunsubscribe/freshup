import { useState, useRef, useEffect, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import PageContainer from '../components/layout/PageContainer'
import CatalogCard from '../components/recipe/CatalogCard'
import CollectionTail, { type TailState } from '../components/recipe/CollectionTail'
import FilterChips, { type RecipeFilters } from '../components/recipe/FilterChips'
import { useCollection } from '../api/hooks/useCatalog'
import type { CardResponse, CollectionSummary } from '../api/types'

// ── filter helper ─────────────────────────────────────────────────────────────

function applyFilters(cards: CardResponse[], filters: RecipeFilters): CardResponse[] {
  return cards.filter((card) => {
    if (filters.saved_only && !card.is_persisted) return false
    if (filters.under_30_min) {
      if (card.prep_time_minutes === null || card.prep_time_minutes > 30) return false
    }
    return true
  })
}

// ── ChildSection ──────────────────────────────────────────────────────────────
// Loads one child collection's cards; calls onSettled/onFailed exactly once.

interface ChildSectionProps {
  child: CollectionSummary
  source: string
  enabled: boolean
  index: number
  filters: RecipeFilters
  onSettled: (index: number, cardCount: number) => void
  onFailed: () => void
}

function ChildSection({ child, source, enabled, index, filters, onSettled, onFailed }: ChildSectionProps) {
  const { data, isLoading, isFetching, isError, error } = useCollection(source, child.slug, { enabled })
  // Guard: only call onSettled/onFailed once per mount.
  const reportedRef = useRef(false)

  useEffect(() => {
    if (!enabled || reportedRef.current) return
    if (isLoading || isFetching) return

    // HTTP error (including 429) → stop the walk
    if (isError) {
      reportedRef.current = true
      onFailed()
      return
    }

    if (data) {
      // fetch_error with no cards means the backend couldn't retrieve new cards
      if (data.fetch_error && data.cards.length === 0) {
        reportedRef.current = true
        onFailed()
      } else {
        reportedRef.current = true
        onSettled(index, data.cards.length)
      }
    }
  }, [enabled, isLoading, isFetching, isError, data, index, onSettled, onFailed])

  if (!enabled) return null

  const cards = data?.cards ?? []
  const filteredCards = applyFilters(cards, filters)

  return (
    <section aria-label={child.name}>
      <h3 className="text-[13px] font-medium text-text-secondary mt-6 mb-2">
        {child.name}
        <span className="text-olive">.</span>
      </h3>

      {(isLoading || isFetching) && (
        <div className="grid grid-cols-2 gap-3">
          <div className="h-40 rounded-[10px] bg-warm-gray/40 animate-pulse" aria-hidden="true" />
          <div className="h-40 rounded-[10px] bg-warm-gray/40 animate-pulse" aria-hidden="true" />
        </div>
      )}

      {!isLoading && !isFetching && filteredCards.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {filteredCards.map((card) => (
            <CatalogCard
              key={card.id}
              card={card}
              collectionSlug={child.slug}
              isNew={true}
            />
          ))}
        </div>
      )}
    </section>
  )
}

// ── Collection page ───────────────────────────────────────────────────────────

export default function Collection() {
  const { slug } = useParams<{ slug: string }>()

  const { data: parent, isLoading, isError, error } = useCollection('hellofresh_web', slug ?? '', {
    enabled: !!slug,
  })

  const [filters, setFilters] = useState<RecipeFilters>({})

  // Walk state: cursor = index of the child currently being fetched (-1 = not started).
  const [cursor, setCursor] = useState(-1)
  const [settledSet, setSettledSet] = useState<Set<number>>(() => new Set())
  const [failed, setFailed] = useState(false)
  const [lastArrivedCount, setLastArrivedCount] = useState(0)
  const [totalChildCards, setTotalChildCards] = useState(0)

  const children: CollectionSummary[] = parent?.children ?? []

  const handleSettled = useCallback((idx: number, count: number) => {
    setSettledSet((prev) => { const s = new Set(prev); s.add(idx); return s })
    setLastArrivedCount(count)
    setTotalChildCards((prev) => prev + count)
  }, [])

  const handleFailed = useCallback(() => {
    setFailed(true)
  }, [])

  // Refs so the observer callback reads current values without re-subscribing on every render.
  const cursorRef = useRef(cursor)
  const settledRef = useRef(settledSet)
  const failedRef = useRef(failed)
  const childrenLenRef = useRef(children.length)
  cursorRef.current = cursor
  settledRef.current = settledSet
  failedRef.current = failed
  childrenLenRef.current = children.length

  // Sentinel: 200px above page bottom. Fires to advance the cursor.
  const sentinelRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting || failedRef.current) return
        const cur = cursorRef.current
        const set = settledRef.current
        const len = childrenLenRef.current
        if (cur === -1) {
          setCursor(0)
        } else if (set.has(cur) && cur + 1 < len) {
          setCursor((c) => c + 1)
        }
      },
      { rootMargin: '200px' }
    )
    observer.observe(el)
    return () => observer.disconnect()
    // Re-subscribe when children load, failed changes, or a child settles (sentinel may still
    // be in viewport — a new observer fires immediately so the walk can advance).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [!!parent, failed, settledSet.size])

  // ── derived display values ───────────────────────────────────────────────────

  const parentCards = parent?.cards ?? []
  const totalCards = parentCards.length + totalChildCards
  const filteredParentCards = applyFilters(parentCards, filters)

  const tailState: TailState | null = (() => {
    if (failed) return 'could-not-bring-in-more'
    if (children.length === 0 && parent) return 'caught-up'
    if (cursor === -1) return null
    if (!settledSet.has(cursor)) return 'bringing-in-more'
    if (cursor === children.length - 1) return 'caught-up'
    return 'more-arrived'
  })()

  // ── loading / error / 404 states ─────────────────────────────────────────────

  if (isLoading) {
    return (
      <PageContainer>
        <div className="pt-6">
          <div className="h-6 w-32 bg-warm-gray/40 rounded animate-pulse mb-2" />
          <div className="h-4 w-20 bg-warm-gray/40 rounded animate-pulse mb-6" />
          <div className="grid grid-cols-2 gap-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-40 rounded-[10px] bg-warm-gray/40 animate-pulse" />
            ))}
          </div>
        </div>
      </PageContainer>
    )
  }

  const is404 = isError && (error as { status?: number })?.status === 404

  if (isError && !is404) {
    return (
      <PageContainer>
        <div className="py-8 text-center">
          <p className="text-mocha mb-2">Could not load this collection right now.</p>
          <Link to="/recipes" className="text-sm text-olive hover:text-olive/80 underline">
            Back to recipes
          </Link>
        </div>
      </PageContainer>
    )
  }

  if (is404 || (!isLoading && !parent)) {
    return (
      <PageContainer>
        <div className="py-8 text-center">
          <p className="text-text-secondary mb-2">Recipe collection not found.</p>
          <Link
            to="/recipes"
            className="text-sm text-olive hover:text-olive/80 underline"
          >
            Back to recipes
          </Link>
        </div>
      </PageContainer>
    )
  }

  const showJustArrived = tailState === 'more-arrived' && lastArrivedCount > 0
  const subtitle = showJustArrived
    ? `${totalCards} recipes · ${lastArrivedCount} just arrived`
    : `${totalCards} recipes`

  return (
    <PageContainer>
      <div className="pt-6 space-y-4">
        {/* Back control */}
        <Link
          to="/recipes"
          className="flex items-center gap-2 text-sm text-text-secondary hover:text-text-primary transition-colors"
          aria-label="Back to recipes"
        >
          <ArrowLeft size={16} />
          Back to recipes
        </Link>

        {/* Header */}
        <div>
          <h1 className="text-xl font-medium text-text-primary">
            {parent!.name}
            <span className="text-olive">.</span>
          </h1>
          <p className="text-sm text-text-secondary mt-0.5" aria-live="polite">{subtitle}</p>
        </div>

        {/* Filter chips */}
        <FilterChips filters={filters} onFilterChange={setFilters} enableBooleanChips={true} />

        {/* Parent cards grid */}
        {filteredParentCards.length > 0 ? (
          <div className="grid grid-cols-2 gap-3">
            {filteredParentCards.map((card) => (
              <CatalogCard
                key={card.id}
                card={card}
                collectionSlug={slug!}
              />
            ))}
          </div>
        ) : parentCards.length > 0 ? (
          <p className="text-sm text-text-secondary">No cards match the current filters.</p>
        ) : null}

        {/* Child sections (lazy-walked) */}
        {children.map((child, i) => (
          <ChildSection
            key={child.slug}
            child={child}
            source="hellofresh_web"
            enabled={i < cursor || (i === cursor && !failed)}
            index={i}
            filters={filters}
            onSettled={handleSettled}
            onFailed={handleFailed}
          />
        ))}

        {/* Tail state */}
        {tailState && (
          <CollectionTail state={tailState} newCount={lastArrivedCount} />
        )}

        {/* Sentinel that the IntersectionObserver watches */}
        <div ref={sentinelRef} aria-hidden="true" style={{ height: 1 }} />
      </div>
    </PageContainer>
  )
}
