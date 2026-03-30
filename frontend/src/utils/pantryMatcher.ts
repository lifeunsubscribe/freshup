import type { RecipeIngredientResponse, InventoryItemListResponse } from '../api/types'

/**
 * Normalizes ingredient names for matching
 * - Converts to lowercase
 * - Trims whitespace
 *
 * Phase 1: Simple name-based presence check (not quantity-based)
 */
function normalizeIngredientName(name: string): string {
  return name.toLowerCase().trim()
}

/**
 * Tokenizes an ingredient name into individual words
 * Splits on spaces, hyphens, and other delimiters
 * Filters out empty strings
 *
 * Examples:
 * - "all-purpose flour" -> ["all", "purpose", "flour"]
 * - "olive oil" -> ["olive", "oil"]
 * - "rice" -> ["rice"]
 */
function tokenizeIngredientName(name: string): string[] {
  return name
    .split(/[\s\-_/]+/) // Split on space, hyphen, underscore, slash
    .filter((word) => word.length > 0)
}

/**
 * Checks if an ingredient name matches an inventory item name
 * Uses word-boundary matching to prevent false positives
 * (e.g., "rice" should NOT match "licorice")
 *
 * Matching strategy:
 * 1. Exact match after normalization
 * 2. Word-boundary match: all words from shorter name must appear in longer name
 *
 * Examples:
 * - "flour" matches "all-purpose flour" ✓ (flour is a word in the longer name)
 * - "rice" does NOT match "licorice" ✗ (rice is not a separate word)
 * - "olive oil" matches "extra virgin olive oil" ✓ (both words present)
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

  // Word-boundary matching: tokenize both names and check if all words
  // from the shorter name appear as complete words in the longer name
  const ingredientTokens = tokenizeIngredientName(normalizedIngredient)
  const inventoryTokens = tokenizeIngredientName(normalizedInventory)

  // Check if all tokens from the shorter name are present in the longer name
  // This handles cases like "flour" matching "all-purpose flour"
  const shorterTokens = ingredientTokens.length <= inventoryTokens.length ? ingredientTokens : inventoryTokens
  const longerTokens = ingredientTokens.length <= inventoryTokens.length ? inventoryTokens : ingredientTokens

  // All words from shorter name must be present in longer name
  return shorterTokens.every((token) => longerTokens.includes(token))
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
