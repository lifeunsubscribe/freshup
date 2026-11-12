import { useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Plus } from 'lucide-react'
import PageContainer from '../components/layout/PageContainer'
import PageTitle from '../components/ui/PageTitle'
import SearchBar from '../components/recipe/SearchBar'
import SectionNav from '../components/recipe/SectionNav'
import RecipeCarousel from '../components/recipe/RecipeCarousel'
import RecipeGrid from '../components/recipe/RecipeGrid'
import CollectionRow from '../components/recipe/CollectionRow'
import MoreCollectionsSheet from '../components/recipe/MoreCollectionsSheet'
import SectionHeader from '../components/ui/SectionHeader'
import Pill from '../components/ui/Pill'
import { useCollections } from '../api/hooks/useCatalog'
import type { RecipeFilters } from '../components/recipe/FilterChips'
import type { CollectionSummary } from '../api/types'

/**
 * Recipes page - Primary recipe discovery interface
 *
 * View Modes:
 * - Carousel view (default): Multiple horizontal carousels by category
 * - Grid view: 2-column grid with search and filters
 *
 * Features:
 * - Search bar transitions to grid view on input
 * - Sticky section navigation in carousel view
 * - "See all" links transition to filtered grid view
 * - Back button returns to carousel view
 * - Recipe cards navigate to /recipes/:id
 */
function sortCollections(collections: CollectionSummary[]): CollectionSummary[] {
  const withCards = collections.filter((c) => c.card_count > 0).sort((a, b) => b.card_count - a.card_count)
  const withoutCards = collections.filter((c) => c.card_count === 0).sort((a, b) => a.name.localeCompare(b.name))
  return [...withCards, ...withoutCards]
}

export default function Recipes() {
  const [viewMode, setViewMode] = useState<'carousel' | 'grid'>('carousel')
  const [searchQuery, setSearchQuery] = useState('')
  const [filters, setFilters] = useState<RecipeFilters>({})
  const [showOnlyInStock, setShowOnlyInStock] = useState(false)
  const [showMoreCollections, setShowMoreCollections] = useState(false)

  const { data: allCollections, isLoading: collectionsLoading } = useCollections('hellofresh_web')
  const sortedCollections = allCollections ? sortCollections(allCollections) : []
  const displayedCollections = sortedCollections.slice(0, 6)

  // Define carousel sections
  const sections = [
    { id: 'favorites', label: 'Your favorites', filters: { limit: 10 } },
    { id: 'quick-meals', label: 'Quick meals', filters: { limit: 10, max_cook_time: 30 } },
    { id: 'recently-added', label: 'Recently added', filters: { limit: 10 } },
    { id: 'italian', label: 'Italian', filters: { limit: 10, tag: 'italian' } },
    { id: 'mexican', label: 'Mexican', filters: { limit: 10, tag: 'mexican' } },
    { id: 'asian', label: 'Asian', filters: { limit: 10, tag: 'asian' } },
    { id: 'vegan', label: 'Vegan', filters: { limit: 10, tag: 'vegan' } },
  ]

  // Handle search input - transition to grid view when typing
  const handleSearchChange = useCallback((value: string) => {
    setSearchQuery(value)
    if (value) {
      setViewMode('grid')
    } else if (!Object.keys(filters).length) {
      // Return to carousel if search is cleared and no filters active
      setViewMode('carousel')
    }
  }, [filters])

  // Handle "See all" button - transition to grid with filter
  const handleSeeAll = useCallback((sectionFilters: { limit?: number; max_cook_time?: number; tag?: string; source_type?: string }) => {
    // Extract only RecipeFilters properties (exclude limit which is for carousel only)
    const { max_cook_time, tag, source_type } = sectionFilters
    const gridFilters: RecipeFilters = {}
    if (max_cook_time !== undefined) gridFilters.max_cook_time = max_cook_time
    if (tag !== undefined) gridFilters.tag = tag
    if (source_type !== undefined) gridFilters.source_type = source_type
    setFilters(gridFilters)
    setViewMode('grid')
  }, [])

  // Handle back button - return to carousel view
  const handleBack = () => {
    setViewMode('carousel')
    setSearchQuery('')
    setFilters({})
  }

  return (
    <PageContainer>
      <div className="py-6 space-y-4">
        {/* Page title + Add a recipe entry */}
        <div className="flex items-center justify-between gap-3">
          <PageTitle>Recipes</PageTitle>
          <Link
            to="/recipes/add"
            className="shrink-0 h-11 px-4 rounded-button bg-olive text-white text-[14px] font-medium inline-flex items-center gap-2"
            aria-label="Add a recipe"
          >
            <Plus size={18} />
            Add a recipe
          </Link>
        </div>

        {/* Search bar */}
        <SearchBar value={searchQuery} onChange={handleSearchChange} />

        {/* "Show what I can make now" toggle (Phase 1: Display only, non-functional) */}
        <div className="flex items-center gap-3 mb-4">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showOnlyInStock}
              onChange={(e) => setShowOnlyInStock(e.target.checked)}
              disabled
              className="w-5 h-5 rounded border-warm-border text-olive focus:ring-olive focus:ring-offset-0 disabled:opacity-50 disabled:cursor-not-allowed"
            />
            <span className="text-sm text-text-primary">Show what I can make now</span>
          </label>
          <Pill variant="default">
            <span className="text-xs">Phase 3</span>
          </Pill>
        </div>

        {/* Carousel view */}
        {viewMode === 'carousel' && (
          <>
            {/* Section navigation — library sections + HelloFresh collection rows */}
            <SectionNav
              sections={[
                ...sections.map((s) => ({ id: s.id, label: s.label })),
                { id: 'kitchen-sanctuary', label: 'Kitchen Sanctuary' },
                ...displayedCollections.map((c) => ({
                  id: `hellofresh-${c.slug}`,
                  label: c.name,
                })),
              ]}
            />

            {/* Library carousels */}
            <div className="space-y-6">
              {sections.map((section) => (
                <RecipeCarousel
                  key={section.id}
                  title={section.label}
                  filters={section.filters}
                  onSeeAll={() => handleSeeAll(section.filters)}
                  sectionId={section.id}
                />
              ))}
            </div>

            {/* Kitchen Sanctuary section — grows only by hand via saved-page import */}
            <div className="mt-6">
              <RecipeCarousel
                title="Kitchen Sanctuary"
                sectionId="kitchen-sanctuary"
                filters={{ source_type: 'kitchen_sanctuary', limit: 10 }}
                onSeeAll={() => handleSeeAll({ source_type: 'kitchen_sanctuary', limit: 10 })}
                subtitle={(n) => `${n ?? 0} recipes · added by hand`}
                emptyState={null}
                footer={
                  <p className="mt-3 text-sm text-text-secondary">
                    Kitchen Sanctuary turns automated fetching away, so this row grows only when someone adds a recipe.{' '}
                    <Link
                      to="/recipes/add?source=kitchen_sanctuary"
                      className="text-olive hover:text-olive/80 transition-colors"
                    >
                      Add a specific recipe
                    </Link>
                  </p>
                }
              />
            </div>

            {/* HelloFresh section */}
            <div className="space-y-6 mt-6">
              {/* Section header "From HelloFresh." */}
              <SectionHeader>From HelloFresh</SectionHeader>

              {/* Skeleton while list is loading (cold start) */}
              {collectionsLoading && (
                <p className="text-sm text-text-secondary">Loading collections…</p>
              )}

              {displayedCollections.map((collection) => (
                <CollectionRow key={collection.slug} collection={collection} />
              ))}

              {/* "More collections" button — only when there are collections */}
              {!collectionsLoading && allCollections && allCollections.length > 0 && (
                <button
                  onClick={() => setShowMoreCollections(true)}
                  className="w-full py-3 text-sm text-olive font-medium hover:text-olive/80 transition-colors text-left"
                  aria-label="More collections"
                >
                  More collections…
                </button>
              )}
            </div>

            <MoreCollectionsSheet
              open={showMoreCollections}
              onClose={() => setShowMoreCollections(false)}
              collections={allCollections ?? []}
            />
          </>
        )}

        {/* Grid view */}
        {viewMode === 'grid' && (
          <RecipeGrid
            searchQuery={searchQuery}
            filters={filters}
            onFilterChange={setFilters}
            onBack={handleBack}
          />
        )}
      </div>
    </PageContainer>
  )
}
