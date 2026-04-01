import { describe, it, expect } from 'vitest'
import { checkIngredientAvailability, areAllIngredientsInStock } from '../pantryMatcher'
import type { RecipeIngredientResponse, InventoryItemListResponse } from '../../api/types'

describe('pantryMatcher', () => {
  const createIngredient = (overrides: Partial<RecipeIngredientResponse> = {}): RecipeIngredientResponse => ({
    id: 'ing-1',
    recipe_id: 'recipe-1',
    ingredient_name: 'flour',
    quantity: 1,
    unit: 'cup',
    step_index: null,
    ...overrides,
  })

  const createInventoryItem = (overrides: Partial<InventoryItemListResponse> = {}): InventoryItemListResponse => ({
    id: 'inv-1',
    name: 'flour',
    quantity: 2,
    unit: 'cup',
    category: 'baking',
    storage_location: 'pantry',
    date_added: '2026-03-01',
    expiration_date: null,
    is_staple: true,
    shareability: 'shared',
    ...overrides,
  })

  describe('checkIngredientAvailability', () => {
    it('identifies ingredients in stock with exact name match', () => {
      const ingredients = [
        createIngredient({ id: 'ing-1', ingredient_name: 'flour' }),
        createIngredient({ id: 'ing-2', ingredient_name: 'sugar' }),
      ]

      const inventoryItems = [
        createInventoryItem({ id: 'inv-1', name: 'flour' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
      expect(result.totalCount).toBe(2)
      expect(result.inStock).toHaveLength(1)
      expect(result.outOfStock).toHaveLength(1)
      expect(result.inStock[0].ingredient.ingredient_name).toBe('flour')
      expect(result.outOfStock[0].ingredient.ingredient_name).toBe('sugar')
    })

    it('matches ingredients case-insensitively', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'Flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'flour' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
      expect(result.inStock[0].inStock).toBe(true)
    })

    it('matches ingredients with partial name match (contains)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'all-purpose flour' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
      expect(result.inStock[0].inStock).toBe(true)
      expect(result.inStock[0].matchedInventoryItem?.name).toBe('all-purpose flour')
    })

    it('does NOT match specific recipe ingredient with generic inventory (asymmetric)', () => {
      // Recipe needs "all-purpose flour" but inventory only has "flour"
      // This should NOT match to prevent false positives
      const ingredients = [
        createIngredient({ ingredient_name: 'all-purpose flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'flour' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(0)
      expect(result.outOfStock).toHaveLength(1)
      expect(result.outOfStock[0].ingredient.ingredient_name).toBe('all-purpose flour')
    })

    it('does NOT match "almond flour" recipe with "flour" inventory', () => {
      // This is the specific example from the issue
      const ingredients = [
        createIngredient({ ingredient_name: 'almond flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'flour' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(0)
      expect(result.outOfStock).toHaveLength(1)
      expect(result.outOfStock[0].ingredient.ingredient_name).toBe('almond flour')
    })

    it('returns all out of stock when inventory is empty', () => {
      const ingredients = [
        createIngredient({ id: 'ing-1', ingredient_name: 'flour' }),
        createIngredient({ id: 'ing-2', ingredient_name: 'sugar' }),
      ]

      const result = checkIngredientAvailability(ingredients, [])

      expect(result.inStockCount).toBe(0)
      expect(result.totalCount).toBe(2)
      expect(result.inStock).toHaveLength(0)
      expect(result.outOfStock).toHaveLength(2)
    })

    it('returns empty result when no ingredients', () => {
      const inventoryItems = [
        createInventoryItem({ name: 'flour' }),
      ]

      const result = checkIngredientAvailability([], inventoryItems)

      expect(result.inStockCount).toBe(0)
      expect(result.totalCount).toBe(0)
      expect(result.inStock).toHaveLength(0)
      expect(result.outOfStock).toHaveLength(0)
    })

    it('matches first inventory item found (first match wins)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ id: 'inv-1', name: 'flour' }),
        createInventoryItem({ id: 'inv-2', name: 'all-purpose flour' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
      expect(result.inStock[0].matchedInventoryItem?.id).toBe('inv-1')
    })

    it('handles whitespace in ingredient names', () => {
      const ingredients = [
        createIngredient({ ingredient_name: '  flour  ' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'flour' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    // False positive prevention tests
    it('does NOT match "rice" with "licorice" (prevents false positive)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'rice' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'licorice' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(0)
      expect(result.outOfStock).toHaveLength(1)
      expect(result.outOfStock[0].ingredient.ingredient_name).toBe('rice')
    })

    it('does NOT match "egg" with "eggplant" (prevents false positive)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'egg' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'eggplant' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(0)
      expect(result.outOfStock).toHaveLength(1)
    })

    it('does NOT match "oil" with "foil" (prevents false positive)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'oil' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'foil' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(0)
      expect(result.outOfStock).toHaveLength(1)
    })

    it('does NOT match "mint" with "peppermint" (prevents false positive)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'mint' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'peppermint' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(0)
      expect(result.outOfStock).toHaveLength(1)
    })

    // Valid multi-word matching (should still work)
    it('matches "olive oil" with "extra virgin olive oil"', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'olive oil' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'extra virgin olive oil' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
      expect(result.inStock[0].matchedInventoryItem?.name).toBe('extra virgin olive oil')
    })

    it('matches "soy sauce" with "low-sodium soy sauce"', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'soy sauce' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'low-sodium soy sauce' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    it('handles hyphenated ingredients correctly', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'all-purpose flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'all purpose flour' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    // Plural matching tests
    it('matches "egg" recipe with "eggs" inventory (plural normalization)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'egg' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'eggs' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
      expect(result.inStock[0].matchedInventoryItem?.name).toBe('eggs')
    })

    it('matches "eggs" recipe with "egg" inventory (bidirectional plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'eggs' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'egg' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
      expect(result.inStock[0].matchedInventoryItem?.name).toBe('egg')
    })

    it('matches "tomato" with "tomatoes" (-oes plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'tomato' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'tomatoes' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    it('matches "potato" with "potatoes" (-oes plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'potato' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'potatoes' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    it('matches "berry" with "berries" (-ies plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'berry' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'berries' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    it('matches "cherry" with "cherries" (-ies plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'cherry' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'cherries' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    it('matches "cherry tomato" with "cherry tomatoes" (multi-word plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'cherry tomato' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'cherry tomatoes' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
      expect(result.inStock[0].matchedInventoryItem?.name).toBe('cherry tomatoes')
    })

    it('matches "carrot" with "carrots" (regular -s plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'carrot' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'carrots' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    it('matches "peach" with "peaches" (-es plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'peach' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'peaches' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    it('matches "dish" with "dishes" (-es plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'dish' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'dishes' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    it('handles "glass noodles" correctly (word ending in ss)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'glass noodles' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'glass noodles' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    it('plural matching still prevents false positives (rice vs licorice)', () => {
      // Ensure plural normalization doesn't break existing false-positive prevention
      const ingredients = [
        createIngredient({ ingredient_name: 'rice' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'licorice' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(0)
      expect(result.outOfStock).toHaveLength(1)
    })

    it('plural matching maintains asymmetric behavior (almond flour vs flour)', () => {
      // Ensure plural normalization doesn't break asymmetric matching
      const ingredients = [
        createIngredient({ ingredient_name: 'almond flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'flour' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(0)
      expect(result.outOfStock).toHaveLength(1)
    })
  })

  describe('areAllIngredientsInStock', () => {
    it('returns true when all ingredients are in stock', () => {
      const ingredients = [
        createIngredient({ id: 'ing-1', ingredient_name: 'flour' }),
        createIngredient({ id: 'ing-2', ingredient_name: 'sugar' }),
      ]

      const inventoryItems = [
        createInventoryItem({ id: 'inv-1', name: 'flour' }),
        createInventoryItem({ id: 'inv-2', name: 'sugar' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(true)
    })

    it('returns false when some ingredients are missing', () => {
      const ingredients = [
        createIngredient({ id: 'ing-1', ingredient_name: 'flour' }),
        createIngredient({ id: 'ing-2', ingredient_name: 'sugar' }),
      ]

      const inventoryItems = [
        createInventoryItem({ id: 'inv-1', name: 'flour' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(false)
    })

    it('returns false when no ingredients are in stock', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'flour' }),
      ]

      const result = areAllIngredientsInStock(ingredients, [])

      expect(result).toBe(false)
    })

    it('returns false when recipe has no ingredients', () => {
      const inventoryItems = [
        createInventoryItem({ name: 'flour' }),
      ]

      const result = areAllIngredientsInStock([], inventoryItems)

      expect(result).toBe(false)
    })

    it('handles case-insensitive matching', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'Flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'flour' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(true)
    })

    it('handles partial name matching (generic recipe with specific inventory)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'all-purpose flour' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(true)
    })

    it('returns false when specific recipe ingredient does not match generic inventory (asymmetric)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'almond flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'flour' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(false)
    })

    // False positive prevention tests
    it('returns false when "rice" inventory does not match "licorice" requirement', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'rice' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'licorice' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(false)
    })

    it('returns false when "egg" inventory does not match "eggplant" requirement', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'egg' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'eggplant' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(false)
    })

    it('correctly matches multi-word ingredients with word-boundary logic', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'olive oil' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'extra virgin olive oil' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(true)
    })

    // Plural matching tests for areAllIngredientsInStock
    it('returns true when "egg" recipe matches "eggs" inventory (plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'egg' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'eggs' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(true)
    })

    it('returns true when "eggs" recipe matches "egg" inventory (bidirectional)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'eggs' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'egg' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(true)
    })

    it('returns true when "tomato" matches "tomatoes"', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'tomato' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'tomatoes' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(true)
    })

    it('returns true when "cherry tomato" matches "cherry tomatoes"', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'cherry tomato' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'cherry tomatoes' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(true)
    })

    it('returns true when all plural/singular matches are found', () => {
      const ingredients = [
        createIngredient({ id: 'ing-1', ingredient_name: 'egg' }),
        createIngredient({ id: 'ing-2', ingredient_name: 'tomatoes' }),
        createIngredient({ id: 'ing-3', ingredient_name: 'flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ id: 'inv-1', name: 'eggs' }),
        createInventoryItem({ id: 'inv-2', name: 'tomato' }),
        createInventoryItem({ id: 'inv-3', name: 'all-purpose flour' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(true)
    })
  })
})
