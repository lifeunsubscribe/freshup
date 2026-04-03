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
 * Lookup table for irregular plurals that cannot be handled by pattern rules.
 * Maps both singular and plural forms to their canonical singular form.
 *
 * Categories:
 * - Invariant plurals (same singular/plural): fish, sheep, deer
 * - Vowel changes: goose→geese, mouse→mice, tooth→teeth
 * - Complete transformations: person→people, child→children
 * - -man/-men patterns: man→men, woman→women
 *
 * All entries normalize to the singular form for consistent matching.
 */
const IRREGULAR_PLURALS = new Map<string, string>([
  // Invariant plurals (same singular and plural form)
  ['fish', 'fish'],
  ['sheep', 'sheep'],
  ['deer', 'deer'],
  ['moose', 'moose'],
  ['salmon', 'salmon'],
  ['trout', 'trout'],
  ['shrimp', 'shrimp'],
  ['cod', 'cod'],
  ['squid', 'squid'],

  // Vowel-change plurals (bidirectional: plural→singular, singular→singular)
  ['goose', 'goose'],
  ['geese', 'goose'],
  ['mouse', 'mouse'],
  ['mice', 'mouse'],
  ['tooth', 'tooth'],
  ['teeth', 'tooth'],
  ['foot', 'foot'],
  ['feet', 'foot'],
  ['louse', 'louse'],
  ['lice', 'louse'],

  // Complete transformations
  ['person', 'person'],
  ['people', 'person'],
  ['child', 'child'],
  ['children', 'child'],
  ['ox', 'ox'],
  ['oxen', 'ox'],

  // -man/-men patterns (common in compound food terms)
  ['man', 'man'],
  ['men', 'man'],
  ['woman', 'woman'],
  ['women', 'woman'],

  // Latin/Greek plurals (common in food context)
  ['octopus', 'octopus'],
  ['octopi', 'octopus'],
  ['octopuses', 'octopus'],
  ['cactus', 'cactus'],
  ['cacti', 'cactus'],
  ['cactuses', 'cactus'],
  ['fungus', 'fungus'],
  ['fungi', 'fungus'],
  ['funguses', 'fungus'],

  // -f/-fe → -ves patterns that need special handling
  // (Pattern rule handles most, but these override if needed)
  ['knife', 'knife'],
  ['knives', 'knife'],
  ['life', 'life'],
  ['lives', 'life'],
  ['wife', 'wife'],
  ['wives', 'wife'],
  ['leaf', 'leaf'],
  ['leaves', 'leaf'],
  ['loaf', 'loaf'],
  ['loaves', 'loaf'],
  ['calf', 'calf'],
  ['calves', 'calf'],
  ['half', 'half'],
  ['halves', 'half'],
  ['shelf', 'shelf'],
  ['shelves', 'shelf'],
  ['thief', 'thief'],
  ['thieves', 'thief'],
  ['wolf', 'wolf'],
  ['wolves', 'wolf'],
])

/**
 * Normalizes a word to its singular/base form to handle plural matching
 * Applies simple English pluralization rules for common food ingredients
 *
 * Examples:
 * - "eggs" -> "egg"
 * - "tomatoes" -> "tomato"
 * - "berries" -> "berry"
 * - "cherries" -> "cherry"
 * - "geese" -> "goose" (irregular)
 * - "fish" -> "fish" (invariant)
 *
 * Note: This uses a hybrid approach:
 * 1. First checks lookup table for irregular plurals
 * 2. Falls back to pattern-based rules for regular plurals
 */
function normalizeWordForPlurals(word: string): string {
  // Skip very short words (likely not plurals, e.g., "as", "is")
  if (word.length <= 2) {
    return word
  }

  // Check irregular plurals lookup table first (before pattern rules)
  // This handles edge cases like fish/fish, geese/goose, people/person, etc.
  const irregularForm = IRREGULAR_PLURALS.get(word)
  if (irregularForm !== undefined) {
    return irregularForm
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
 * Tokenizes an ingredient name into individual words and normalizes each for plural matching
 *
 * Process:
 * 1. Splits on spaces, hyphens, underscores, and slashes
 * 2. Filters out empty strings
 * 3. Applies plural normalization to EACH token independently
 *
 * This tokenization strategy enables compound ingredient matching with irregular plurals:
 * - "wild goose" → ["wild", "goose"]
 * - "wild geese" → ["wild", "goose"] (geese normalized to goose)
 * - Both normalize to the same token array, enabling matching
 *
 * Examples:
 * - "all-purpose flour" -> ["all", "purpose", "flour"]
 * - "olive oil" -> ["olive", "oil"]
 * - "rice" -> ["rice"]
 * - "cherry tomatoes" -> ["cherry", "tomato"] (tomatoes → tomato)
 * - "eggs" -> ["egg"] (eggs → egg)
 * - "roasted geese" -> ["roasted", "goose"] (geese → goose via irregular plural)
 * - "smoked fish" -> ["smoked", "fish"] (fish invariant plural)
 */
function tokenizeIngredientName(name: string): string[] {
  return name
    .split(/[\s\-_/]+/) // Split on space, hyphen, underscore, slash
    .filter((word) => word.length > 0)
    .map((word) => normalizeWordForPlurals(word)) // Normalize EACH word for plurals independently
}

/**
 * Checks if an ingredient name matches an inventory item name
 * Uses asymmetric word-boundary matching with plural normalization
 *
 * Matching strategy:
 * 1. Exact match after normalization
 * 2. Asymmetric word-boundary match: all recipe tokens must appear in inventory tokens
 *    (but NOT vice versa - this prevents "flour" in inventory matching "almond flour" in recipe)
 * 3. Plural normalization: Applied to EACH token independently, enabling compound word matching
 *
 * Compound word handling:
 * - Tokenization splits multi-word ingredients and normalizes each word
 * - "wild goose" → ["wild", "goose"] matches "wild geese" → ["wild", "goose"]
 * - "roasted geese" → ["roasted", "goose"] matches "roasted goose" → ["roasted", "goose"]
 * - This enables irregular plural matching in compound ingredients
 *
 * Examples:
 * - Recipe "flour" matches inventory "all-purpose flour" ✓ (inventory has the required ingredient)
 * - Recipe "almond flour" does NOT match inventory "flour" ✗ (inventory lacks "almond")
 * - Recipe "rice" does NOT match inventory "licorice" ✗ (rice is not a separate word)
 * - Recipe "olive oil" matches inventory "extra virgin olive oil" ✓ (both words present)
 * - Recipe "egg" matches inventory "eggs" ✓ (plural normalization)
 * - Recipe "cherry tomatoes" matches inventory "cherry tomato" ✓ (bidirectional plural matching)
 * - Recipe "wild goose" matches inventory "wild geese" ✓ (compound irregular plural)
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
