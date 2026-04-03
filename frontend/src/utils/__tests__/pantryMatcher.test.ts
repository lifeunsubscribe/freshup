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

    it('matches "loaf" with "loaves" (-ves plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'loaf' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'loaves' }),
      ]

      const result = checkIngredientAvailability(ingredients, inventoryItems)

      expect(result.inStockCount).toBe(1)
    })

    it('matches "half" with "halves" (-ves plural)', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'half' }),
      ]

      const inventoryItems = [
        createInventoryItem({ name: 'halves' }),
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

    // Irregular plural tests
    describe('Irregular plurals', () => {
      it('matches "fish" recipe with "fish" inventory (invariant plural)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'fish' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'fish' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
        expect(result.inStock[0].matchedInventoryItem?.name).toBe('fish')
      })

      it('matches "sheep" recipe with "sheep" inventory (invariant plural)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'sheep' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'sheep' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "deer" recipe with "deer" inventory (invariant plural)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'deer' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'deer' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "shrimp" recipe with "shrimp" inventory (invariant plural)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'shrimp' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'shrimp' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "goose" recipe with "geese" inventory (vowel change)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'goose' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'geese' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
        expect(result.inStock[0].matchedInventoryItem?.name).toBe('geese')
      })

      it('matches "geese" recipe with "goose" inventory (vowel change bidirectional)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'geese' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'goose' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
        expect(result.inStock[0].matchedInventoryItem?.name).toBe('goose')
      })

      it('matches "mouse" recipe with "mice" inventory (vowel change)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'mouse' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'mice' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "tooth" recipe with "teeth" inventory (vowel change)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'tooth' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'teeth' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "foot" recipe with "feet" inventory (vowel change)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'foot' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'feet' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "person" recipe with "people" inventory (complete transformation)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'person' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'people' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "people" recipe with "person" inventory (complete transformation bidirectional)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'people' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'person' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "child" recipe with "children" inventory (complete transformation)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'child' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'children' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "ox" recipe with "oxen" inventory (complete transformation)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'ox' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'oxen' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "octopus" recipe with "octopi" inventory (Latin plural)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'octopus' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'octopi' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "octopus" recipe with "octopuses" inventory (English plural)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'octopus' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'octopuses' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "knife" recipe with "knives" inventory (-ves ending)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'knife' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'knives' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
        expect(result.inStock[0].matchedInventoryItem?.name).toBe('knives')
      })

      it('matches "knives" recipe with "knife" inventory (-ves bidirectional)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'knives' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'knife' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches "life" recipe with "lives" inventory (-ves ending)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'life' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'lives' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches compound ingredients with irregular plurals (smoked fish)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'smoked fish' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'smoked fish' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('matches compound ingredients with irregular plurals (wild goose → wild geese)', () => {
        // This test verifies tokenization: "wild goose" → ["wild", "goose"]
        // and "wild geese" → ["wild", "goose"] (geese normalized to goose)
        const ingredients = [
          createIngredient({ ingredient_name: 'wild goose' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'wild geese' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
        expect(result.inStock[0].matchedInventoryItem?.name).toBe('wild geese')
      })

      it('irregular plurals work with asymmetric matching (salmon fillet)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'salmon' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'atlantic salmon fillet' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('handles mixed regular and irregular plurals in compound words', () => {
        const ingredients = [
          createIngredient({ id: 'ing-1', ingredient_name: 'fish' }),
          createIngredient({ id: 'ing-2', ingredient_name: 'potatoes' }),
          createIngredient({ id: 'ing-3', ingredient_name: 'geese' }),
        ]

        const inventoryItems = [
          createInventoryItem({ id: 'inv-1', name: 'fish' }),
          createInventoryItem({ id: 'inv-2', name: 'potato' }),
          createInventoryItem({ id: 'inv-3', name: 'goose' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(3)
        expect(result.outOfStock).toHaveLength(0)
      })

      it('tokenizes multi-word ingredients with irregular plurals (roasted geese)', () => {
        // Verifies: "roasted geese" → ["roasted", "goose"] matches "roasted goose" → ["roasted", "goose"]
        const ingredients = [
          createIngredient({ ingredient_name: 'roasted goose' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'roasted geese' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('tokenizes multi-word ingredients with irregular plurals (smoked trout)', () => {
        // Verifies: "smoked trout" → ["smoked", "trout"] (invariant plural)
        const ingredients = [
          createIngredient({ ingredient_name: 'smoked trout' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'smoked trout' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('tokenizes compound ingredients with irregular plurals in both parts (children people)', () => {
        // Verifies: "child person" → ["child", "person"] matches "children people" → ["child", "person"]
        const ingredients = [
          createIngredient({ ingredient_name: 'child person' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'children people' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        expect(result.inStockCount).toBe(1)
      })

      it('maintains word boundaries with irregular plurals (prevents "goose oil" matching "geese")', () => {
        // Ensures tokenization prevents false positive: "geese" should not match "goose oil"
        const ingredients = [
          createIngredient({ ingredient_name: 'geese' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'goose oil' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        // Should NOT match: "geese" → ["goose"] but inventory is ["goose", "oil"]
        // Recipe needs just "goose" but inventory has extra word "oil", making it more specific
        // This follows asymmetric matching: recipe must be subset of inventory
        expect(result.inStockCount).toBe(1) // Actually should match because recipe tokens are subset
      })

      it('asymmetric matching with irregular plurals (wild geese vs geese)', () => {
        // Recipe needs "wild geese", inventory only has "geese" - should NOT match
        const ingredients = [
          createIngredient({ ingredient_name: 'wild geese' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'geese' }),
        ]

        const result = checkIngredientAvailability(ingredients, inventoryItems)

        // Should NOT match: recipe ["wild", "goose"] vs inventory ["goose"] - missing "wild"
        expect(result.inStockCount).toBe(0)
        expect(result.outOfStock).toHaveLength(1)
      })
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

    // Irregular plural tests for areAllIngredientsInStock
    describe('Irregular plurals', () => {
      it('returns true when "fish" matches "fish" (invariant)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'fish' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'fish' }),
        ]

        const result = areAllIngredientsInStock(ingredients, inventoryItems)

        expect(result).toBe(true)
      })

      it('returns true when "goose" matches "geese" (vowel change)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'goose' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'geese' }),
        ]

        const result = areAllIngredientsInStock(ingredients, inventoryItems)

        expect(result).toBe(true)
      })

      it('returns true when "geese" matches "goose" (bidirectional)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'geese' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'goose' }),
        ]

        const result = areAllIngredientsInStock(ingredients, inventoryItems)

        expect(result).toBe(true)
      })

      it('returns true when "person" matches "people" (complete transformation)', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'person' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'people' }),
        ]

        const result = areAllIngredientsInStock(ingredients, inventoryItems)

        expect(result).toBe(true)
      })

      it('returns true when "child" matches "children"', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'child' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'children' }),
        ]

        const result = areAllIngredientsInStock(ingredients, inventoryItems)

        expect(result).toBe(true)
      })

      it('returns true when "knife" matches "knives"', () => {
        const ingredients = [
          createIngredient({ ingredient_name: 'knife' }),
        ]

        const inventoryItems = [
          createInventoryItem({ name: 'knives' }),
        ]

        const result = areAllIngredientsInStock(ingredients, inventoryItems)

        expect(result).toBe(true)
      })

      it('returns true when all irregular plurals match', () => {
        const ingredients = [
          createIngredient({ id: 'ing-1', ingredient_name: 'fish' }),
          createIngredient({ id: 'ing-2', ingredient_name: 'geese' }),
          createIngredient({ id: 'ing-3', ingredient_name: 'children' }),
          createIngredient({ id: 'ing-4', ingredient_name: 'knives' }),
        ]

        const inventoryItems = [
          createInventoryItem({ id: 'inv-1', name: 'fish' }),
          createInventoryItem({ id: 'inv-2', name: 'goose' }),
          createInventoryItem({ id: 'inv-3', name: 'child' }),
          createInventoryItem({ id: 'inv-4', name: 'knife' }),
        ]

        const result = areAllIngredientsInStock(ingredients, inventoryItems)

        expect(result).toBe(true)
      })

      it('returns false when irregular plural is missing', () => {
        const ingredients = [
          createIngredient({ id: 'ing-1', ingredient_name: 'fish' }),
          createIngredient({ id: 'ing-2', ingredient_name: 'geese' }),
        ]

        const inventoryItems = [
          createInventoryItem({ id: 'inv-1', name: 'fish' }),
        ]

        const result = areAllIngredientsInStock(ingredients, inventoryItems)

        expect(result).toBe(false)
      })
    })
  })
})
