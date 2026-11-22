import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, within } from '@testing-library/react'
import Grocery from './Grocery'
import { renderWithProviders } from '../test/renderWithProviders'
import type { GroceryItemResponse } from '../api/types'

let items: GroceryItemResponse[] = []

vi.mock('../api', () => ({
  useGroceryList: () => ({ data: items, isLoading: false, error: null }),
  useGroceryListByStore: () => ({
    data: { stores: [], unassigned: items },
    isLoading: false,
    error: null,
  }),
  useCreateGroceryItem: () => ({ mutate: vi.fn(), isPending: false }),
  useUsers: () => ({ data: [{ id: 'user-1', name: 'Sarah' }] }),
  usePurchaseGroceryItem: () => ({ mutate: vi.fn() }),
  useUnpurchaseGroceryItem: () => ({ mutate: vi.fn() }),
  useHaveGroceryItem: () => ({ mutate: vi.fn() }),
}))

function item(name: string, overrides: Partial<GroceryItemResponse> = {}): GroceryItemResponse {
  return {
    id: name,
    item_name: name,
    quantity: 1,
    unit: 'unit',
    source: 'manual',
    added_by: 'user-1',
    date_added: '2026-11-21T10:00:00Z',
    purchased: false,
    purchased_by: null,
    purchased_date: null,
    target_store: null,
    ...overrides,
  }
}

const pressed = (name: string) =>
  screen.getByRole('button', { name }).getAttribute('aria-pressed') === 'true'

describe('Grocery page views', () => {
  beforeEach(() => {
    items = []
  })

  it('opens by recipe when a planned meal put items on the list, grouping them under it', () => {
    items = [
      item('Dish soap'),
      item('Shrimp', {
        source: 'meal_plan',
        linked_meal_plan_entry: 'entry-1',
        recipe_name: 'Gochujang Shrimp Fried Rice',
        plan_date: '2026-11-21',
      }),
    ]

    renderWithProviders(<Grocery />)

    expect(pressed('By Recipe')).toBe(true)
    const meal = within(screen.getByRole('region', { name: 'Gochujang Shrimp Fried Rice' }))
    expect(meal.getByText('Saturday dinner · Nov 21')).toBeInTheDocument()
    expect(meal.getByText('Shrimp')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Other items' })).getByText('Dish soap')).toBeInTheDocument()
  })

  it('opens as the plain list, not by store, while nothing has a store or a recipe', () => {
    items = [item('Dish soap')]

    renderWithProviders(<Grocery />)

    expect(pressed('All Items')).toBe(true)
    expect(pressed('By Store')).toBe(false)
  })

  it('opens by store once an item has one', () => {
    items = [item('Milk', { target_store: 'store-1' })]

    renderWithProviders(<Grocery />)

    expect(pressed('By Store')).toBe(true)
  })

  it('keeps the view the user picks', () => {
    items = [item('Dish soap')]

    renderWithProviders(<Grocery />)
    fireEvent.click(screen.getByRole('button', { name: 'By Store' }))

    expect(pressed('By Store')).toBe(true)
    expect(pressed('All Items')).toBe(false)
  })

  it('names the recipe on each item in the plain list', () => {
    items = [
      item('Shrimp', {
        source: 'meal_plan',
        linked_meal_plan_entry: 'entry-1',
        linked_recipe: 'recipe-1',
        recipe_name: 'Gochujang Shrimp Fried Rice',
        plan_date: '2026-11-21',
      }),
    ]

    renderWithProviders(<Grocery />)
    fireEvent.click(screen.getByRole('button', { name: 'All Items' }))

    expect(screen.getByRole('link', { name: /For Gochujang Shrimp Fried Rice/ })).toHaveAttribute(
      'href',
      '/recipes/recipe-1'
    )
    // Who added it sits under the chip, not on a line of its own.
    expect(screen.getByText('Added by Sarah')).toBeInTheDocument()
  })
})
