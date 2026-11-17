import { useState, useCallback } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import PageContainer from '../components/layout/PageContainer'
import PageTitle from '../components/ui/PageTitle'
import SectionHeader from '../components/ui/SectionHeader'
import SearchBar from '../components/recipe/SearchBar'
import ThemeBar, { type ThemeFilter } from '../components/recipe/ThemeBar'
import RecipeCarousel from '../components/recipe/RecipeCarousel'
import RecipeGrid from '../components/recipe/RecipeGrid'
import CollectionRow from '../components/recipe/CollectionRow'
import MixedRow from '../components/recipe/MixedRow'
import MoreCollectionsSheet from '../components/recipe/MoreCollectionsSheet'
import Pill from '../components/ui/Pill'
import { buildPageRows } from '../components/recipe/themeRows'
import { useCollections } from '../api/hooks/useCatalog'
import { useThemes } from '../api/hooks/useThemes'
import { useRecommendations } from '../api/hooks/useRecipes'
import type { RecipeListFilters } from '../api'
import type { RecipeFilters } from '../components/recipe/FilterChips'

/**
 * Recipes page - Primary recipe discovery interface
 *
 * View Modes:
 * - Carousel view (default): whole lists as horizontal carousels
 * - Grid view: 2-column grid with search and filters
 *
 * Carousel view is shaped by the theme bar (Cuisine, Main ingredient, Dish
 * type, Diet, Meal type, Source), held in the URL so back/forward work:
 * - no params:            your rows, then the fullest few lists per theme
 * - ?theme=cuisine:       every list from that theme ("See all")
 * - ?filter=cuisine:thai: your rows containing a Thai recipe, then every Thai list
 * Several filters (one per theme) apply together, also on a theme page.
 * Lists are always shown whole and each names its own source.
 *
 * Also: search icon expands into an inline input (typing switches to grid);
 * "See all" on a row opens the grid filtered to that row.
 */
function parseFilters(raw: string[]): ThemeFilter[] {
  const filters: ThemeFilter[] = []
  for (const entry of raw) {
    const [theme, value] = entry.split(':')
    // One value per theme: a later duplicate theme is ignored
    if (theme && value && !filters.some((f) => f.theme === theme)) filters.push({ theme, value })
  }
  return filters
}

export default function Recipes() {
  const [viewMode, setViewMode] = useState<'carousel' | 'grid'>('carousel')
  const [searchQuery, setSearchQuery] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)
  const [filters, setFilters] = useState<RecipeFilters>({})
  const [showOnlyInStock, setShowOnlyInStock] = useState(false)
  const [showMoreCollections, setShowMoreCollections] = useState(false)
  const [searchParams, setSearchParams] = useSearchParams()

  const themeKey = searchParams.get('theme')
  const themeFilters = parseFilters(searchParams.getAll('filter'))

  const setThemeState = (theme: string | null, filters: ThemeFilter[]) => {
    const next = new URLSearchParams()
    if (theme) next.set('theme', theme)
    filters.forEach((f) => next.append('filter', `${f.theme}:${f.value}`))
    setSearchParams(next)
  }

  // Selecting a value sets that theme's filter, keeping the others; selecting
  // the active value again clears it.
  const toggleFilter = (picked: ThemeFilter) => {
    const others = themeFilters.filter((f) => f.theme !== picked.theme)
    const alreadyActive = themeFilters.some((f) => f.theme === picked.theme && f.value === picked.value)
    setThemeState(themeKey, alreadyActive ? others : [...others, picked])
  }

  // Listing collections seeds the catalog on first use, so wait for it before
  // asking for themes (which only read what is stored).
  const { data: allCollections, isLoading: collectionsLoading } = useCollections('hellofresh_web')
  const { data: themes } = useThemes({ enabled: !collectionsLoading })
  const { rows, heading } = buildPageRows(themes, themeKey, themeFilters)
  const onMainPage = !themeKey && themeFilters.length === 0

  const { data: recommendations } = useRecommendations(20)

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
  const handleSeeAll = useCallback((sectionFilters: RecipeListFilters) => {
    // Extract only RecipeFilters properties (exclude limit which is for carousel only)
    const { max_cook_time, tag, source_type, liked, viewed } = sectionFilters
    const gridFilters: RecipeFilters = {}
    if (max_cook_time !== undefined) gridFilters.max_cook_time = max_cook_time
    if (tag !== undefined) gridFilters.tag = tag
    if (source_type !== undefined) gridFilters.source_type = source_type
    if (liked) gridFilters.liked = true
    if (viewed) gridFilters.viewed = true
    setFilters(gridFilters)
    setViewMode('grid')
  }, [])

  // Handle back button - return to carousel view
  const handleBack = () => {
    setViewMode('carousel')
    setSearchQuery('')
    setSearchOpen(false)
    setFilters({})
  }

  return (
    <PageContainer>
      <div className="py-6 space-y-4">
        {/* Page title + search + Add a recipe entry */}
        <div className="flex items-center justify-between gap-3">
          <PageTitle>Recipes</PageTitle>
          <div className="flex items-center gap-2 min-w-0">
            {searchOpen || searchQuery ? (
              <div className="w-72 max-w-full">
                <SearchBar
                  value={searchQuery}
                  onChange={handleSearchChange}
                  autoFocus
                  onBlur={(value) => {
                    if (!value) setSearchOpen(false)
                  }}
                />
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setSearchOpen(true)}
                className="shrink-0 h-11 w-11 rounded-button border border-warm-border bg-white text-text-secondary hover:text-text-primary inline-flex items-center justify-center transition-colors"
                aria-label="Search recipes"
              >
                <Search size={18} />
              </button>
            )}
            <Link
              to="/recipes/add"
              className="shrink-0 h-11 px-4 rounded-button bg-olive text-white text-[14px] font-medium inline-flex items-center gap-2"
              aria-label="Add a recipe"
            >
              <Plus size={18} />
              Add a recipe
            </Link>
          </div>
        </div>

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
            <ThemeBar
              themes={themes ?? []}
              activeTheme={themeKey}
              activeFilters={themeFilters}
              onSelectValue={toggleFilter}
              onSeeAll={(theme) => setThemeState(theme, themeFilters)}
              onClear={() => setThemeState(null, [])}
            />

            {heading && <SectionHeader subtitle={heading.subtitle}>{heading.title}</SectionHeader>}

            <div className="space-y-6">
              {onMainPage && (
                <MixedRow title="For you" items={recommendations ?? []} />
              )}

              {rows.map((row) =>
                row.kind === 'library' ? (
                  <RecipeCarousel
                    key={row.id}
                    sectionId={row.id}
                    title={row.title}
                    filters={row.filters}
                    subtitle={row.subtitle}
                    showIf={row.showIf}
                    minCount={row.minCount}
                    hideIfWithin={row.hideIfWithin}
                    onSeeAll={() => handleSeeAll(row.filters)}
                  />
                ) : (
                  <CollectionRow key={row.id} collection={row.collection} minCount={row.minCount} />
                )
              )}

              {collectionsLoading && (
                <p className="text-sm text-text-secondary">Loading HelloFresh collections…</p>
              )}

              {/* Everything else in the catalog, themed or not (e.g. Hall of Fame) */}
              {onMainPage && !collectionsLoading && allCollections && allCollections.length > 0 && (
                <button
                  onClick={() => setShowMoreCollections(true)}
                  className="w-full py-3 text-sm text-olive font-medium hover:text-olive/80 transition-colors text-left"
                  aria-label="More HelloFresh collections"
                >
                  More HelloFresh collections…
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
