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
 * Normalizes a word to its singular/base form to handle plural matching
 * Applies simple English pluralization rules for common food ingredients
 *
 * Examples:
 * - "eggs" -> "egg"
 * - "tomatoes" -> "tomato"
 * - "berries" -> "berry"
 * - "cherries" -> "cherry"
 *
 * Note: This is a lightweight approach focused on common food terms.
 * It handles regular plurals (-s, -es) and common irregular patterns (-ies).
 */
function normalizeWordForPlurals(word: string): string {
  // Skip very short words (likely not plurals, e.g., "as", "is")
  if (word.length <= 2) {
    return word
  }

  // Handle -ies -> -y (berries -> berry, cherries -> cherry)
  if (word.endsWith('ies') && word.length > 3) {
    // Check if the letter before 'ies' is a consonant (not a vowel)
    const beforeIes = word[word.length - 4]
    if (beforeIes && !'aeiou'.includes(beforeIes)) {
      return word.slice(0, -3) + 'y'
    }
  }

  // Handle -oes -> -o (tomatoes -> tomato, potatoes -> potato)
  if (word.endsWith('oes') && word.length > 3) {
    return word.slice(0, -2)
  }

  // Handle -ves -> -f (loaves -> loaf, shelves -> shelf, halves -> half)
  if (word.endsWith('ves') && word.length > 3) {
    // Use -f as default (covers food items like "loaf", "half", "shelf")
    return word.slice(0, -3) + 'f'
  }

  // Handle -ses -> -s (glasses -> glass, but not -ases like bases -> base)
  if (word.endsWith('ses') && word.length > 4) {
    // Check if it's -ases pattern (bases -> base, not bas)
    if (word.endsWith('ases')) {
      return word.slice(0, -1) // Remove just 's' to get 'base'
    }
    return word.slice(0, -2)
  }

  // Handle regular -es plurals for words ending in s, x, z, ch, sh
  // (dishes -> dish, peaches -> peach)
  if (word.endsWith('es') && word.length > 3) {
    const base = word.slice(0, -2)
    // Only remove 'es' if the base ends in s, x, z, or has ch/sh pattern
    if (base.endsWith('s') || base.endsWith('x') || base.endsWith('z') ||
        base.endsWith('ch') || base.endsWith('sh')) {
      return base
    }
  }

  // Handle regular -s plural (eggs -> egg, carrots -> carrot)
  if (word.endsWith('s') && word.length > 3) {
    // Don't strip 's' from words that naturally end in 's' (e.g., "grass")
    // This is a simple heuristic: if removing 's' creates a very short word, keep it
    const base = word.slice(0, -1)
    // Keep words ending in 'ss' (e.g., grass, bass)
    if (word.endsWith('ss')) {
      return word
    }
    return base
  }

  return word
}

/**
 * Tokenizes an ingredient name into individual words
 * Splits on spaces, hyphens, and other delimiters
 * Filters out empty strings
 * Normalizes each token for plural matching
 *
 * Examples:
 * - "all-purpose flour" -> ["all", "purpose", "flour"]
 * - "olive oil" -> ["olive", "oil"]
 * - "rice" -> ["rice"]
 * - "cherry tomatoes" -> ["cherry", "tomato"]
 * - "eggs" -> ["egg"]
 */
function tokenizeIngredientName(name: string): string[] {
  return name
    .split(/[\s\-_/]+/) // Split on space, hyphen, underscore, slash
    .filter((word) => word.length > 0)
    .map((word) => normalizeWordForPlurals(word)) // Normalize for plurals
}

/**
 * Checks if an ingredient name matches an inventory item name
 * Uses asymmetric word-boundary matching with plural normalization
 *
 * Matching strategy:
 * 1. Exact match after normalization
 * 2. Asymmetric word-boundary match: all recipe tokens must appear in inventory tokens
 *    (but NOT vice versa - this prevents "flour" in inventory matching "almond flour" in recipe)
 * 3. Plural normalization: "egg" matches "eggs", "tomato" matches "tomatoes", etc.
 *
 * Examples:
 * - Recipe "flour" matches inventory "all-purpose flour" ✓ (inventory has the required ingredient)
 * - Recipe "almond flour" does NOT match inventory "flour" ✗ (inventory lacks "almond")
 * - Recipe "rice" does NOT match inventory "licorice" ✗ (rice is not a separate word)
 * - Recipe "olive oil" matches inventory "extra virgin olive oil" ✓ (both words present)
 * - Recipe "egg" matches inventory "eggs" ✓ (plural normalization)
 * - Recipe "cherry tomatoes" matches inventory "cherry tomato" ✓ (bidirectional plural matching)
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

  // Asymmetric word-boundary matching: all recipe tokens must be present in inventory
  // This ensures recipe requirements are a subset of what's available in inventory
  const ingredientTokens = tokenizeIngredientName(normalizedIngredient)
  const inventoryTokens = tokenizeIngredientName(normalizedInventory)

  // All words from recipe ingredient must be present in inventory item
  // (one-directional check prevents false positives)
  return ingredientTokens.every((token) => inventoryTokens.includes(token))
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
