import { describe, it, expect } from 'vitest'
import { ingredientsForStep } from '../stepIngredients'
import type { RecipeIngredientResponse } from '../../api/types'

function makeIng(
  id: string,
  ingredient_name: string,
  step_index: number | null = null
): RecipeIngredientResponse {
  return {
    id,
    recipe_id: 'recipe-1',
    ingredient_name,
    quantity: 1,
    unit: 'piece',
    variation_group: null,
    variation_diet: null,
    is_optional: false,
    step_index,
  }
}

describe('ingredientsForStep', () => {
  describe('step_index mode (any ingredient has step_index set)', () => {
    const ingredients = [
      makeIng('1', 'Firm tofu', 0),
      makeIng('2', 'Soy sauce', 0),
      makeIng('3', 'Sesame seeds', 1),
      makeIng('4', 'Garlic', 2),
    ]

    it('returns ingredients matching the given step_index', () => {
      const result = ingredientsForStep(0, 'Add the tofu and soy sauce', ingredients)
      expect(result.map(i => i.ingredient_name)).toEqual(['Firm tofu', 'Soy sauce'])
    })

    it('returns ingredients for a different step index', () => {
      const result = ingredientsForStep(1, 'Garnish with sesame seeds', ingredients)
      expect(result.map(i => i.ingredient_name)).toEqual(['Sesame seeds'])
    })

    it('returns empty when no ingredient has the given step_index', () => {
      const result = ingredientsForStep(5, 'Some step', ingredients)
      expect(result).toHaveLength(0)
    })

    it('honours step_index even when ingredient name appears in the step text', () => {
      // Firm tofu (step_index 0) should NOT be returned for step_index 1,
      // even if the step text contains "tofu".
      const result = ingredientsForStep(1, 'Remove the tofu from the pan', ingredients)
      expect(result.map(i => i.ingredient_name)).not.toContain('Firm tofu')
    })
  })

  describe('name-matching mode (all step_index are null)', () => {
    const ingredients = [
      makeIng('1', 'Firm tofu'),
      makeIng('2', 'Soy sauce'),
      makeIng('3', 'Sesame seeds'),
      makeIng('4', 'Garlic'),
    ]

    it('matches "Firm tofu" via the token "tofu"', () => {
      const result = ingredientsForStep(0, 'Add the tofu and soy sauce', ingredients)
      expect(result.map(i => i.ingredient_name)).toContain('Firm tofu')
    })

    it('matches "Soy sauce" via the token "soy"', () => {
      const result = ingredientsForStep(0, 'Add the tofu and soy sauce', ingredients)
      expect(result.map(i => i.ingredient_name)).toContain('Soy sauce')
    })

    it('does not match "Sesame seeds" when neither token appears in the step', () => {
      const result = ingredientsForStep(0, 'Add the tofu and soy sauce', ingredients)
      expect(result.map(i => i.ingredient_name)).not.toContain('Sesame seeds')
    })

    it('returns results in original recipe order', () => {
      const result = ingredientsForStep(0, 'Add the tofu and soy sauce', ingredients)
      const names = result.map(i => i.ingredient_name)
      // Firm tofu is index 0 in the ingredients array, Soy sauce is index 1
      expect(names.indexOf('Firm tofu')).toBeLessThan(names.indexOf('Soy sauce'))
    })

    it('returns an empty array when no ingredient tokens appear in the step', () => {
      const result = ingredientsForStep(0, 'Bring water to a boil', ingredients)
      expect(result).toHaveLength(0)
    })

    it('uses whole-word matching — does not match partial words', () => {
      // "oil" should not match inside the word "boil"
      const oilIngredient = makeIng('5', 'Olive oil')
      const result = ingredientsForStep(0, 'Bring water to a boil', [oilIngredient])
      expect(result).toHaveLength(0)
    })

    it('is case-insensitive', () => {
      const result = ingredientsForStep(0, 'Add GARLIC to the pan', ingredients)
      expect(result.map(i => i.ingredient_name)).toContain('Garlic')
    })

    it('matches multi-word ingredients when any significant token appears', () => {
      const result = ingredientsForStep(0, 'Drizzle with soy sauce', ingredients)
      expect(result.map(i => i.ingredient_name)).toContain('Soy sauce')
    })
  })

  describe('mixed step_index (some set, some null)', () => {
    it('falls back to step_index mode when any ingredient has step_index set', () => {
      const mixed = [
        makeIng('1', 'Salt', null),
        makeIng('2', 'Pepper', 0),
      ]
      // step_index mode: only Pepper (step_index 0) should be returned for step 0
      const result = ingredientsForStep(0, 'Season with salt and pepper', mixed)
      expect(result.map(i => i.ingredient_name)).toEqual(['Pepper'])
    })
  })
})
