import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import OutcomesSection from './OutcomesSection'
import { useRecipeOutcomes } from '../../api/hooks/useRecipes'
import type { RecipeOutcome } from '../../api/types'

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ currentUser: { id: 'user-1', name: 'Sarah' } }),
}))

vi.mock('../../api/hooks/useRecipes', () => ({
  useRecipeOutcomes: vi.fn(),
}))

// relativeTime is used for last_cooked_at; pin it to a stable output in tests
vi.mock('../../utils/relativeTime', () => ({
  relativeTime: () => '3 days ago',
}))

const mockUseRecipeOutcomes = vi.mocked(useRecipeOutcomes)

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>
}

function makeOutcome(overrides: Partial<RecipeOutcome> = {}): RecipeOutcome {
  return {
    user_id: 'user-2',
    user_name: 'Alex',
    rating: 4,
    rating_comment: null,
    rating_photos: null,
    times_cooked: 2,
    last_cooked_at: '2026-11-09T10:00:00Z',
    latest_cook_notes: null,
    ...overrides,
  }
}

describe('OutcomesSection', () => {
  it('renders two rows; viewer row is first and labelled "You"', () => {
    const viewerOutcome = makeOutcome({
      user_id: 'user-1',
      user_name: 'Sarah',
      rating: 5,
      rating_comment: 'Amazing every time.',
      times_cooked: 3,
      last_cooked_at: '2026-11-10T18:00:00Z',
      latest_cook_notes: 'Added extra chili.',
    })
    const otherOutcome = makeOutcome()

    // Backend returns other member first; component must sort viewer to top.
    mockUseRecipeOutcomes.mockReturnValue({
      data: [otherOutcome, viewerOutcome],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useRecipeOutcomes>)

    render(<OutcomesSection recipeId="recipe-1" />, { wrapper })

    const items = screen.getAllByRole('listitem')
    expect(items[0]).toHaveTextContent('You')
    expect(items[1]).toHaveTextContent('Alex')
  })

  it('renders stars, cook count, comment and notes for viewer row', () => {
    mockUseRecipeOutcomes.mockReturnValue({
      data: [
        makeOutcome({
          user_id: 'user-1',
          user_name: 'Sarah',
          rating: 4,
          times_cooked: 2,
          last_cooked_at: '2026-11-09T10:00:00Z',
          rating_comment: 'Very tasty.',
          latest_cook_notes: 'Added extra lime.',
        }),
      ],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useRecipeOutcomes>)

    render(<OutcomesSection recipeId="recipe-1" />, { wrapper })

    expect(screen.getByText('You')).toBeInTheDocument()
    expect(screen.getByLabelText('4 of 5')).toBeInTheDocument()
    expect(screen.getByText(/cooked 2 times, last/i)).toBeInTheDocument()
    expect(screen.getByText(/Very tasty\./)).toBeInTheDocument()
    expect(screen.getByText(/Last time: Added extra lime\./)).toBeInTheDocument()
  })

  it('renders photos as thumbnail links opening in a new tab', () => {
    mockUseRecipeOutcomes.mockReturnValue({
      data: [
        makeOutcome({
          user_id: 'user-1',
          user_name: 'Sarah',
          rating_photos: ['https://example.com/photo1.jpg', 'https://example.com/photo2.jpg'],
        }),
      ],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useRecipeOutcomes>)

    render(<OutcomesSection recipeId="recipe-1" />, { wrapper })

    const links = screen.getAllByRole('link')
    expect(links).toHaveLength(2)
    expect(links[0]).toHaveAttribute('target', '_blank')
    expect(links[0]).toHaveAttribute('href', 'https://example.com/photo1.jpg')
  })

  it('hides cook count when times_cooked is 0', () => {
    mockUseRecipeOutcomes.mockReturnValue({
      data: [makeOutcome({ user_id: 'user-1', times_cooked: 0, last_cooked_at: null })],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useRecipeOutcomes>)

    render(<OutcomesSection recipeId="recipe-1" />, { wrapper })

    expect(screen.queryByText(/cooked/i)).not.toBeInTheDocument()
  })

  it('renders empty state when outcomes list is empty', () => {
    mockUseRecipeOutcomes.mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useRecipeOutcomes>)

    render(<OutcomesSection recipeId="recipe-1" />, { wrapper })

    expect(screen.getByText('Nobody here has cooked this yet.')).toBeInTheDocument()
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  })

  it('renders two skeleton rows while loading', () => {
    mockUseRecipeOutcomes.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useRecipeOutcomes>)

    render(<OutcomesSection recipeId="recipe-1" />, { wrapper })

    // Two skeleton li elements
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.queryByText('Nobody here has cooked this yet.')).not.toBeInTheDocument()
  })

  it('renders error line when outcomes fail to load', () => {
    mockUseRecipeOutcomes.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useRecipeOutcomes>)

    render(<OutcomesSection recipeId="recipe-1" />, { wrapper })

    expect(screen.getByText('Could not load how it turned out.')).toBeInTheDocument()
    expect(screen.queryByRole('listitem')).not.toBeInTheDocument()
  })
})
