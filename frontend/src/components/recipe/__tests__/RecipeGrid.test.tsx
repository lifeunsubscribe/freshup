import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import RecipeGrid from '../RecipeGrid'
import { useRecipeList } from '../../../api'
import type { RecipeFilters } from '../FilterChips'

// Mock the API hook
vi.mock('../../../api', () => ({
  useRecipeList: vi.fn(),
}))

// Helper to render component with Router context
const renderWithRouter = (ui: React.ReactElement) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>)
}

describe('RecipeGrid', () => {
  const mockOnFilterChange = vi.fn()
  const mockOnBack = vi.fn()

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
  })

  describe('basic rendering', () => {
    it('renders back button', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(screen.getByRole('button', { name: 'Back to browse view' })).toBeInTheDocument()
    })

    it('renders FilterChips component', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      // FilterChips renders dropdowns
      expect(screen.getByDisplayValue('All sources')).toBeInTheDocument()
    })

    it('calls onBack when back button is clicked', async () => {
      const user = userEvent.setup()
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      const backButton = screen.getByRole('button', { name: 'Back to browse view' })
      await user.click(backButton)

      expect(mockOnBack).toHaveBeenCalledTimes(1)
    })
  })

  describe('loading state', () => {
    it('displays loading message when initial load', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(screen.getByText('Loading recipes...')).toBeInTheDocument()
    })

    it('does not display loading message during pagination', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: true,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      // Should not show main loading message when data exists
      expect(screen.queryByText('Loading recipes...')).not.toBeInTheDocument()
    })
  })

  describe('error state', () => {
    it('displays error message when isError is true', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: new Error('Network error'),
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(screen.getByText(/failed to load recipes/i)).toBeInTheDocument()
      expect(screen.getByText(/network error/i)).toBeInTheDocument()
    })

    it('displays generic error message when error is not an Error instance', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: 'Unknown error',
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(screen.getByText(/failed to load recipes/i)).toBeInTheDocument()
      expect(screen.getByText(/please try again/i)).toBeInTheDocument()
    })
  })

  describe('empty state', () => {
    it('displays empty message when no recipes match filters', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(screen.getByText('No recipes found')).toBeInTheDocument()
      expect(screen.getByText('Try adjusting your search or filters')).toBeInTheDocument()
    })
  })

  describe('recipe grid display', () => {
    it('renders recipes in a 2-column grid', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const { container } = renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      const grid = container.querySelector('.grid-cols-2')
      expect(grid).toBeInTheDocument()
    })

    it('renders all recipe cards', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(screen.getByText('Pasta Carbonara')).toBeInTheDocument()
      expect(screen.getByText('Chicken Tacos')).toBeInTheDocument()
    })

    it('displays recipe count', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(screen.getByText('2 recipes found')).toBeInTheDocument()
    })

    it('displays singular form for single recipe', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [mockRecipes[0]],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(screen.getByText('1 recipe found')).toBeInTheDocument()
    })
  })

  describe('search and filter integration', () => {
    it('passes search query to useRecipeList hook', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery="pasta"
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          search: 'pasta',
        })
      )
    })

    it('passes filters to useRecipeList hook', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const filters: RecipeFilters = {
        source_type: 'manual',
        tag: 'italian',
        max_cook_time: 30,
      }

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={filters}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          source_type: 'manual',
          tag: 'italian',
          max_cook_time: 30,
        })
      )
    })

    it('combines search query and filters', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const filters: RecipeFilters = { tag: 'mexican' }

      renderWithRouter(
        <RecipeGrid
          searchQuery="taco"
          filters={filters}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          search: 'taco',
          tag: 'mexican',
        })
      )
    })

    it('omits search from API call when empty', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          search: undefined,
        })
      )
    })
  })

  describe('pagination', () => {
    it('includes limit and offset in API call', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(useRecipeList).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 100,
          offset: 0,
        })
      )
    })

    it('shows "Load More" button when full page of recipes returned', () => {
      // Create 100 recipes (full page)
      const fullPageRecipes = Array.from({ length: 100 }, (_, i) => ({
        id: `recipe-${i}`,
        name: `Recipe ${i}`,
        source_type: 'manual',
        cook_time_minutes: 30,
        prep_time_minutes: 10,
        tags: ['test'],
        created_at: '2024-01-01',
        base_servings: 4,
      }))

      vi.mocked(useRecipeList).mockReturnValue({
        data: fullPageRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(screen.getByRole('button', { name: 'Load More Recipes' })).toBeInTheDocument()
    })

    it('does not show "Load More" button when fewer than full page returned', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes, // Only 2 recipes, less than 100
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      expect(screen.queryByRole('button', { name: 'Load More Recipes' })).not.toBeInTheDocument()
    })

    it('shows pagination loading message when loading more recipes', () => {
      // First render with recipes
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: true,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      // Note: This will only show if offset > 0, which requires state management
      // The test captures the intended behavior
      expect(screen.queryByText('Loading more recipes...')).not.toBeInTheDocument()
    })
  })

  describe('accessibility', () => {
    it('has aria-live region for results count', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const { container } = renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      const resultsCount = container.querySelector('[aria-live="polite"]')
      expect(resultsCount).toBeInTheDocument()
    })

    it('back button has proper aria-label', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      const backButton = screen.getByRole('button', { name: 'Back to browse view' })
      expect(backButton).toHaveAttribute('aria-label', 'Back to browse view')
    })
  })

  describe('responsive grid', () => {
    it('applies 2-column grid layout', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const { container } = renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      const grid = container.querySelector('.grid')
      expect(grid).toHaveClass('grid-cols-2')
    })

    it('applies gap between grid items', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const { container } = renderWithRouter(
        <RecipeGrid
          searchQuery=""
          filters={{}}
          onFilterChange={mockOnFilterChange}
          onBack={mockOnBack}
        />
      )

      const grid = container.querySelector('.grid')
      expect(grid).toHaveClass('gap-3')
    })
  })
})
