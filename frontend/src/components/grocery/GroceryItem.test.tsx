import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import GroceryItem from './GroceryItem'
import type { GroceryItemResponse } from '../../api/types'

// Mock the API hooks
vi.mock('../../api', () => ({
  usePurchaseGroceryItem: vi.fn(),
  useUnpurchaseGroceryItem: vi.fn(),
  useHaveGroceryItem: vi.fn(),
}))

import { useHaveGroceryItem, usePurchaseGroceryItem, useUnpurchaseGroceryItem } from '../../api'

describe('GroceryItem', () => {
  let queryClient: QueryClient
  let purchaseMutate: ReturnType<typeof vi.fn>
  let unpurchaseMutate: ReturnType<typeof vi.fn>
  let haveMutate: ReturnType<typeof vi.fn>

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    purchaseMutate = vi.fn()
    unpurchaseMutate = vi.fn()

    vi.mocked(usePurchaseGroceryItem).mockReturnValue({
      mutate: purchaseMutate,
    } as any)

    vi.mocked(useUnpurchaseGroceryItem).mockReturnValue({
      mutate: unpurchaseMutate,
    } as any)

    haveMutate = vi.fn()
    vi.mocked(useHaveGroceryItem).mockReturnValue({
      mutate: haveMutate,
    } as any)
  })

  const renderWithProviders = (ui: React.ReactElement) => {
    return render(
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
      </MemoryRouter>
    )
  }

  const createMockItem = (
    overrides?: Partial<GroceryItemResponse>
  ): GroceryItemResponse => ({
    id: 'item-1',
    item_name: 'Olive oil',
    quantity: 1,
    unit: 'bottle',
    source: 'manual',
    added_by: 'user-1',
    date_added: '2026-03-23T10:00:00Z',
    purchased: false,
    purchased_by: null,
    purchased_date: null,
    target_store: null,
    ...overrides,
  })

  describe('Visual States', () => {
    it('renders unchecked state correctly', () => {
      const item = createMockItem()
      renderWithProviders(<GroceryItem item={item} />)

      // Item name visible and not struck through
      const itemText = screen.getByText(/Olive oil/)
      expect(itemText).toBeInTheDocument()
      expect(itemText.className).not.toContain('line-through')
      expect(itemText.className).toContain('text-text-primary')

      // Quantity visible
      expect(screen.getByText(/1 bottle/)).toBeInTheDocument()

      // Checkbox not filled
      const checkbox = screen.getByRole('button', {
        name: /Mark Olive oil as purchased/,
      })
      expect(checkbox).toBeInTheDocument()
      expect(checkbox).toHaveAttribute('aria-pressed', 'false')

      // No purchaser name shown
      expect(screen.queryByText(/Sarah/)).not.toBeInTheDocument()
    })

    it('renders checked state correctly', () => {
      const item = createMockItem({
        purchased: true,
        purchased_by: 'user-2',
        purchased_date: '2026-03-23T11:00:00Z',
      })
      renderWithProviders(<GroceryItem item={item} purchaserName="Sarah" />)

      // Item name struck through with tertiary color
      const itemText = screen.getByText(/Olive oil/)
      expect(itemText.className).toContain('line-through')
      expect(itemText.className).toContain('text-text-tertiary')

      // Checkbox filled (aria-pressed true)
      const checkbox = screen.getByRole('button', {
        name: /Unmark Olive oil as purchased/,
      })
      expect(checkbox).toHaveAttribute('aria-pressed', 'true')

      // Purchaser name shown
      expect(screen.getByText('Sarah')).toBeInTheDocument()
    })

    it('does not show purchaser name when not provided', () => {
      const item = createMockItem({
        purchased: true,
        purchased_by: 'user-2',
        purchased_date: '2026-03-23T11:00:00Z',
      })
      renderWithProviders(<GroceryItem item={item} />)

      // No purchaser name shown
      expect(screen.queryByText(/Sarah/)).not.toBeInTheDocument()
    })
  })

  describe('Context Chips', () => {
    it('renders "manual" chip for manual source', () => {
      const item = createMockItem({ source: 'manual' })
      renderWithProviders(<GroceryItem item={item} />)

      expect(screen.getByText('manual')).toBeInTheDocument()
    })

    it('renders "recipe" chip for recipe source', () => {
      const item = createMockItem({ source: 'recipe' })
      renderWithProviders(<GroceryItem item={item} />)

      expect(screen.getByText('recipe')).toBeInTheDocument()
    })

    it('renders "staple restock" chip for low_stock source', () => {
      const item = createMockItem({ source: 'low_stock' })
      renderWithProviders(<GroceryItem item={item} />)

      expect(screen.getByText('staple restock')).toBeInTheDocument()
    })
  })

  describe('What the item is for', () => {
    it('names the recipe a planned meal added it for, shortened, linking to it', () => {
      const item = createMockItem({
        source: 'meal_plan',
        recipes: [{ id: 'recipe-1', name: 'Cajun-Spiced Chickpea Power Bowls with Brussels Sprouts' }],
      })
      renderWithProviders(<GroceryItem item={item} />)

      const chip = screen.getByRole('link', { name: /^For Cajun-Spiced Chickpea Power Bowls with Brussels Sprouts/ })
      expect(chip).toHaveAttribute('href', '/recipes/recipe-1')
      expect(chip).toHaveTextContent('Cajun-Spiced Chickpea…')
      expect(screen.queryByText('meal plan')).not.toBeInTheDocument()
    })

    it('falls back to the single linked recipe', () => {
      const item = createMockItem({ source: 'meal_plan', linked_recipe: 'recipe-2', recipe_name: 'Fried Rice' })
      renderWithProviders(<GroceryItem item={item} />)

      expect(screen.getByRole('link', { name: /For Fried Rice/ })).toHaveAttribute('href', '/recipes/recipe-2')
    })

    it('leaves the recipe out when the list is already grouped under it', () => {
      const item = createMockItem({ source: 'meal_plan', recipes: [{ id: 'r', name: 'Gochujang Shrimp Fried Rice' }] })
      renderWithProviders(<GroceryItem item={item} hideRecipe />)

      expect(screen.queryByRole('link')).not.toBeInTheDocument()
    })

    it('names the first of several recipes and counts the rest', () => {
      const item = createMockItem({
        source: 'meal_plan',
        recipes: [
          { id: 'a', name: 'Fried Rice' },
          { id: 'b', name: 'Tofu Bowl' },
          { id: 'c', name: 'Stew' },
        ],
      })
      renderWithProviders(<GroceryItem item={item} />)

      expect(screen.getByRole('link', { name: /^For Fried Rice and Tofu Bowl and Stew/ })).toHaveTextContent('Fried Rice')
      expect(screen.getByText('+2')).toBeInTheDocument()
    })

    it('shows who added it beneath the chip', () => {
      renderWithProviders(<GroceryItem item={createMockItem()} addedBy="Sarah" />)

      expect(screen.getByText('Added by Sarah')).toBeInTheDocument()
    })

    it('puts the amount in its own column, with short units and no "count"', () => {
      const { unmount } = renderWithProviders(
        <GroceryItem item={createMockItem({ quantity: 2, unit: 'teaspoon' })} />
      )
      expect(screen.getByTestId('grocery-amount')).toHaveTextContent('2 tsp')
      unmount()

      const second = renderWithProviders(<GroceryItem item={createMockItem({ quantity: 3, unit: 'count' })} />)
      expect(screen.getByTestId('grocery-amount')).toHaveTextContent(/^3$/)
      second.unmount()

      renderWithProviders(<GroceryItem item={createMockItem({ item_name: 'Salt', quantity: 0.001, unit: '' })} />)
      expect(screen.getByTestId('grocery-amount')).toHaveTextContent('to taste')
    })

    it('says "meal plan" for a planned item whose recipe is not known', () => {
      const item = createMockItem({ source: 'meal_plan', recipe_name: null })
      renderWithProviders(<GroceryItem item={item} />)

      expect(screen.getByText('meal plan')).toBeInTheDocument()
    })
  })

  describe('I have this', () => {
    it('takes an unbought item off the list', async () => {
      const user = userEvent.setup()
      renderWithProviders(<GroceryItem item={createMockItem()} />)

      await user.click(screen.getByRole('button', { name: 'I already have Olive oil' }))

      expect(haveMutate).toHaveBeenCalledWith('item-1', expect.anything())
      expect(purchaseMutate).not.toHaveBeenCalled()
    })

    it('is not offered on an item already bought', () => {
      renderWithProviders(<GroceryItem item={createMockItem({ purchased: true })} />)

      expect(screen.queryByRole('button', { name: /I already have/ })).not.toBeInTheDocument()
    })

    it('says so when it fails', async () => {
      haveMutate.mockImplementation((_id, options) => options.onError(new Error('nope')))
      const user = userEvent.setup()
      renderWithProviders(<GroceryItem item={createMockItem()} />)

      await user.click(screen.getByRole('button', { name: 'I already have Olive oil' }))

      expect(await screen.findByText(/Could not take this off the list|nope/)).toBeInTheDocument()
    })
  })

  describe('Checkbox Interaction', () => {
    it('calls purchase mutation when unchecked item is clicked', async () => {
      const user = userEvent.setup()
      const item = createMockItem({ purchased: false })
      renderWithProviders(<GroceryItem item={item} />)

      const checkbox = screen.getByRole('button', {
        name: /Mark Olive oil as purchased/,
      })
      await user.click(checkbox)

      expect(purchaseMutate).toHaveBeenCalledWith(
        'item-1',
        expect.objectContaining({
          onError: expect.any(Function),
        })
      )
      expect(unpurchaseMutate).not.toHaveBeenCalled()
    })

    it('calls unpurchase mutation when checked item is clicked', async () => {
      const user = userEvent.setup()
      const item = createMockItem({ purchased: true })
      renderWithProviders(<GroceryItem item={item} />)

      const checkbox = screen.getByRole('button', {
        name: /Unmark Olive oil as purchased/,
      })
      await user.click(checkbox)

      expect(unpurchaseMutate).toHaveBeenCalledWith(
        'item-1',
        expect.objectContaining({
          onError: expect.any(Function),
        })
      )
      expect(purchaseMutate).not.toHaveBeenCalled()
    })

    it('supports keyboard interaction with Enter key', async () => {
      const user = userEvent.setup()
      const item = createMockItem({ purchased: false })
      renderWithProviders(<GroceryItem item={item} />)

      const checkbox = screen.getByRole('button', {
        name: /Mark Olive oil as purchased/,
      })
      checkbox.focus()
      await user.keyboard('{Enter}')

      expect(purchaseMutate).toHaveBeenCalledWith(
        'item-1',
        expect.objectContaining({
          onError: expect.any(Function),
        })
      )
    })

    it('supports keyboard interaction with Space key', async () => {
      const user = userEvent.setup()
      const item = createMockItem({ purchased: false })
      renderWithProviders(<GroceryItem item={item} />)

      const checkbox = screen.getByRole('button', {
        name: /Mark Olive oil as purchased/,
      })
      checkbox.focus()
      await user.keyboard(' ')

      expect(purchaseMutate).toHaveBeenCalledWith(
        'item-1',
        expect.objectContaining({
          onError: expect.any(Function),
        })
      )
    })
  })

  describe('Error Handling', () => {
    it('displays error banner when purchaseMutation fails', async () => {
      const purchaseMutate = vi.fn((_id, options) => {
        // Simulate mutation failure by calling onError
        if (options?.onError) {
          options.onError()
        }
      })

      vi.mocked(usePurchaseGroceryItem).mockReturnValue({
        mutate: purchaseMutate,
        isError: false,
        isPending: false,
      } as any)

      const item = createMockItem({ purchased: false })
      renderWithProviders(<GroceryItem item={item} />)

      // Click checkbox to trigger error
      const checkbox = screen.getByRole('button', {
        name: /Mark Olive oil as purchased/,
      })
      fireEvent.click(checkbox)

      // Error banner should appear
      await waitFor(() => {
        const errorBanner = screen.getByRole('alert')
        expect(errorBanner).toBeInTheDocument()
        expect(errorBanner).toHaveTextContent(
          'Failed to mark item as purchased. Please try again.'
        )
      })
    })

    it('displays error banner when unpurchaseMutation fails', async () => {
      const unpurchaseMutate = vi.fn((_id, options) => {
        // Simulate mutation failure by calling onError
        if (options?.onError) {
          options.onError()
        }
      })

      vi.mocked(useUnpurchaseGroceryItem).mockReturnValue({
        mutate: unpurchaseMutate,
        isError: false,
        isPending: false,
      } as any)

      const item = createMockItem({ purchased: true })
      renderWithProviders(<GroceryItem item={item} />)

      // Click checkbox to trigger error
      const checkbox = screen.getByRole('button', {
        name: /Unmark Olive oil as purchased/,
      })
      fireEvent.click(checkbox)

      // Error banner should appear
      await waitFor(() => {
        const errorBanner = screen.getByRole('alert')
        expect(errorBanner).toBeInTheDocument()
        expect(errorBanner).toHaveTextContent(
          'Failed to unmark item. Please try again.'
        )
      })
    })

    it('auto-dismisses error message after 5 seconds', async () => {
      vi.useFakeTimers()

      const purchaseMutate = vi.fn((_id, options) => {
        // Simulate mutation failure by calling onError
        if (options?.onError) {
          options.onError()
        }
      })

      vi.mocked(usePurchaseGroceryItem).mockReturnValue({
        mutate: purchaseMutate,
        isError: false,
        isPending: false,
      } as any)

      const item = createMockItem({ purchased: false })
      renderWithProviders(<GroceryItem item={item} />)

      // Click checkbox to trigger error
      const checkbox = screen.getByRole('button', {
        name: /Mark Olive oil as purchased/,
      })
      // Fake timers are installed, so waitFor cannot poll — it relies on real
      // timers that are frozen here. act() flushes the state update instead.
      act(() => {
        fireEvent.click(checkbox)
      })

      // Error should be visible initially
      expect(screen.getByRole('alert')).toBeInTheDocument()

      // Fast-forward 5 seconds
      act(() => {
        vi.advanceTimersByTime(5000)
      })

      // Error should be dismissed
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()

      vi.useRealTimers()
    })

    it('clears error when user retries the action', async () => {
      const user = userEvent.setup()
      let shouldError = true

      const purchaseMutate = vi.fn((_id, options) => {
        // First call fails, second succeeds
        if (shouldError && options?.onError) {
          options.onError()
        }
      })

      vi.mocked(usePurchaseGroceryItem).mockReturnValue({
        mutate: purchaseMutate,
        isError: false,
        isPending: false,
      } as any)

      const item = createMockItem({ purchased: false })
      renderWithProviders(<GroceryItem item={item} />)

      // Click checkbox to trigger first error
      const checkbox = screen.getByRole('button', {
        name: /Mark Olive oil as purchased/,
      })
      await user.click(checkbox)

      // Error should be visible
      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument()
      })

      // Next click should succeed (no error)
      shouldError = false
      await user.click(checkbox)

      // Error should be cleared immediately (component clears error in handleCheckboxClick)
      await waitFor(() => {
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      })
    })
  })

  describe('Pending State', () => {
    it('disables button when purchaseMutation is pending', () => {
      vi.mocked(usePurchaseGroceryItem).mockReturnValue({
        mutate: purchaseMutate,
        isPending: true,
        isError: false,
      } as any)

      const item = createMockItem({ purchased: false })
      renderWithProviders(<GroceryItem item={item} />)

      const checkbox = screen.getByRole('button', {
        name: /Mark Olive oil as purchased/,
      })
      expect(checkbox).toBeDisabled()
    })

    it('disables button when unpurchaseMutation is pending', () => {
      vi.mocked(useUnpurchaseGroceryItem).mockReturnValue({
        mutate: unpurchaseMutate,
        isPending: true,
        isError: false,
      } as any)

      const item = createMockItem({ purchased: true })
      renderWithProviders(<GroceryItem item={item} />)

      const checkbox = screen.getByRole('button', {
        name: /Unmark Olive oil as purchased/,
      })
      expect(checkbox).toBeDisabled()
    })
  })

  describe('Accessibility', () => {
    it('has proper ARIA label for unchecked state', () => {
      const item = createMockItem({ purchased: false })
      renderWithProviders(<GroceryItem item={item} />)

      const checkbox = screen.getByRole('button', {
        name: /Mark Olive oil as purchased/,
      })
      expect(checkbox).toHaveAttribute('aria-pressed', 'false')
    })

    it('has proper ARIA label for checked state', () => {
      const item = createMockItem({ purchased: true })
      renderWithProviders(<GroceryItem item={item} />)

      const checkbox = screen.getByRole('button', {
        name: /Unmark Olive oil as purchased/,
      })
      expect(checkbox).toHaveAttribute('aria-pressed', 'true')
    })

    it('is keyboard focusable', () => {
      const item = createMockItem()
      renderWithProviders(<GroceryItem item={item} />)

      const checkbox = screen.getByRole('button', { name: 'Mark Olive oil as purchased' })
      expect(checkbox).toHaveAttribute('type', 'button')
    })
  })

  describe('Touch Target', () => {
    it('has minimum 44px height for mobile usability', () => {
      const item = createMockItem()
      const { container } = renderWithProviders(<GroceryItem item={item} />)

      const itemContainer = container.querySelector('.min-h-\\[44px\\]')
      expect(itemContainer).toBeInTheDocument()
    })
  })

  describe('Visual Design Specs', () => {
    it('checkbox has correct size (19px)', () => {
      const item = createMockItem()
      const { container } = renderWithProviders(<GroceryItem item={item} />)

      // Check for 19px width and height classes
      const checkbox = container.querySelector('.w-\\[19px\\].h-\\[19px\\]')
      expect(checkbox).toBeInTheDocument()
    })

    it('checkbox has correct border radius (6px)', () => {
      const item = createMockItem()
      const { container } = renderWithProviders(<GroceryItem item={item} />)

      // Check for 6px border radius
      const checkbox = container.querySelector('.rounded-\\[6px\\]')
      expect(checkbox).toBeInTheDocument()
    })

    it('checked checkbox has olive background', () => {
      const item = createMockItem({ purchased: true })
      const { container } = renderWithProviders(<GroceryItem item={item} />)

      const checkbox = container.querySelector('.bg-olive')
      expect(checkbox).toBeInTheDocument()
    })

    it('unchecked checkbox has white background with warm border', () => {
      const item = createMockItem({ purchased: false })
      const { container } = renderWithProviders(<GroceryItem item={item} />)

      const checkbox = container.querySelector('.bg-white.border-warm-border')
      expect(checkbox).toBeInTheDocument()
    })
  })

  describe('Item Name Formatting', () => {
    it('displays item name and quantity', () => {
      const item = createMockItem({
        item_name: 'Tomatoes',
        quantity: 3,
        unit: 'lbs',
      })
      renderWithProviders(<GroceryItem item={item} />)

      // Both should be present
      expect(screen.getByText('Tomatoes')).toBeInTheDocument()
      expect(screen.getByTestId('grocery-amount')).toHaveTextContent('3 lb')
    })

    it('handles decimal quantities', () => {
      const item = createMockItem({
        item_name: 'Flour',
        quantity: 2.5,
        unit: 'cups',
      })
      renderWithProviders(<GroceryItem item={item} />)

      expect(screen.getByTestId('grocery-amount')).toHaveTextContent('2.5 cup')
    })
  })
})
