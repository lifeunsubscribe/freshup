import { useState, useCallback } from 'react'
import PageContainer from '../components/layout/PageContainer'
import PageTitle from '../components/ui/PageTitle'
import SearchBar from '../components/recipe/SearchBar'
import SectionNav from '../components/recipe/SectionNav'
import RecipeCarousel from '../components/recipe/RecipeCarousel'
import RecipeGrid from '../components/recipe/RecipeGrid'
import type { RecipeFilters } from '../components/recipe/FilterChips'

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
export default function Recipes() {
  const [viewMode, setViewMode] = useState<'carousel' | 'grid'>('carousel')
  const [searchQuery, setSearchQuery] = useState('')
  const [filters, setFilters] = useState<RecipeFilters>({})

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
  const handleSeeAll = useCallback((sectionFilters: { limit?: number; max_cook_time?: number; tag?: string }) => {
    // Extract only RecipeFilters properties (exclude limit which is for carousel only)
    const { max_cook_time, tag } = sectionFilters
    const gridFilters: RecipeFilters = {}
    if (max_cook_time !== undefined) gridFilters.max_cook_time = max_cook_time
    if (tag !== undefined) gridFilters.tag = tag
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
        {/* Page title */}
        <PageTitle>Recipes</PageTitle>

        {/* Search bar */}
        <SearchBar value={searchQuery} onChange={handleSearchChange} />

        {/* Carousel view */}
        {viewMode === 'carousel' && (
          <>
            {/* Section navigation */}
            <SectionNav
              sections={sections.map((s) => ({ id: s.id, label: s.label }))}
            />

            {/* Carousels */}
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
