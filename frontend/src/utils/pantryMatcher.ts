import type { RecipeIngredientResponse, InventoryItemListResponse } from '../api/types'

/**
 * Normalizes ingredient names for matching
 * - Converts to lowercase
 * - Trims whitespace
 * - Removes common variations (e.g., "all-purpose flour" -> "flour")
 *
 * Phase 1: Simple name-based presence check (not quantity-based)
 */
function normalizeIngredientName(name: string): string {
  return name.toLowerCase().trim()
}

/**
 * Checks if an ingredient name matches an inventory item name
 * Phase 1: Simple case-insensitive match
 * Future: Could enhance with fuzzy matching, synonyms, etc.
 */
function ingredientMatchesInventoryItem(
  ingredientName: string,
  inventoryItemName: string
): boolean {
  const normalizedIngredient = normalizeIngredientName(ingredientName)
  const normalizedInventory = normalizeIngredientName(inventoryItemName)

  // Exact match after normalization
  if (normalizedIngredient === normalizedInventory) {
    return true
  }

  // Check if one contains the other (e.g., "flour" matches "all-purpose flour")
  // This handles common variations where inventory items are more specific
  if (
    normalizedInventory.includes(normalizedIngredient) ||
    normalizedIngredient.includes(normalizedInventory)
  ) {
    return true
  }

  return false
}

export interface IngredientStockStatus {
  ingredient: RecipeIngredientResponse
  inStock: boolean
  matchedInventoryItem?: InventoryItemListResponse
}

export interface PantryCheckResult {
  inStock: IngredientStockStatus[]
  outOfStock: IngredientStockStatus[]
  totalCount: number
  inStockCount: number
}

/**
 * Checks recipe ingredients against pantry inventory
 * Returns stock status for each ingredient
 *
 * @param ingredients - Recipe ingredients to check
 * @param inventoryItems - Current pantry inventory
 * @returns Categorized stock status with counts
 */
export function checkIngredientAvailability(
  ingredients: RecipeIngredientResponse[],
  inventoryItems: InventoryItemListResponse[]
): PantryCheckResult {
  const inStock: IngredientStockStatus[] = []
  const outOfStock: IngredientStockStatus[] = []

  for (const ingredient of ingredients) {
    // Find matching inventory item (first match wins)
    const matchedItem = inventoryItems.find((item) =>
      ingredientMatchesInventoryItem(ingredient.ingredient_name, item.name)
    )

    if (matchedItem) {
      inStock.push({
        ingredient,
        inStock: true,
        matchedInventoryItem: matchedItem,
      })
    } else {
      outOfStock.push({
        ingredient,
        inStock: false,
      })
    }
  }

  return {
    inStock,
    outOfStock,
    totalCount: ingredients.length,
    inStockCount: inStock.length,
  }
}

/**
 * Checks if ALL ingredients in a recipe are available in pantry
 * Used for "All in stock" badge on recipe cards
 */
export function areAllIngredientsInStock(
  ingredients: RecipeIngredientResponse[],
  inventoryItems: InventoryItemListResponse[]
): boolean {
  if (ingredients.length === 0) {
    return false // No ingredients = can't make it
  }

  return ingredients.every((ingredient) =>
    inventoryItems.some((item) =>
      ingredientMatchesInventoryItem(ingredient.ingredient_name, item.name)
    )
  )
}
