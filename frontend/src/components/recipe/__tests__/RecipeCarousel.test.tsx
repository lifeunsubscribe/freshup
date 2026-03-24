import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import RecipeCarousel from '../RecipeCarousel'
import { useRecipeList } from '../../../api'

// Mock the API hook
vi.mock('../../../api', () => ({
  useRecipeList: vi.fn(),
}))

// Helper to render component with Router context
const renderWithRouter = (ui: React.ReactElement) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>)
}

describe('RecipeCarousel', () => {
  const mockFilters = { limit: 10 }
  const mockOnSeeAll = vi.fn()

  const mockRecipes = [
    {
      id: 'recipe-1',
      name: 'Sweet Potato Curry',
      source_type: 'hellofresh_card',
      cook_time_minutes: 25,
      prep_time_minutes: 10,
      tags: ['vegetarian'],
    },
    {
      id: 'recipe-2',
      name: 'Chicken Tacos',
      source_type: 'manual',
      cook_time_minutes: 30,
      prep_time_minutes: 15,
      tags: ['mexican'],
    },
    {
      id: 'recipe-3',
      name: 'Pasta Carbonara',
      source_type: 'hellofresh_card',
      cook_time_minutes: 20,
      prep_time_minutes: 5,
      tags: ['italian'],
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('basic rendering', () => {
    it('renders section header with title', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      expect(screen.getByText('Quick meals')).toBeInTheDocument()
    })

    it('renders "See all" button', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      expect(screen.getByRole('button', { name: /see all quick meals/i })).toBeInTheDocument()
    })

    it('calls onSeeAll when "See all" button is clicked', async () => {
      const user = userEvent.setup()
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      await user.click(screen.getByRole('button', { name: /see all quick meals/i }))
      expect(mockOnSeeAll).toHaveBeenCalledTimes(1)
    })
  })

  describe('loading state', () => {
    it('displays loading message when isLoading is true', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      expect(screen.getByText('Loading recipes...')).toBeInTheDocument()
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
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
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
        error: 'Something went wrong',
      } as any)

      renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      expect(screen.getByText(/failed to load recipes/i)).toBeInTheDocument()
      expect(screen.getByText(/please try again/i)).toBeInTheDocument()
    })
  })

  describe('empty state', () => {
    it('displays empty message when no recipes are returned', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      expect(screen.getByText('No recipes found for this category.')).toBeInTheDocument()
    })
  })

  describe('recipe cards', () => {
    it('renders all recipe cards when data is available', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      expect(screen.getByText('Sweet Potato Curry')).toBeInTheDocument()
      expect(screen.getByText('Chicken Tacos')).toBeInTheDocument()
      expect(screen.getByText('Pasta Carbonara')).toBeInTheDocument()
    })

    it('renders carousel with correct ARIA label', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      expect(screen.getByRole('list', { name: 'Quick meals carousel' })).toBeInTheDocument()
    })
  })

  describe('navigation controls', () => {
    beforeEach(() => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)
    })

    it('renders left navigation button with correct aria-label', async () => {
      const { container } = renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      // Mock the scroll container to have overflow (scrollWidth > clientWidth)
      const scrollContainer = container.querySelector('[role="list"]') as HTMLDivElement
      expect(scrollContainer).toBeInTheDocument()

      Object.defineProperty(scrollContainer, 'scrollWidth', { value: 1000, configurable: true })
      Object.defineProperty(scrollContainer, 'clientWidth', { value: 500, configurable: true })
      Object.defineProperty(scrollContainer, 'scrollLeft', { value: 100, configurable: true })

      // Trigger the effect to update button states
      scrollContainer.dispatchEvent(new Event('scroll'))

      await waitFor(() => {
        const scrollLeft = screen.getByRole('button', { name: 'Scroll left' })
        expect(scrollLeft).toBeInTheDocument()
      })
    })

    it('renders right navigation button with correct aria-label', async () => {
      const { container } = renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      // Mock the scroll container to have overflow (scrollWidth > clientWidth)
      const scrollContainer = container.querySelector('[role="list"]') as HTMLDivElement
      expect(scrollContainer).toBeInTheDocument()

      Object.defineProperty(scrollContainer, 'scrollWidth', { value: 1000, configurable: true })
      Object.defineProperty(scrollContainer, 'clientWidth', { value: 500, configurable: true })
      Object.defineProperty(scrollContainer, 'scrollLeft', { value: 0, configurable: true })

      // Trigger the effect to update button states
      scrollContainer.dispatchEvent(new Event('scroll'))

      await waitFor(() => {
        const scrollRight = screen.getByRole('button', { name: 'Scroll right' })
        expect(scrollRight).toBeInTheDocument()
      })
    })

    it('scroll buttons call scroll method when clicked', async () => {
      const user = userEvent.setup()
      const { container } = renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      // Mock the scroll container to have overflow and setup scrollTo
      const scrollContainer = container.querySelector('[role="list"]') as HTMLDivElement
      expect(scrollContainer).toBeInTheDocument()

      Object.defineProperty(scrollContainer, 'scrollWidth', { value: 1000, configurable: true })
      Object.defineProperty(scrollContainer, 'clientWidth', { value: 500, configurable: true })
      Object.defineProperty(scrollContainer, 'scrollLeft', { value: 0, configurable: true })

      const mockScrollTo = vi.fn()
      scrollContainer.scrollTo = mockScrollTo

      // Trigger the effect to update button states
      scrollContainer.dispatchEvent(new Event('scroll'))

      await waitFor(() => {
        const scrollRight = screen.getByRole('button', { name: 'Scroll right' })
        expect(scrollRight).toBeInTheDocument()
        expect(scrollRight).not.toBeDisabled()
      })

      const scrollRight = screen.getByRole('button', { name: 'Scroll right' })
      await user.click(scrollRight)

      expect(mockScrollTo).toHaveBeenCalledWith({
        left: expect.any(Number),
        behavior: 'smooth',
      })
    })
  })

  describe('section id', () => {
    it('applies sectionId to section element when provided', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const { container } = renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
          sectionId="quick-meals"
        />
      )

      const section = container.querySelector('#quick-meals')
      expect(section).toBeInTheDocument()
    })

    it('does not apply id when sectionId is not provided', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const { container } = renderWithRouter(
        <RecipeCarousel
          title="Quick meals"
          filters={mockFilters}
          onSeeAll={mockOnSeeAll}
        />
      )

      const section = container.querySelector('section')
      expect(section).toBeInTheDocument()
      expect(section?.id).toBe('')
    })
  })
})
