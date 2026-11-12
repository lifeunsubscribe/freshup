import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import PantryReviewSheet from './PantryReviewSheet'
import type { PantryCheckResult } from '../../utils/pantryMatcher'
import type { RecipeIngredientResponse } from '../../api/types'

// ── Grocery mock state ────────────────────────────────────────────────────────

const mockMutateAsync = vi.fn()
const mockRefetch = vi.fn()

vi.mock('../../api/hooks/useGrocery', () => ({
  useCreateGroceryItem: () => ({ mutateAsync: mockMutateAsync }),
  useGroceryList: () => ({ data: [], refetch: mockRefetch }),
}))

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeIngredient(overrides: Partial<RecipeIngredientResponse> = {}): RecipeIngredientResponse {
  return {
    id: 'ing-1',
    recipe_id: 'recipe-1',
    ingredient_name: 'flour',
    quantity: 2,
    unit: 'cup',
    variation_group: null,
    variation_diet: null,
    is_optional: false,
    step_index: null,
    ...overrides,
  }
}

const flour = makeIngredient({ id: 'ing-1', ingredient_name: 'flour', quantity: 2, unit: 'cup' })
const sugar = makeIngredient({ id: 'ing-2', ingredient_name: 'sugar', quantity: 1, unit: 'cup' })
const salt = makeIngredient({ id: 'ing-3', ingredient_name: 'salt', quantity: 1, unit: 'tsp' })
const vanilla = makeIngredient({ id: 'ing-4', ingredient_name: 'vanilla extract', quantity: 1, unit: 'tsp', is_optional: true })

const ingredients: RecipeIngredientResponse[] = [flour, sugar, salt, vanilla]

function makeStockStatus(inStockIds: string[], outOfStockIds: string[]): PantryCheckResult {
  const all = ingredients.filter(i => inStockIds.includes(i.id) || outOfStockIds.includes(i.id))
  const inStock = all.filter(i => inStockIds.includes(i.id)).map(i => ({ ingredient: i, inStock: true as const }))
  const outOfStock = all.filter(i => outOfStockIds.includes(i.id)).map(i => ({ ingredient: i, inStock: false as const }))
  return { inStock, outOfStock, totalCount: all.length, inStockCount: inStock.length }
}

let queryClient: QueryClient

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

function renderSheet(props: Partial<React.ComponentProps<typeof PantryReviewSheet>> = {}) {
  const defaults = {
    open: true,
    onClose: vi.fn(),
    ingredients,
    stockStatus: makeStockStatus(['ing-1', 'ing-4'], ['ing-2', 'ing-3']),
    servingsMultiplier: 1,
    onSuccess: vi.fn(),
  }
  return render(<PantryReviewSheet {...defaults} {...props} />, { wrapper })
}

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  mockMutateAsync.mockReset().mockResolvedValue({})
  mockRefetch.mockReset().mockResolvedValue({ data: [] })
})

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('PantryReviewSheet', () => {
  describe('initial row state', () => {
    it('renders a checkbox row for each ingredient', () => {
      renderSheet()
      const checkboxes = screen.getAllByRole('checkbox')
      // flour (inStock), sugar (outOfStock), salt (outOfStock), vanilla (optional)
      expect(checkboxes).toHaveLength(4)
    })

    it('outOfStock rows start checked', () => {
      renderSheet()
      // sugar and salt are outOfStock → checked
      const sugarCb = screen.getByRole('checkbox', { name: /sugar/i })
      const saltCb = screen.getByRole('checkbox', { name: /salt/i })
      expect(sugarCb).toBeChecked()
      expect(saltCb).toBeChecked()
    })

    it('inStock rows start unchecked', () => {
      renderSheet()
      const flourCb = screen.getByRole('checkbox', { name: /flour/i })
      expect(flourCb).not.toBeChecked()
    })

    it('optional ingredients appear last', () => {
      renderSheet()
      const labels = screen.getAllByRole('checkbox').map(cb => {
        const label = cb.closest('label')
        return label?.textContent ?? ''
      })
      // vanilla (optional) should be after flour, sugar, salt
      const vanillaIndex = labels.findIndex(t => t.includes('vanilla'))
      const saltIndex = labels.findIndex(t => t.includes('salt'))
      expect(vanillaIndex).toBeGreaterThan(saltIndex)
    })

    it('shows (optional) label next to optional ingredients', () => {
      renderSheet()
      expect(screen.getByText('(optional)')).toBeInTheDocument()
    })

    it('labels inStock rows as "In the pantry"', () => {
      renderSheet()
      expect(screen.getAllByText('In the pantry').length).toBeGreaterThan(0)
    })

    it('labels outOfStock rows as "Needed"', () => {
      renderSheet()
      expect(screen.getAllByText('Needed').length).toBeGreaterThan(0)
    })
  })

  describe('scaled amounts', () => {
    it('shows scaled quantity in the row', () => {
      // flour is 2 cups × 2 multiplier = 4 cups
      renderSheet({ servingsMultiplier: 2 })
      expect(screen.getByText(/4 cup/i)).toBeInTheDocument()
    })
  })

  describe('footer button', () => {
    it('shows checked count in footer button', () => {
      // 2 outOfStock items checked by default (sugar, salt)
      renderSheet()
      expect(screen.getByRole('button', { name: /add 2 to the grocery list/i })).toBeInTheDocument()
    })

    it('footer button is disabled when no items are checked', () => {
      // All inStock, nothing checked initially
      renderSheet({
        stockStatus: makeStockStatus(['ing-1', 'ing-2', 'ing-3'], []),
        ingredients: [flour, sugar, salt],
      })
      const btn = screen.getByRole('button', { name: /add 0/i })
      expect(btn).toBeDisabled()
    })

    it('toggling a row updates the footer count', async () => {
      renderSheet()
      // Start: 2 checked (sugar, salt). Uncheck sugar.
      await userEvent.click(screen.getByRole('checkbox', { name: /sugar/i }))
      expect(screen.getByRole('button', { name: /add 1 to the grocery list/i })).toBeInTheDocument()
    })

    it('checking an inStock row increases the count', async () => {
      renderSheet()
      // Start: 2 checked. Check flour (inStock).
      await userEvent.click(screen.getByRole('checkbox', { name: /flour/i }))
      expect(screen.getByRole('button', { name: /add 3 to the grocery list/i })).toBeInTheDocument()
    })
  })

  describe('submitting', () => {
    it('calls mutateAsync for each checked item', async () => {
      renderSheet()
      await userEvent.click(screen.getByRole('button', { name: /add 2 to the grocery list/i }))
      await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(2))
    })

    it('calls onSuccess and onClose on full success', async () => {
      const onSuccess = vi.fn()
      const onClose = vi.fn()
      renderSheet({ onSuccess, onClose })
      await userEvent.click(screen.getByRole('button', { name: /add 2 to the grocery list/i }))
      await waitFor(() => expect(onSuccess).toHaveBeenCalledWith(2))
      expect(onClose).toHaveBeenCalled()
    })

    it('skips items already on the unpurchased grocery list', async () => {
      // sugar is already on the list
      mockRefetch.mockResolvedValue({ data: [{ item_name: 'sugar' }] })
      const onSuccess = vi.fn()
      renderSheet({ onSuccess })
      await userEvent.click(screen.getByRole('button', { name: /add 2 to the grocery list/i }))
      await waitFor(() => expect(onSuccess).toHaveBeenCalled())
      // only salt should be added (sugar was already on the list)
      expect(mockMutateAsync).toHaveBeenCalledTimes(1)
      const call = mockMutateAsync.mock.calls[0][0]
      expect(call.item_name).toBe('salt')
    })

    it('keeps sheet open with failed rows marked on partial failure', async () => {
      // sugar fails, salt succeeds
      mockMutateAsync.mockImplementation(({ item_name }: { item_name: string }) => {
        if (item_name === 'sugar') return Promise.reject(new Error('failed'))
        return Promise.resolve({})
      })
      const onClose = vi.fn()
      renderSheet({ onClose })
      await userEvent.click(screen.getByRole('button', { name: /add 2 to the grocery list/i }))
      await waitFor(() => expect(screen.getByRole('button', { name: /retry 1/i })).toBeInTheDocument())
      expect(onClose).not.toHaveBeenCalled()
    })

    it('preserves sentinel quantity (0.001) without scaling when servingsMultiplier is 2', async () => {
      const sentinelIng = makeIngredient({ id: 'ing-5', ingredient_name: 'spice', quantity: 0.001, unit: 'tsp' })
      const sentinelStockStatus: PantryCheckResult = {
        inStock: [],
        outOfStock: [{ ingredient: sentinelIng, inStock: false }],
        totalCount: 1,
        inStockCount: 0,
      }
      renderSheet({
        ingredients: [sentinelIng],
        stockStatus: sentinelStockStatus,
        servingsMultiplier: 2,
      })
      await userEvent.click(screen.getByRole('button', { name: /add 1 to the grocery list/i }))
      await waitFor(() => expect(mockMutateAsync).toHaveBeenCalledTimes(1))
      const call = mockMutateAsync.mock.calls[0][0]
      expect(call.quantity).toBe(0.001)
    })

    it('shows "Failed" label on failed rows', async () => {
      mockMutateAsync.mockImplementation(({ item_name }: { item_name: string }) => {
        if (item_name === 'sugar') return Promise.reject(new Error('failed'))
        return Promise.resolve({})
      })
      renderSheet()
      await userEvent.click(screen.getByRole('button', { name: /add 2 to the grocery list/i }))
      await waitFor(() => expect(screen.getByText('Failed')).toBeInTheDocument())
    })
  })

  describe('closed state', () => {
    it('renders nothing when open is false', () => {
      const { container } = renderSheet({ open: false })
      expect(container.firstChild).toBeNull()
    })
  })
})
