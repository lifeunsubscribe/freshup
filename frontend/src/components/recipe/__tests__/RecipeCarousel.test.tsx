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
// ConnectedRecipeCard (rendered inside) reads engagement state from React Query.
// These tests mock the API layer rather than wrapping in a QueryClientProvider,
// so the engagement hooks are stubbed the same way.
vi.mock('../../../api/hooks/useRecipeEngagement', () => ({
  useMyRecipeRelations: () => ({ data: new Map() }),
  useToggleBookmark: () => ({ mutate: vi.fn() }),
  useToggleLike: () => ({ mutate: vi.fn() }),
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
    it('renders nothing when no recipes are returned', () => {
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

      expect(screen.queryByRole('region', { name: 'Quick meals' })).not.toBeInTheDocument()
      expect(screen.queryByText('Quick meals')).not.toBeInTheDocument()
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

  describe('subtitle prop', () => {
    it('renders computed subtitle when subtitle fn is provided', () => {
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
          subtitle={(n) => `${n ?? 0} items · added by hand`}
        />
      )

      expect(screen.getByText(`${mockRecipes.length} items · added by hand`)).toBeInTheDocument()
    })

    it('does not render subtitle when prop is omitted', () => {
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

      expect(screen.queryByText(/items · added by hand/)).not.toBeInTheDocument()
    })
  })

  describe('onCountChange', () => {
    it('reports the loaded recipe count', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: mockRecipes,
        isLoading: false,
        isError: false,
        error: null,
      } as any)
      const onCountChange = vi.fn()

      renderWithRouter(
        <RecipeCarousel title="Quick meals" filters={mockFilters} onSeeAll={mockOnSeeAll} onCountChange={onCountChange} />
      )

      expect(onCountChange).toHaveBeenCalledWith(mockRecipes.length)
    })

    it('reports 0 for an empty row so the page can drop its nav entry', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)
      const onCountChange = vi.fn()

      renderWithRouter(
        <RecipeCarousel title="Quick meals" filters={mockFilters} onSeeAll={mockOnSeeAll} onCountChange={onCountChange} />
      )

      expect(onCountChange).toHaveBeenCalledWith(0)
    })

    it('does not report while loading', () => {
      vi.mocked(useRecipeList).mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      } as any)
      const onCountChange = vi.fn()

      renderWithRouter(
        <RecipeCarousel title="Quick meals" filters={mockFilters} onSeeAll={mockOnSeeAll} onCountChange={onCountChange} />
      )

      expect(onCountChange).not.toHaveBeenCalled()
    })
  })

  describe('footer prop', () => {
    it('renders footer content after cards when recipes exist', () => {
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
          footer={<p>Footer line here</p>}
        />
      )

      expect(screen.getByText('Footer line here')).toBeInTheDocument()
    })

    it('does not render footer when the row is empty', () => {
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
          footer={<p>Footer in empty state</p>}
        />
      )

      expect(screen.queryByText('Footer in empty state')).not.toBeInTheDocument()
    })

    it('does not render footer during loading', () => {
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
          footer={<p>Footer should not appear</p>}
        />
      )

      expect(screen.queryByText('Footer should not appear')).not.toBeInTheDocument()
    })

    it('does not render footer during error', () => {
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
          footer={<p>Footer should not appear</p>}
        />
      )

      expect(screen.queryByText('Footer should not appear')).not.toBeInTheDocument()
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

  describe('accessibility attributes', () => {
    it('applies role="region" to section element', () => {
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

      const section = screen.getByRole('region', { name: 'Quick meals' })
      expect(section).toBeInTheDocument()
    })

    it('applies aria-roledescription="carousel" to section element', () => {
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
      expect(section).toHaveAttribute('aria-roledescription', 'carousel')
    })

    it('applies aria-label with title to section element', () => {
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
      expect(section).toHaveAttribute('aria-label', 'Quick meals')
    })
  })

  describe('minCount and hideIfWithin', () => {
    const loaded = (data: unknown) => ({ data, isLoading: false, isError: false, error: null }) as any
    const many = (n: number, prefix = 'quick') =>
      Array.from({ length: n }, (_, i) => ({ ...mockRecipes[0], id: `${prefix}-${i}`, name: `Recipe ${prefix}-${i}` }))
    const aboveFilters = { limit: 20, viewed: true }
    /** The row's own list and the list of the row above it. */
    const mockLists = (own: unknown, above: unknown) =>
      vi.mocked(useRecipeList).mockImplementation((filters) => ((filters as any)?.viewed ? above : own) as any)
    const renderRow = (props: Partial<React.ComponentProps<typeof RecipeCarousel>> = {}) => {
      const onCountChange = vi.fn()
      renderWithRouter(
        <RecipeCarousel title="Quick meals" filters={mockFilters} onSeeAll={mockOnSeeAll} onCountChange={onCountChange} {...props} />
      )
      return onCountChange
    }
    const row = () => screen.queryByRole('region', { name: 'Quick meals' })

    it('hides a row with fewer recipes than minCount and reports it as empty', () => {
      vi.mocked(useRecipeList).mockReturnValue(loaded(many(9)))
      const onCountChange = renderRow({ minCount: 10 })
      expect(row()).not.toBeInTheDocument()
      expect(onCountChange).toHaveBeenCalledWith(0)
    })

    it('shows a row that has exactly minCount recipes', () => {
      vi.mocked(useRecipeList).mockReturnValue(loaded(many(10)))
      const onCountChange = renderRow({ minCount: 10 })
      expect(row()).toBeInTheDocument()
      expect(onCountChange).toHaveBeenCalledWith(10)
    })

    it('hides a row whose every recipe is already in the row above', () => {
      const quick = many(10)
      mockLists(loaded(quick), loaded([...quick, ...many(3, 'other')]))
      const onCountChange = renderRow({ minCount: 10, hideIfWithin: aboveFilters })
      expect(row()).not.toBeInTheDocument()
      expect(onCountChange).toHaveBeenCalledWith(0)
    })

    it('shows the whole row when one recipe is not in the row above', () => {
      const quick = many(10)
      mockLists(loaded(quick), loaded(quick.slice(0, 9)))
      renderRow({ minCount: 10, hideIfWithin: aboveFilters })
      expect(row()).toBeInTheDocument()
      expect(screen.getAllByText(/^Recipe quick-/)).toHaveLength(10)
    })

    it('shows the row when the row above is empty', () => {
      mockLists(loaded(many(10)), loaded([]))
      renderRow({ hideIfWithin: aboveFilters })
      expect(row()).toBeInTheDocument()
    })

    it('asks for the row above with that row’s own filters, so the cache answers', () => {
      mockLists(loaded(many(10)), loaded([]))
      renderRow({ hideIfWithin: aboveFilters })
      expect(useRecipeList).toHaveBeenCalledWith(aboveFilters, { enabled: true })
    })

    it('shows no cards until the row above has loaded', () => {
      mockLists(loaded(many(10)), { data: undefined, isLoading: true, isError: false, error: null })
      const onCountChange = renderRow({ hideIfWithin: aboveFilters })
      expect(screen.getByText('Loading recipes...')).toBeInTheDocument()
      expect(screen.queryAllByText(/^Recipe quick-/)).toHaveLength(0)
      expect(onCountChange).not.toHaveBeenCalled()
    })

    it('shows the row when the row above failed to load', () => {
      mockLists(loaded(many(10)), { data: undefined, isLoading: false, isError: true, error: new Error('x') })
      renderRow({ hideIfWithin: aboveFilters })
      expect(row()).toBeInTheDocument()
    })

    it('without hideIfWithin, makes no second request and ignores other lists', () => {
      vi.mocked(useRecipeList).mockReturnValue(loaded(many(3)))
      renderRow()
      expect(row()).toBeInTheDocument()
      const enabledCalls = vi.mocked(useRecipeList).mock.calls.filter(([, opts]) => (opts as any)?.enabled)
      expect(new Set(enabledCalls.map(([f]) => JSON.stringify(f))).size).toBe(1)
    })
  })
})
