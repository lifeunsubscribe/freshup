/**
 * Recipes page, file 1 of 2: YOUR OWN ROWS, SEARCH AND THE GRID
 *
 * Covers the library side of the page: the user's own rows (favorites,
 * recently added, quick meals), the search button and input, "See all" into
 * the grid, the back button, and switching between carousel and grid views.
 * Themes and the catalog are mocked empty so only those rows render.
 *
 * Not here: anything driven by GET /themes or the catalog (theme bar, theme
 * pages, theme filters, collection rows, More collections sheet, bylines).
 * Those are in Recipes.themes.test.tsx.
 *
 * Both files mock '../api'. A hook that Recipes.tsx starts taking from there
 * has to be added to the mock in both, and a change to Recipes.tsx needs both
 * files run. The split is listed in README.md under "Three things to know
 * when writing frontend tests".
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import Recipes from './Recipes'
import { useRecipeList } from '../api'

// Mock the API hook
vi.mock('../api', () => ({
  useRecipeList: vi.fn(),
}))
// ConnectedRecipeCard (rendered inside) reads engagement state from React Query.
// These tests mock the API layer rather than wrapping in a QueryClientProvider,
// so the engagement hooks are stubbed the same way.
vi.mock('../api/hooks/useRecipeEngagement', () => ({
  useMyRecipeRelations: () => ({ data: new Map() }),
  useToggleBookmark: () => ({ mutate: vi.fn() }),
  useToggleLike: () => ({ mutate: vi.fn() }),
}))
// The "From HelloFresh" section (#545) reads the catalog through React Query.
// An empty, settled list keeps these library-view tests focused on what they
// already assert; the catalog section has its own tests in Recipes.themes.test.tsx.
// Theme lists come from GET /themes; empty here keeps these tests on the
// user's own rows. Theme behaviour is covered in Recipes.themes.test.tsx.
vi.mock('../api/hooks/useThemes', () => ({
  useThemes: () => ({ data: [] }),
}))
vi.mock('../api/hooks/useCatalog', () => ({
  useCollections: () => ({ data: [], isLoading: false, isError: false }),
  useCollection: () => ({ data: undefined, isLoading: false, isError: false }),
  useOpenCard: () => ({ mutate: vi.fn(), isPending: false, isError: false, error: null, reset: vi.fn() }),
}))


// Helper to render component with Router context
const renderWithRouter = (ui: React.ReactElement) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>)
}

/** Search is collapsed behind an icon in the header; click it to reveal the input. */
async function openSearch(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Search recipes' }))
  return screen.getByPlaceholderText('Search recipes...')
}

describe('Recipes Page', () => {
  const mockRecipes = [
    {
      id: 'recipe-1',
      name: 'Pasta Carbonara',
      source_type: 'manual',
      cook_time_minutes: 20,
      prep_time_minutes: 10,
      tags: ['italian'],
      created_at: '2024-01-01',
      base_servings: 4,
      is_bookmarked: false,
      source_url: null,
    },
    {
      id: 'recipe-2',
      name: 'Chicken Tacos',
      source_type: 'hellofresh_card',
      cook_time_minutes: 25,
      prep_time_minutes: 15,
      tags: ['mexican'],
      created_at: '2024-01-02',
      base_servings: 2,
      is_bookmarked: true,
      source_url: null,
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock: successful recipe load
    vi.mocked(useRecipeList).mockReturnValue({
      data: mockRecipes,
      isLoading: false,
      isError: false,
      error: null,
    } as any)
  })

  describe('page structure', () => {
    it('renders page title', () => {
      renderWithRouter(<Recipes />)
      expect(screen.getByText('Recipes')).toBeInTheDocument()
    })

    it('renders a search icon button instead of an always-visible search bar', () => {
      renderWithRouter(<Recipes />)
      expect(screen.getByRole('button', { name: 'Search recipes' })).toBeInTheDocument()
      expect(screen.queryByPlaceholderText('Search recipes...')).not.toBeInTheDocument()
    })

    it('expands the search icon into a focused input', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)
      const input = await openSearch(user)
      expect(input).toHaveFocus()
      expect(screen.queryByRole('button', { name: 'Search recipes' })).not.toBeInTheDocument()
    })

    it('collapses back to the icon when the empty input loses focus', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)
      await openSearch(user)
      await user.click(screen.getByText('Recipes'))
      expect(screen.getByRole('button', { name: 'Search recipes' })).toBeInTheDocument()
      expect(screen.queryByPlaceholderText('Search recipes...')).not.toBeInTheDocument()
    })

    it('renders in PageContainer', () => {
      const { container } = renderWithRouter(<Recipes />)
      // PageContainer provides consistent layout
      expect(container.querySelector('.py-6')).toBeInTheDocument()
    })
  })

  describe('carousel view (default)', () => {
    const sectionHeading = (label: string) => screen.getByRole('heading', { name: `${label}.` })

    it('displays carousel view by default', () => {
      renderWithRouter(<Recipes />)
      expect(sectionHeading('Your favorites')).toBeInTheDocument()
      expect(screen.getByRole('navigation', { name: 'Recipe themes' })).toBeInTheDocument()
    })

    it("leads with the user's own rows", () => {
      renderWithRouter(<Recipes />)
      expect(sectionHeading('Your favorites')).toBeInTheDocument()
      expect(sectionHeading('Recently added')).toBeInTheDocument()
      expect(sectionHeading('Quick meals')).toBeInTheDocument()
    })

    it('has no hard-coded cuisine rows; theme lists come from /themes', () => {
      renderWithRouter(<Recipes />)
      expect(screen.queryByRole('heading', { name: 'Italian.' })).not.toBeInTheDocument()
      expect(useRecipeList).not.toHaveBeenCalledWith(expect.objectContaining({ tag: 'italian' }), expect.anything())
    })

    it("calls useRecipeList once per own row", () => {
      renderWithRouter(<Recipes />)
      const distinct = new Set(vi.mocked(useRecipeList).mock.calls.map(([f]) => JSON.stringify(f)))
      expect(distinct.size).toBe(3)
    })

    it('passes correct filters to each carousel', () => {
      renderWithRouter(<Recipes />)

      // Your favorites is the user's liked recipes, not every recipe
      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 20, liked: true }),
        expect.anything()
      )
      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({ limit: 20, max_cook_time: 30 }),
        expect.anything()
      )
    })

    it('does not render grid components in carousel view', () => {
      renderWithRouter(<Recipes />)

      // Grid-specific elements should not be present
      expect(screen.queryByRole('button', { name: 'Back to browse view' })).not.toBeInTheDocument()
      expect(screen.queryByDisplayValue('All sources')).not.toBeInTheDocument()
    })
  })

  describe('search functionality', () => {
    it('transitions to grid view when typing in search bar', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      const searchInput = await openSearch(user)
      await user.type(searchInput, 'pasta')

      // Wait for debounce and state update
      await waitFor(() => {
        // Grid view should show back button
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })
    })

    it('maintains grid view while search has value', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      const searchInput = await openSearch(user)
      await user.type(searchInput, 'taco')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      // Carousel rows should not be visible in grid mode
      expect(screen.queryByRole('heading', { name: 'Your favorites.' })).not.toBeInTheDocument()
    })

    it('returns to carousel view when search is cleared and no filters active', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      const searchInput = await openSearch(user)

      // Type and then clear
      await user.type(searchInput, 'soup')
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      // Clear the search
      await user.clear(searchInput)

      // Should return to carousel view
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Your favorites.' })).toBeInTheDocument()
      })
    })

    it('does not return to carousel if filters are still active', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      // Type in search to enter grid mode
      const searchInput = await openSearch(user)
      await user.type(searchInput, 'pasta')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      // Add a filter
      const sourceSelect = screen.getByDisplayValue('All sources')
      await user.selectOptions(sourceSelect, 'manual')

      // Clear search
      await user.clear(searchInput)

      // Should stay in grid mode because filter is active
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })
    })
  })

  describe('see all functionality', () => {
    it('transitions to grid view when "See all" is clicked', async () => {
      const user = userEvent.setup()
      renderWithRouter(<Recipes />)

      // Find "See all" button for Quick meals section
      const seeAllButtons = screen.getAllByRole('button', { name: /see all/i })
      await user.click(seeAllButtons[0])

      // Should show grid view with back button
      expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
    })

    it('applies section filter when transitioning to grid', async () => {
      const user = userEvent.setup()
      renderWithRouter(<Recipes />)

      // Click "See all" on Quick meals (has max_cook_time: 30 filter)
      await user.click(screen.getByRole('button', { name: 'See all quick meals' }))

      // Grid opens with the time filter on at 30 min
      await waitFor(() => {
        expect(screen.getByText('up to 30 min')).toBeInTheDocument()
      })
    })
  })

  describe('back button functionality', () => {
    it('returns to carousel view when back button is clicked', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      // Enter grid mode via search
      const searchInput = await openSearch(user)
      await user.type(searchInput, 'chicken')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      // Click back button
      const backButton = screen.getByRole('button', { name: 'Back to browse view' })
      await user.click(backButton)

      // Should return to carousel view
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Your favorites.' })).toBeInTheDocument()
      })
    })

    it('clears search and filters when back button is clicked', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      // Enter grid mode and add search + filter
      const searchInput = await openSearch(user)
      await user.type(searchInput, 'pasta')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      const sourceSelect = screen.getByDisplayValue('All sources')
      await user.selectOptions(sourceSelect, 'manual')

      // Click back
      const backButton = screen.getByRole('button', { name: 'Back to browse view' })
      await user.click(backButton)

      // Search should be cleared and collapsed back to the icon
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Search recipes' })).toBeInTheDocument()
      })
      expect(screen.queryByPlaceholderText('Search recipes...')).not.toBeInTheDocument()

      // Should be in carousel mode (no filter dropdowns visible)
      expect(screen.queryByDisplayValue('All sources')).not.toBeInTheDocument()
    })
  })

  describe('view mode state management', () => {
    it('maintains separate state for search query, filters, and view mode', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      // Start in carousel mode
      expect(screen.getByRole('heading', { name: 'Your favorites.' })).toBeInTheDocument()

      // Enter search -> grid mode
      const searchInput = await openSearch(user)
      await user.type(searchInput, 'curry')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      // Verify search value is maintained
      expect(searchInput).toHaveValue('curry')
    })

    it('handles rapid view mode transitions', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      const searchInput = await openSearch(user)

      // Enter grid mode
      await user.type(searchInput, 'test')
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      // Back to carousel
      const backButton = screen.getByRole('button', { name: 'Back to browse view' })
      await user.click(backButton)

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Your favorites.' })).toBeInTheDocument()
      })

      // Enter grid mode again via "See all"
      const seeAllButtons = screen.getAllByRole('button', { name: /see all/i })
      await user.click(seeAllButtons[0])

      // Should be back in grid mode
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })
    })
  })

  describe('integration between components', () => {
    it('search button, ThemeBar, and RecipeCarousel work together in carousel view', () => {
      renderWithRouter(<Recipes />)

      // All three components should be visible
      expect(screen.getByRole('button', { name: 'Search recipes' })).toBeInTheDocument()
      expect(screen.getByRole('navigation', { name: 'Recipe themes' })).toBeInTheDocument()
      expect(screen.getAllByRole('button', { name: /see all/i }).length).toBeGreaterThan(0)
    })

    it('SearchBar, FilterChips, and RecipeGrid work together in grid view', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      const searchInput = await openSearch(user)
      await user.type(searchInput, 'burger')

      await waitFor(() => {
        // All three components should be visible in grid mode
        expect(screen.getByPlaceholderText('Search recipes...')).toBeInTheDocument()
        expect(screen.getByDisplayValue('All sources')).toBeInTheDocument() // FilterChips
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument() // RecipeGrid
      })
    })
  })

  describe('accessibility', () => {
    it('page title is rendered as heading', () => {
      renderWithRouter(<Recipes />)
      // PageTitle appends the signature olive period, so the accessible name
      // is "Recipes.", not "Recipes".
      const heading = screen.getByRole('heading', { name: 'Recipes.' })
      expect(heading).toBeInTheDocument()
    })

    it('maintains focus management during view transitions', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      const searchInput = await openSearch(user)
      await user.type(searchInput, 'salad')

      // Input should still be accessible
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search recipes...')).toBeInTheDocument()
      })
    })
  })

  describe('carousel section configuration', () => {
    it('configures favorites section correctly', () => {
      renderWithRouter(<Recipes />)

      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 20,
        }),
        expect.anything()
      )
    })

    it('configures quick meals with max_cook_time filter', () => {
      renderWithRouter(<Recipes />)

      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 20,
          max_cook_time: 30,
        }),
        expect.anything()
      )
    })
  })
})
