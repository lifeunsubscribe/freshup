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

    it('matches inventory items with more generic names', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'all-purpose flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'flour' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
      expect(result.inStock[0].inStock).toBe(true)
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

    it('handles partial name matching', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'flour' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'all-purpose flour' }),
      ]

      const result = areAllIngredientsInStock(ingredients, inventoryItems)

      expect(result).toBe(true)
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
  })
})
