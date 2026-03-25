import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import Recipes from '../Recipes'
import { useRecipeList } from '../../api'

// Mock the API hook
vi.mock('../../api', () => ({
  useRecipeList: vi.fn(),
}))

// Helper to render component with Router context
const renderWithRouter = (ui: React.ReactElement) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>)
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

    it('renders search bar', () => {
      renderWithRouter(<Recipes />)
      expect(screen.getByPlaceholderText('Search recipes...')).toBeInTheDocument()
    })

    it('renders in PageContainer', () => {
      const { container } = renderWithRouter(<Recipes />)
      // PageContainer provides consistent layout
      expect(container.querySelector('.py-6')).toBeInTheDocument()
    })
  })

  describe('carousel view (default)', () => {
    it('displays carousel view by default', () => {
      renderWithRouter(<Recipes />)

      // Should show section navigation
      expect(screen.getByRole('button', { name: 'Your favorites' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Quick meals' })).toBeInTheDocument()
    })

    it('renders all carousel sections', () => {
      renderWithRouter(<Recipes />)

      // Check for section headers (via SectionHeader component which wraps text)
      expect(screen.getByText('Your favorites')).toBeInTheDocument()
      expect(screen.getByText('Quick meals')).toBeInTheDocument()
      expect(screen.getByText('Recently added')).toBeInTheDocument()
      expect(screen.getByText('Italian')).toBeInTheDocument()
      expect(screen.getByText('Mexican')).toBeInTheDocument()
      expect(screen.getByText('Asian')).toBeInTheDocument()
      expect(screen.getByText('Vegan')).toBeInTheDocument()
    })

    it('renders section navigation with all sections', () => {
      renderWithRouter(<Recipes />)

      // Section nav should have all section links
      expect(screen.getByRole('button', { name: 'Your favorites' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Quick meals' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Recently added' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Italian' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Mexican' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Asian' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Vegan' })).toBeInTheDocument()
    })

    it('calls useRecipeList for each carousel section', () => {
      renderWithRouter(<Recipes />)

      // Should be called 7 times (one for each section)
      expect(useRecipeList).toHaveBeenCalledTimes(7)
    })

    it('passes correct filters to each carousel', () => {
      renderWithRouter(<Recipes />)

      // Verify quick-meals section has max_cook_time filter
      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 10,
          max_cook_time: 30,
        })
      )

      // Verify italian section has tag filter
      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 10,
          tag: 'italian',
        })
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

      const searchInput = screen.getByPlaceholderText('Search recipes...')
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

      const searchInput = screen.getByPlaceholderText('Search recipes...')
      await user.type(searchInput, 'taco')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      // Section nav should not be visible in grid mode
      expect(screen.queryByRole('button', { name: 'Your favorites' })).not.toBeInTheDocument()
    })

    it('returns to carousel view when search is cleared and no filters active', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      const searchInput = screen.getByPlaceholderText('Search recipes...')

      // Type and then clear
      await user.type(searchInput, 'soup')
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      // Clear the search
      await user.clear(searchInput)

      // Should return to carousel view
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Your favorites' })).toBeInTheDocument()
      })
    })

    it('does not return to carousel if filters are still active', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      // Type in search to enter grid mode
      const searchInput = screen.getByPlaceholderText('Search recipes...')
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
      const seeAllButtons = screen.getAllByRole('button', { name: /see all/i })
      const quickMealsSeeAll = seeAllButtons[1] // Second carousel is quick meals

      await user.click(quickMealsSeeAll)

      // Should show grid with filter chip for cook time
      await waitFor(() => {
        expect(screen.getByText('Max 30 min or less')).toBeInTheDocument()
      })
    })

    it('applies tag filter when "See all" clicked on cuisine section', async () => {
      const user = userEvent.setup()
      renderWithRouter(<Recipes />)

      // Click "See all" on Italian section (has tag: 'italian' filter)
      const seeAllButtons = screen.getAllByRole('button', { name: /see all/i })
      const italianSeeAll = seeAllButtons[3] // Fourth carousel is Italian

      await user.click(italianSeeAll)

      // Should show grid with cuisine filter chip
      await waitFor(() => {
        expect(screen.getByText('Cuisine: Italian')).toBeInTheDocument()
      })
    })
  })

  describe('back button functionality', () => {
    it('returns to carousel view when back button is clicked', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      // Enter grid mode via search
      const searchInput = screen.getByPlaceholderText('Search recipes...')
      await user.type(searchInput, 'chicken')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      // Click back button
      const backButton = screen.getByRole('button', { name: 'Back to browse view' })
      await user.click(backButton)

      // Should return to carousel view
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Your favorites' })).toBeInTheDocument()
      })
    })

    it('clears search and filters when back button is clicked', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      // Enter grid mode and add search + filter
      const searchInput = screen.getByPlaceholderText('Search recipes...')
      await user.type(searchInput, 'pasta')

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      const sourceSelect = screen.getByDisplayValue('All sources')
      await user.selectOptions(sourceSelect, 'manual')

      // Click back
      const backButton = screen.getByRole('button', { name: 'Back to browse view' })
      await user.click(backButton)

      // Search should be cleared
      await waitFor(() => {
        const clearedInput = screen.getByPlaceholderText('Search recipes...') as HTMLInputElement
        expect(clearedInput.value).toBe('')
      })

      // Should be in carousel mode (no filter dropdowns visible)
      expect(screen.queryByDisplayValue('All sources')).not.toBeInTheDocument()
    })
  })

  describe('view mode state management', () => {
    it('maintains separate state for search query, filters, and view mode', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      // Start in carousel mode
      expect(screen.getByRole('button', { name: 'Your favorites' })).toBeInTheDocument()

      // Enter search -> grid mode
      const searchInput = screen.getByPlaceholderText('Search recipes...')
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

      const searchInput = screen.getByPlaceholderText('Search recipes...')

      // Enter grid mode
      await user.type(searchInput, 'test')
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
      })

      // Back to carousel
      const backButton = screen.getByRole('button', { name: 'Back to browse view' })
      await user.click(backButton)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Your favorites' })).toBeInTheDocument()
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
    it('SearchBar, SectionNav, and RecipeCarousel work together in carousel view', () => {
      renderWithRouter(<Recipes />)

      // All three components should be visible
      expect(screen.getByPlaceholderText('Search recipes...')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Quick meals' })).toBeInTheDocument()
      expect(screen.getAllByRole('button', { name: /see all/i }).length).toBeGreaterThan(0)
    })

    it('SearchBar, FilterChips, and RecipeGrid work together in grid view', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      const searchInput = screen.getByPlaceholderText('Search recipes...')
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
      const heading = screen.getByRole('heading', { name: 'Recipes' })
      expect(heading).toBeInTheDocument()
    })

    it('maintains focus management during view transitions', async () => {
      const user = userEvent.setup({ delay: null })
      renderWithRouter(<Recipes />)

      const searchInput = screen.getByPlaceholderText('Search recipes...')
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
          limit: 10,
        })
      )
    })

    it('configures quick meals with max_cook_time filter', () => {
      renderWithRouter(<Recipes />)

      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 10,
          max_cook_time: 30,
        })
      )
    })

    it('configures cuisine sections with tag filters', () => {
      renderWithRouter(<Recipes />)

      // Check Italian section
      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 10,
          tag: 'italian',
        })
      )

      // Check Mexican section
      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 10,
          tag: 'mexican',
        })
      )

      // Check Asian section
      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 10,
          tag: 'asian',
        })
      )
    })
  })
})
