import type { GroceryItemResponse } from '../../api/types'

/** The items of one planned meal, or the items that belong to no meal. */
export interface RecipeGroup {
  /** The planned meal's id, or 'other' for items no meal put on the list. */
  key: string
  /** The recipe's name; null for the "other" group. */
  recipeName: string | null
  /** The day of the planned meal, YYYY-MM-DD, when known. */
  planDate: string | null
  items: GroceryItemResponse[]
}

/**
 * Group a grocery list by the planned meal each item is for: meals in the
 * order they will be cooked, then everything that is on the list for its own
 * sake. Two plannings of the same recipe stay separate, since each has its
 * own day.
 */
export function groupByRecipe(items: GroceryItemResponse[]): RecipeGroup[] {
  const meals = new Map<string, RecipeGroup>()
  const other: GroceryItemResponse[] = []

  for (const item of items) {
    if (!item.recipe_name) {
      other.push(item)
      continue
    }
    const key = item.linked_meal_plan_entry ?? `recipe-${item.linked_recipe ?? item.recipe_name}`
    const group = meals.get(key)
    if (group) {
      group.items.push(item)
    } else {
      meals.set(key, {
        key,
        recipeName: item.recipe_name,
        planDate: item.plan_date ?? null,
        items: [item],
      })
    }
  }

  const ordered = [...meals.values()].sort((a, b) => {
    // Undated meals (already eaten, or their plan entry is gone) go last.
    if (a.planDate === b.planDate) return (a.recipeName ?? '').localeCompare(b.recipeName ?? '')
    if (a.planDate === null) return 1
    if (b.planDate === null) return -1
    return a.planDate < b.planDate ? -1 : 1
  })
  return other.length > 0
    ? [...ordered, { key: 'other', recipeName: null, planDate: null, items: other }]
    : ordered
}

export type GroceryView = 'by-recipe' | 'by-store' | 'flat'

/**
 * The view the list opens in. Stores only help once something has a store;
 * recipes only help once a planned meal has put something on the list.
 */
export function defaultGroceryView(items: GroceryItemResponse[]): GroceryView {
  if (items.some((item) => item.target_store)) return 'by-store'
  if (items.some((item) => item.recipe_name)) return 'by-recipe'
  return 'flat'
}
