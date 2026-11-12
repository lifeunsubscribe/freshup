import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import RecipeDetail from './RecipeDetail'

// ── Route param ──────────────────────────────────────────────────────────────

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useParams: () => ({ id: 'recipe-1' }),
    useNavigate: () => vi.fn(),
  }
})

// ── Auth ──────────────────────────────────────────────────────────────────────

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ currentUser: { id: 'user-1', name: 'Sarah' } }),
}))

// ── API hooks ──────────────────────────────────────────────────────────────────

const mockCookMutateAsync = vi.fn().mockResolvedValue({})
const mockCreateEntryMutateAsync = vi.fn().mockResolvedValue({})
const mockRateMutateAsync = vi.fn().mockResolvedValue({})

const baseRecipe = {
  id: 'recipe-1',
  name: 'Mushroom Risotto',
  source_type: 'hellofresh',
  source_url: 'https://www.hellofresh.com/recipes/mushroom-risotto',
  source_image: null,
  steps: ['Boil water.', 'Add rice.'],
  notes: null,
  tags: ['vegetarian'],
  cook_time_minutes: 30,
  prep_time_minutes: 10,
  base_servings: 4,
  times_cooked: 3,
  is_persisted: true,
  variation_groups: null,
  nutritional_info: null,
  ingredients: [],
}

vi.mock('../api/hooks/useRecipes', () => ({
  useRecipe: vi.fn(() => ({
    data: baseRecipe,
    isLoading: false,
    isError: false,
  })),
  useRateRecipe: vi.fn(() => ({ mutateAsync: mockRateMutateAsync })),
}))

vi.mock('../api/hooks/useRecipeEngagement', () => ({
  useMyRecipeRelation: vi.fn(() => ({
    data: { rating: null, is_bookmarked: false, is_liked: false, rating_photos: null, rating_comment: null, menu_id: null },
    isLoading: false,
  })),
  useToggleBookmark: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useToggleLike: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useCookRecipe: () => ({ mutateAsync: mockCookMutateAsync }),
  useCookHistory: vi.fn(() => ({ data: [] })),
}))

vi.mock('../api/hooks/usePlan', () => ({
  useCreatePlanEntry: () => ({ mutateAsync: mockCreateEntryMutateAsync }),
}))

vi.mock('../api/hooks/useInventory', () => ({
  useInventoryList: () => ({ data: [], isLoading: false, isError: false }),
}))

vi.mock('../utils/pantryMatcher', () => ({
  checkIngredientAvailability: () => ({
    inStock: [],
    outOfStock: [],
    totalCount: 0,
    inStockCount: 0,
  }),
}))

// ── Render helper ─────────────────────────────────────────────────────────────

let queryClient: QueryClient

function wrapper({ children }: { children: ReactNode }) {
  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </BrowserRouter>
  )
}

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  mockCookMutateAsync.mockReset().mockResolvedValue({})
  mockCreateEntryMutateAsync.mockReset().mockResolvedValue({})
  mockRateMutateAsync.mockReset().mockResolvedValue({})
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

function renderPage() {
  return render(<RecipeDetail />, { wrapper })
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('RecipeDetail', () => {
  describe('SourceLine', () => {
    it('renders source attribution when source_url is set', async () => {
      renderPage()
      // Under the title on every tab; the copy after the last step only exists
      // once the Cook & enjoy! tab is rendered.
      expect(screen.getAllByText(/view original/i)).toHaveLength(1)
      await userEvent.click(screen.getByRole('button', { name: 'Cook & enjoy!' }))
      expect(screen.getAllByText(/view original/i)).toHaveLength(2)
    })

    it('renders "From HelloFresh" for hellofresh source_type', () => {
      renderPage()
      // 'hellofresh' is in the display-name map so the text is "From HelloFresh"
      expect(screen.getAllByText(/from hellofresh/i).length).toBeGreaterThan(0)
    })
  })

  describe('"I cooked this" button', () => {
    it('calls useCookRecipe when clicked', async () => {
      renderPage()
      const btn = screen.getByRole('button', { name: /i cooked this/i })
      await userEvent.click(btn)
      await waitFor(() => expect(mockCookMutateAsync).toHaveBeenCalledTimes(1))
      expect(mockCookMutateAsync).toHaveBeenCalledWith({ recipeId: 'recipe-1' })
    })

    it('shows times_cooked pill', () => {
      renderPage()
      expect(screen.getByText(/cooked 3×/i)).toBeInTheDocument()
    })
  })

  describe('"Add to plan" sheet', () => {
    it('opens AddToPlanSheet when "Add to plan" is clicked', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: /add to plan/i }))
      await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    })

    it('calls useCreatePlanEntry when Add is confirmed in sheet', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: /add to plan/i }))
      await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())

      await userEvent.click(screen.getByRole('button', { name: /^add$/i }))
      await waitFor(() => expect(mockCreateEntryMutateAsync).toHaveBeenCalledTimes(1))

      const call = mockCreateEntryMutateAsync.mock.calls[0][0]
      expect(call.recipe_id).toBe('recipe-1')
      expect(call.meal_type).toBe('dinner')
      expect(typeof call.date).toBe('string')
    })

    it('shows confirmation banner after successful plan entry', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: /add to plan/i }))
      await waitFor(() => screen.getByRole('dialog'))
      await userEvent.click(screen.getByRole('button', { name: /^add$/i }))
      await waitFor(() =>
        expect(screen.getByText(/added to/i)).toBeInTheDocument()
      )
    })
  })

  describe('SourceLine absent when source_url is null', () => {
    it('renders no source attribution when source_url is null', async () => {
      const useRecipesModule = await import('../api/hooks/useRecipes')
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      vi.mocked(useRecipesModule.useRecipe).mockReturnValueOnce({
        data: {
          id: 'recipe-1',
          name: 'Manual Recipe',
          source_type: 'manual',
          source_url: null,
          source_image: null,
          steps: ['Step 1.'],
          notes: null,
          tags: [],
          cook_time_minutes: null,
          prep_time_minutes: null,
          base_servings: 4,
          times_cooked: 0,
          is_persisted: true,
          variation_groups: null,
          nutritional_info: null,
          ingredients: [],
        },
        isLoading: false,
        isError: false,
      } as any) // eslint-disable-line @typescript-eslint/no-explicit-any

      renderPage()
      expect(screen.queryByText(/view original/i)).not.toBeInTheDocument()
    })
  })

  describe('RatingLine', () => {
    it('shows the gate message when user has never cooked (no cook history)', () => {
      renderPage()
      expect(
        screen.getByText(/ratings open up after the first cook/i)
      ).toBeInTheDocument()
    })

    it('shows inline stars when user has cook history but no rating', async () => {
      const engagementModule = await import('../api/hooks/useRecipeEngagement')
      vi.mocked(engagementModule.useCookHistory).mockReturnValueOnce({
        data: [{ id: 'ev-1', user_id: 'user-1', recipe_id: 'recipe-1', cooked_at: '2026-11-10T10:00:00Z', meal_plan_entry_id: null, notes: null }],
      } as any) // eslint-disable-line @typescript-eslint/no-explicit-any

      renderPage()
      await waitFor(() =>
        expect(screen.getByText(/you've cooked this\. rate it\?/i)).toBeInTheDocument()
      )
      expect(screen.getByRole('radiogroup', { name: /rating/i })).toBeInTheDocument()
    })

    it('shows the user\'s rating when myRelation has a non-null rating', async () => {
      const engagementModule = await import('../api/hooks/useRecipeEngagement')
      vi.mocked(engagementModule.useMyRecipeRelation).mockReturnValueOnce({
        data: { rating: 4, is_bookmarked: false, is_liked: false, rating_photos: null, rating_comment: null, menu_id: null },
        isLoading: false,
      } as any) // eslint-disable-line @typescript-eslint/no-explicit-any

      renderPage()
      expect(screen.getByText(/your rating/i)).toBeInTheDocument()
    })
  })

  describe('JustCookedStrip', () => {
    it('replaces ActionBar with JustCookedStrip after a successful cook', async () => {
      renderPage()
      expect(screen.getByRole('button', { name: /i cooked this/i })).toBeInTheDocument()

      await userEvent.click(screen.getByRole('button', { name: /i cooked this/i }))
      await waitFor(() =>
        expect(screen.getByRole('radiogroup', { name: /rating/i })).toBeInTheDocument()
      )
      expect(screen.queryByRole('button', { name: /i cooked this/i })).not.toBeInTheDocument()
    })

    it('"Not now" returns the ActionBar without calling rateRecipe', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: /i cooked this/i }))
      await waitFor(() =>
        expect(screen.getByRole('button', { name: /not now/i })).toBeInTheDocument()
      )
      await userEvent.click(screen.getByRole('button', { name: /not now/i }))
      await waitFor(() =>
        expect(screen.getByRole('button', { name: /i cooked this/i })).toBeInTheDocument()
      )
      expect(mockRateMutateAsync).not.toHaveBeenCalled()
    })

    it('a star tap calls rateRecipe with the merged relation', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: /i cooked this/i }))
      await waitFor(() =>
        expect(screen.getByRole('radiogroup', { name: /rating/i })).toBeInTheDocument()
      )
      const stars = screen.getByRole('radiogroup').querySelectorAll('button')
      await userEvent.click(stars[4]) // star 5

      await waitFor(() => expect(mockRateMutateAsync).toHaveBeenCalledTimes(1))
      const call = mockRateMutateAsync.mock.calls[0][0]
      expect(call.rating).toBe(5)
      expect(call.recipeId).toBe('recipe-1')
      expect(call.currentRelation).toBeDefined()
    })

    it('ActionBar returns after the thanks delay', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: /i cooked this/i }))
      await waitFor(() =>
        expect(screen.getByRole('radiogroup', { name: /rating/i })).toBeInTheDocument()
      )
      const stars = screen.getByRole('radiogroup').querySelectorAll('button')
      await userEvent.click(stars[2]) // star 3

      await waitFor(() =>
        expect(screen.getByText(/thanks\. rated 3 stars/i)).toBeInTheDocument()
      )
      // ActionBar not yet restored
      expect(screen.queryByRole('button', { name: /i cooked this/i })).not.toBeInTheDocument()

      vi.advanceTimersByTime(2000)
      await waitFor(() =>
        expect(screen.getByRole('button', { name: /i cooked this/i })).toBeInTheDocument()
      )
    })
  })
})
