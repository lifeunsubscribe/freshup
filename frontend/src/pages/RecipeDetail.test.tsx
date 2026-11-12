import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, render, screen, waitFor } from '@testing-library/react'
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
const mockRateMutateAsync = vi.fn().mockResolvedValue({})
const mockCreateEntryMutateAsync = vi.fn().mockResolvedValue({})

vi.mock('../api/hooks/useRecipes', () => ({
  useRateRecipe: vi.fn(() => ({ mutateAsync: mockRateMutateAsync })),
  useRecipe: vi.fn(() => ({
    data: {
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
    },
    isLoading: false,
    isError: false,
  })),
  useRecipeOutcomes: vi.fn(() => ({ data: [], isLoading: false, isError: false })),
}))

vi.mock('../api/hooks/useRecipeEngagement', () => ({
  useMyRecipeRelation: () => ({
    data: {
      is_bookmarked: false,
      is_liked: false,
      rating: null,
      rating_photos: null,
      rating_comment: null,
      menu_id: null,
    },
    isLoading: false,
  }),
  useToggleBookmark: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useToggleLike: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useCookRecipe: () => ({ mutateAsync: mockCookMutateAsync }),
  useCookHistory: vi.fn(() => ({ data: [] })),
}))

vi.mock('../api/hooks/usePlan', () => ({
  useCreatePlanEntry: () => ({ mutateAsync: mockCreateEntryMutateAsync }),
}))

vi.mock('../api/hooks/useInventory', () => ({
  useInventoryList: vi.fn(() => ({ data: [], isLoading: false, isError: false })),
}))

vi.mock('../utils/pantryMatcher', () => ({
  checkIngredientAvailability: vi.fn(() => ({
    inStock: [],
    outOfStock: [],
    totalCount: 0,
    inStockCount: 0,
  })),
}))

vi.mock('../api/hooks/useGrocery', () => ({
  useCreateGroceryItem: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useGroceryList: () => ({ data: [], refetch: vi.fn().mockResolvedValue({ data: [] }) }),
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
  mockRateMutateAsync.mockReset().mockResolvedValue({})
  mockCreateEntryMutateAsync.mockReset().mockResolvedValue({})
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

  describe('PantryCheck card', () => {
    const mockIngredient = {
      id: 'ing-1',
      recipe_id: 'recipe-1',
      ingredient_name: 'flour',
      quantity: 2,
      unit: 'cup',
      variation_group: null,
      variation_diet: null,
      is_optional: false,
      step_index: null,
    }

    beforeEach(async () => {
      const matcher = await import('../utils/pantryMatcher')
      vi.mocked(matcher.checkIngredientAvailability).mockReturnValue({
        inStock: [],
        outOfStock: [{ ingredient: mockIngredient, inStock: false }],
        totalCount: 1,
        inStockCount: 0,
      })
      const useRecipesModule = await import('../api/hooks/useRecipes')
      vi.mocked(useRecipesModule.useRecipe).mockReturnValue({
        data: {
          id: 'recipe-1',
          name: 'Mushroom Risotto',
          source_type: 'manual',
          source_url: null,
          source_image: null,
          steps: [],
          notes: null,
          tags: [],
          cook_time_minutes: null,
          prep_time_minutes: null,
          base_servings: 4,
          times_cooked: 0,
          is_persisted: true,
          variation_groups: null,
          nutritional_info: null,
          ingredients: [mockIngredient],
        },
        isLoading: false,
        isError: false,
      } as any) // eslint-disable-line @typescript-eslint/no-explicit-any
    })

    it('shows k-of-n pantry card text', () => {
      renderPage()
      expect(screen.getByText('0 of 1 in the pantry.')).toBeInTheDocument()
    })

    it('opens the pantry review sheet when the card is tapped', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: /tap to review/i }))
      await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    })

    it('shows pantry unavailable text when inventory fails to load', async () => {
      const useInventoryModule = await import('../api/hooks/useInventory')
      vi.mocked(useInventoryModule.useInventoryList).mockReturnValueOnce({
        data: [],
        isLoading: false,
        isError: true,
      } as any) // eslint-disable-line @typescript-eslint/no-explicit-any
      renderPage()
      expect(screen.getByText('Pantry unavailable right now.')).toBeInTheDocument()
    })

    it('does not open the pantry sheet when inventory fails', async () => {
      const useInventoryModule = await import('../api/hooks/useInventory')
      vi.mocked(useInventoryModule.useInventoryList).mockReturnValueOnce({
        data: [],
        isLoading: false,
        isError: true,
      } as any) // eslint-disable-line @typescript-eslint/no-explicit-any
      renderPage()
      expect(screen.queryByRole('button', { name: /tap to review/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  describe('Cook-tab header: timer slot vs bookmark/heart', () => {
    it('shows bookmark and heart on the Ingredients tab (default)', () => {
      renderPage()
      expect(screen.getByRole('button', { name: /bookmark recipe/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /like recipe/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /new timer/i })).not.toBeInTheDocument()
    })

    it('shows the timer button and no bookmark/heart on the Cook tab', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: 'Cook & enjoy!' }))
      expect(screen.getByRole('button', { name: /new timer/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /bookmark recipe/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /like recipe/i })).not.toBeInTheDocument()
    })

    it('restores bookmark and heart when switching back from Cook to Ingredients', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: 'Cook & enjoy!' }))
      await userEvent.click(screen.getByRole('button', { name: 'Ingredients' }))
      expect(screen.getByRole('button', { name: /bookmark recipe/i })).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /new timer/i })).not.toBeInTheDocument()
    })

    it('opens NewTimerSheet when the timer button is clicked', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: 'Cook & enjoy!' }))
      await userEvent.click(screen.getByRole('button', { name: /new timer/i }))
      await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
      expect(screen.getByText(/new timer/i)).toBeInTheDocument()
    })
  })

  describe('RatingLine', () => {
    it('shows the muted gate sentence when user has never cooked (cookHistory empty)', () => {
      // Default mock has useCookHistory returning []
      renderPage()
      expect(
        screen.getByText(/ratings open up after the first cook/i)
      ).toBeInTheDocument()
    })

    it('shows inline stars when user has cook history and no rating', async () => {
      const engagement = await import('../api/hooks/useRecipeEngagement')
      vi.mocked(engagement.useCookHistory).mockReturnValueOnce({
        data: [{ id: 'ev-1', user_id: 'user-1', recipe_id: 'recipe-1', cooked_at: '2026-01-01', meal_plan_entry_id: null, notes: null }],
      } as any) // eslint-disable-line @typescript-eslint/no-explicit-any
      renderPage()
      expect(screen.getByRole('radiogroup', { name: /rating, 1 to 5/i })).toBeInTheDocument()
    })
  })

  describe('JustCookedStrip', () => {
    it('replaces the action bar after a successful cook', async () => {
      renderPage()
      expect(screen.getByRole('button', { name: /i cooked this/i })).toBeInTheDocument()
      expect(screen.queryByRole('radiogroup', { name: /rating, 1 to 5/i })).not.toBeInTheDocument()

      await userEvent.click(screen.getByRole('button', { name: /i cooked this/i }))
      await waitFor(() =>
        expect(screen.getByRole('radiogroup', { name: /rating, 1 to 5/i })).toBeInTheDocument()
      )
      expect(screen.queryByRole('button', { name: /i cooked this/i })).not.toBeInTheDocument()
    })

    it('"Not now" restores the action bar without calling useRateRecipe', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: /i cooked this/i }))
      await waitFor(() => screen.getByRole('button', { name: /not now/i }))

      await userEvent.click(screen.getByRole('button', { name: /not now/i }))
      await waitFor(() =>
        expect(screen.getByRole('button', { name: /i cooked this/i })).toBeInTheDocument()
      )
      expect(mockRateMutateAsync).not.toHaveBeenCalled()
    })

    it('tapping a star posts to useRateRecipe and restores action bar after success', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: /i cooked this/i }))
      await waitFor(() => screen.getByRole('radiogroup', { name: /rating, 1 to 5/i }))

      await userEvent.click(screen.getByRole('radio', { name: /4 stars/i }))
      await waitFor(() => expect(mockRateMutateAsync).toHaveBeenCalledTimes(1))

      const call = mockRateMutateAsync.mock.calls[0][0]
      expect(call.recipeId).toBe('recipe-1')
      expect(call.rating).toBe(4)
      expect(call.currentRelation.is_bookmarked).toBe(false)
      expect(call.currentRelation.is_liked).toBe(false)
    })

    it('shows the gate sentence when useRateRecipe rejects with 403', async () => {
      const gateError = Object.assign(new Error('Rate after cooking'), { status: 403 })
      mockRateMutateAsync.mockRejectedValueOnce(gateError)

      renderPage()
      await userEvent.click(screen.getByRole('button', { name: /i cooked this/i }))
      await waitFor(() => screen.getByRole('radiogroup'))

      await userEvent.click(screen.getByRole('radio', { name: /2 stars/i }))
      await waitFor(() =>
        // Two elements: RatingLine (cookCount=0 never-cooked gate) + JustCookedStrip (403 gate state)
        expect(
          screen.getAllByText(/ratings open up after the first cook/i)
        ).toHaveLength(2)
      )
      // The strip is still visible (no retry, no dismiss)
      expect(screen.queryByRole('button', { name: /i cooked this/i })).not.toBeInTheDocument()
    })
  })

  describe('OutcomesSection', () => {
    it('renders the "How it turned out" section on the Ingredients tab', () => {
      renderPage()
      expect(screen.getByText(/how it turned out/i)).toBeInTheDocument()
    })

    it('renders the "How it turned out" section on the Cook tab', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: 'Cook & enjoy!' }))
      expect(screen.getByText(/how it turned out/i)).toBeInTheDocument()
    })

    it('renders the "How it turned out" section on the Nutrition tab', async () => {
      renderPage()
      await userEvent.click(screen.getByRole('button', { name: 'Nutrition' }))
      expect(screen.getByText(/how it turned out/i)).toBeInTheDocument()
    })

    it('shows empty state when outcomes list is empty', () => {
      renderPage()
      expect(screen.getByText('Nobody here has cooked this yet.')).toBeInTheDocument()
    })
  })

  describe('transient-message timers', () => {
    beforeEach(() => {
      // shouldAdvanceTime keeps waitFor polling and userEvent working while
      // still allowing manual advances via vi.advanceTimersByTime.
      vi.useFakeTimers({ shouldAdvanceTime: true })
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('clears plan-confirmation timer on unmount so no pending timers remain', async () => {
      const errorSpy = vi.spyOn(console, 'error')

      const { unmount } = renderPage()

      // Trigger the plan-confirmation flow
      await userEvent.click(screen.getByRole('button', { name: /add to plan/i }))
      await waitFor(() => screen.getByRole('dialog'))
      await userEvent.click(screen.getByRole('button', { name: /^add$/i }))
      await waitFor(() => screen.getByText(/added to/i))

      // Unmount before the 4 s timeout fires — cleanup effect must cancel it
      unmount()

      expect(vi.getTimerCount()).toBe(0)
      expect(errorSpy).not.toHaveBeenCalledWith(
        expect.stringContaining('unmounted'),
        expect.anything()
      )
      errorSpy.mockRestore()
    })

    it('plan-confirmation message auto-clears after 4 seconds on a mounted page', async () => {
      renderPage()

      await userEvent.click(screen.getByRole('button', { name: /add to plan/i }))
      await waitFor(() => screen.getByRole('dialog'))
      await userEvent.click(screen.getByRole('button', { name: /^add$/i }))
      await waitFor(() => screen.getByText(/added to/i))

      act(() => vi.advanceTimersByTime(4000))

      expect(screen.queryByText(/added to/i)).not.toBeInTheDocument()
    })
  })
})
