import { describe, it, expect, vi, beforeEach } from 'vitest'
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

vi.mock('../api/hooks/useRecipes', () => ({
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
}))

vi.mock('../api/hooks/useRecipeEngagement', () => ({
  useMyRecipeRelation: () => ({
    data: { is_bookmarked: false, is_liked: false },
    isLoading: false,
  }),
  useToggleBookmark: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useToggleLike: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useCookRecipe: () => ({ mutateAsync: mockCookMutateAsync }),
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
})
