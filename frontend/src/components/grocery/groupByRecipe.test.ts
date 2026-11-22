import { describe, it, expect } from 'vitest'
import { defaultGroceryView, groupByRecipe } from './groupByRecipe'
import type { GroceryItemResponse } from '../../api/types'

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

const forMeal = (name: string, entry: string, recipe: string, day: string | null) =>
  item(name, { source: 'meal_plan', linked_meal_plan_entry: entry, recipe_name: recipe, plan_date: day })

describe('groupByRecipe', () => {
  it('puts each planned meal\'s items together, meals in the order they are cooked, the rest last', () => {
    const groups = groupByRecipe([
      item('Dish soap'),
      forMeal('Shrimp', 'entry-sat', 'Fried Rice', '2026-11-21'),
      forMeal('Tofu', 'entry-thu', 'Teriyaki Tofu', '2026-11-19'),
      forMeal('Rice', 'entry-sat', 'Fried Rice', '2026-11-21'),
      item('Paper towels'),
    ])

    expect(groups.map((g) => [g.recipeName, g.planDate, g.items.map((i) => i.item_name)])).toEqual([
      ['Teriyaki Tofu', '2026-11-19', ['Tofu']],
      ['Fried Rice', '2026-11-21', ['Shrimp', 'Rice']],
      [null, null, ['Dish soap', 'Paper towels']],
    ])
  })

  it('keeps two plannings of the same recipe apart', () => {
    const groups = groupByRecipe([
      forMeal('Rice', 'entry-1', 'Fried Rice', '2026-11-21'),
      forMeal('Rice again', 'entry-2', 'Fried Rice', '2026-11-25'),
    ])

    expect(groups.map((g) => g.items.map((i) => i.item_name))).toEqual([['Rice'], ['Rice again']])
  })

  it('puts a meal with no day after the dated ones', () => {
    const groups = groupByRecipe([
      forMeal('Old', 'entry-gone', 'Stew', null),
      forMeal('New', 'entry-1', 'Fried Rice', '2026-11-21'),
    ])

    expect(groups.map((g) => g.recipeName)).toEqual(['Fried Rice', 'Stew'])
  })

  it('has no "other" group when every item belongs to a meal, and no groups for an empty list', () => {
    expect(groupByRecipe([forMeal('Rice', 'entry-1', 'Fried Rice', '2026-11-21')])).toHaveLength(1)
    expect(groupByRecipe([])).toEqual([])
  })
})

describe('groupByRecipe with items shared by several dinners', () => {
  it('puts them in one group at the top', () => {
    const groups = groupByRecipe([
      forMeal('Shrimp', 'entry-sat', 'Fried Rice', '2026-11-21'),
      item('Garlic', { source: 'meal_plan', recipe_names: ['Fried Rice', 'Tofu Bowl'] }),
      item('Dish soap'),
    ])

    expect(groups.map((g) => [g.recipeName, g.items.map((i) => i.item_name)])).toEqual([
      ['For several dinners', ['Garlic']],
      ['Fried Rice', ['Shrimp']],
      [null, ['Dish soap']],
    ])
  })

  it('opens the list by recipe when only shared items came from the plan', () => {
    expect(defaultGroceryView([item('Garlic', { recipe_names: ['A', 'B'] })])).toBe('by-recipe')
  })
})

describe('defaultGroceryView', () => {
  it('opens by store only once an item has a store', () => {
    expect(defaultGroceryView([item('Milk', { target_store: 'store-1' }), forMeal('Rice', 'e', 'Fried Rice', null)])).toBe('by-store')
  })

  it('opens by recipe when a planned meal has put something on the list', () => {
    expect(defaultGroceryView([item('Milk'), forMeal('Rice', 'e', 'Fried Rice', null)])).toBe('by-recipe')
  })

  it('opens as the plain list otherwise', () => {
    expect(defaultGroceryView([item('Milk')])).toBe('flat')
    expect(defaultGroceryView([])).toBe('flat')
  })
})
