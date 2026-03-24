import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import IngredientsTab from '../IngredientsTab'
import type { RecipeIngredientResponse } from '../../../api/types'

describe('IngredientsTab', () => {
  const createIngredient = (overrides: Partial<RecipeIngredientResponse> = {}): RecipeIngredientResponse => ({
    id: 'ing-1',
    recipe_id: 'recipe-1',
    ingredient_name: 'flour',
    quantity: 1,
    unit: 'cup',
    step_index: null,
    ...overrides,
  })

  describe('component rendering', () => {
    it('renders ingredients list with formatted quantities', () => {
      const ingredients = [
        createIngredient({ id: 'ing-1', ingredient_name: 'flour', quantity: 1, unit: 'cup' }),
        createIngredient({ id: 'ing-2', ingredient_name: 'sugar', quantity: 0.5, unit: 'cup' }),
      ]

      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)

      expect(screen.getByText('flour')).toBeInTheDocument()
      expect(screen.getByText('sugar')).toBeInTheDocument()
      expect(screen.getByText(/1 cup/)).toBeInTheDocument()
      expect(screen.getByText(/1\/2 cup/)).toBeInTheDocument()
    })

    it('displays empty state when no ingredients', () => {
      render(<IngredientsTab ingredients={[]} servingsMultiplier={1} />)

      expect(screen.getByText('No ingredients listed for this recipe.')).toBeInTheDocument()
    })

    it('scales quantities by servingsMultiplier', () => {
      const ingredients = [
        createIngredient({ id: 'ing-1', ingredient_name: 'flour', quantity: 1, unit: 'cup' }),
      ]

      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={2} />)

      expect(screen.getByText(/2 cup/)).toBeInTheDocument()
    })
  })

  describe('formatQuantity - whole numbers', () => {
    it('formats whole numbers without decimals', () => {
      const ingredients = [
        createIngredient({ quantity: 1 }),
        createIngredient({ id: 'ing-2', quantity: 5 }),
      ]

      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)

      expect(screen.getByText(/^1 cup$/)).toBeInTheDocument()
      expect(screen.getByText(/^5 cup$/)).toBeInTheDocument()
    })

    it('handles floating-point whole numbers (e.g., 2.0000001)', () => {
      const ingredients = [
        createIngredient({ quantity: 2.0000001 }),
      ]

      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)

      expect(screen.getByText(/^2 cup$/)).toBeInTheDocument()
    })

    it('handles floating-point whole numbers (e.g., 1.9999999)', () => {
      const ingredients = [
        createIngredient({ quantity: 1.9999999 }),
      ]

      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)

      expect(screen.getByText(/^2 cup$/)).toBeInTheDocument()
    })
  })

  describe('formatQuantity - common fractions', () => {
    it('formats 1/4 (0.25) correctly', () => {
      const ingredients = [createIngredient({ quantity: 0.25 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/1\/4 cup/)).toBeInTheDocument()
    })

    it('formats 1/3 (0.333...) correctly', () => {
      const ingredients = [createIngredient({ quantity: 1 / 3 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/1\/3 cup/)).toBeInTheDocument()
    })

    it('formats 1/2 (0.5) correctly', () => {
      const ingredients = [createIngredient({ quantity: 0.5 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/1\/2 cup/)).toBeInTheDocument()
    })

    it('formats 2/3 (0.666...) correctly', () => {
      const ingredients = [createIngredient({ quantity: 2 / 3 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/2\/3 cup/)).toBeInTheDocument()
    })

    it('formats 3/4 (0.75) correctly', () => {
      const ingredients = [createIngredient({ quantity: 0.75 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/3\/4 cup/)).toBeInTheDocument()
    })

    it('formats 1/8 (0.125) correctly', () => {
      const ingredients = [createIngredient({ quantity: 0.125 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/1\/8 cup/)).toBeInTheDocument()
    })

    it('formats 3/8 (0.375) correctly', () => {
      const ingredients = [createIngredient({ quantity: 0.375 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/3\/8 cup/)).toBeInTheDocument()
    })

    it('formats 5/8 (0.625) correctly', () => {
      const ingredients = [createIngredient({ quantity: 0.625 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/5\/8 cup/)).toBeInTheDocument()
    })

    it('formats 7/8 (0.875) correctly', () => {
      const ingredients = [createIngredient({ quantity: 0.875 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/7\/8 cup/)).toBeInTheDocument()
    })
  })

  describe('formatQuantity - mixed numbers', () => {
    it('formats 1 1/2 correctly', () => {
      const ingredients = [createIngredient({ quantity: 1.5 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/1 1\/2 cup/)).toBeInTheDocument()
    })

    it('formats 2 1/4 correctly', () => {
      const ingredients = [createIngredient({ quantity: 2.25 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/2 1\/4 cup/)).toBeInTheDocument()
    })

    it('formats 1 1/3 correctly', () => {
      const ingredients = [createIngredient({ quantity: 1 + 1 / 3 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/1 1\/3 cup/)).toBeInTheDocument()
    })

    it('formats 3 2/3 correctly', () => {
      const ingredients = [createIngredient({ quantity: 3 + 2 / 3 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/3 2\/3 cup/)).toBeInTheDocument()
    })
  })

  describe('formatQuantity - tolerance-based matching', () => {
    it('matches values within tolerance to 1/4 (0.249 -> 1/4)', () => {
      const ingredients = [createIngredient({ quantity: 0.249 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/1\/4 cup/)).toBeInTheDocument()
    })

    it('matches values within tolerance to 1/3 (0.334 -> 1/3)', () => {
      const ingredients = [createIngredient({ quantity: 0.334 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/1\/3 cup/)).toBeInTheDocument()
    })

    it('matches values within tolerance to 1/2 (0.499 -> 1/2)', () => {
      const ingredients = [createIngredient({ quantity: 0.499 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/1\/2 cup/)).toBeInTheDocument()
    })

    it('matches values within tolerance to 2/3 (0.669 -> 2/3)', () => {
      const ingredients = [createIngredient({ quantity: 0.669 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/2\/3 cup/)).toBeInTheDocument()
    })

    it('matches values within tolerance to 3/4 (0.751 -> 3/4)', () => {
      const ingredients = [createIngredient({ quantity: 0.751 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/3\/4 cup/)).toBeInTheDocument()
    })
  })

  describe('formatQuantity - values outside tolerance', () => {
    it('formats 0.26 as decimal (outside 1/4 tolerance)', () => {
      const ingredients = [createIngredient({ quantity: 0.26 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/0\.26 cup/)).toBeInTheDocument()
    })

    it('formats 0.4 as decimal', () => {
      const ingredients = [createIngredient({ quantity: 0.4 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/0\.40 cup/)).toBeInTheDocument()
    })

    it('formats 0.6 as decimal', () => {
      const ingredients = [createIngredient({ quantity: 0.6 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/0\.60 cup/)).toBeInTheDocument()
    })

    it('formats 1.37 as decimal (outside 1 1/3 tolerance)', () => {
      const ingredients = [createIngredient({ quantity: 1.37 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      expect(screen.getByText(/1\.37 cup/)).toBeInTheDocument()
    })
  })

  describe('formatQuantity - floating-point edge cases', () => {
    it('handles (1/3) * 3 as whole number 1', () => {
      const ingredients = [createIngredient({ quantity: (1 / 3) * 3 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1} />)
      // (1/3) * 3 might be 0.9999999... or 1.0000001 due to floating-point
      // Should round to 1
      expect(screen.getByText(/^1 cup$/)).toBeInTheDocument()
    })

    it('handles scaled fractions: 0.25 * 2 = 0.5 -> 1/2', () => {
      const ingredients = [createIngredient({ quantity: 0.25 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={2} />)
      expect(screen.getByText(/1\/2 cup/)).toBeInTheDocument()
    })

    it('handles scaled fractions: 0.5 * 3 = 1.5 -> 1 1/2', () => {
      const ingredients = [createIngredient({ quantity: 0.5 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={3} />)
      expect(screen.getByText(/1 1\/2 cup/)).toBeInTheDocument()
    })

    it('handles scaled fractions: (1/3) * 2 = 2/3', () => {
      const ingredients = [createIngredient({ quantity: 1 / 3 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={2} />)
      expect(screen.getByText(/2\/3 cup/)).toBeInTheDocument()
    })

    it('handles scaled fractions: (2/3) * 1.5 = 1', () => {
      const ingredients = [createIngredient({ quantity: 2 / 3 })]
      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={1.5} />)
      // (2/3) * 1.5 = 1 (with potential floating-point errors)
      expect(screen.getByText(/^1 cup$/)).toBeInTheDocument()
    })
  })

  describe('formatQuantity - realistic cooking scenarios', () => {
    it('handles typical ingredient scaling for 2 servings', () => {
      const ingredients = [
        createIngredient({ id: 'ing-1', ingredient_name: 'flour', quantity: 0.5, unit: 'cup' }),
        createIngredient({ id: 'ing-2', ingredient_name: 'sugar', quantity: 0.25, unit: 'cup' }),
        createIngredient({ id: 'ing-3', ingredient_name: 'butter', quantity: 0.125, unit: 'cup' }),
      ]

      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={2} />)

      expect(screen.getByText(/1 cup/)).toBeInTheDocument() // flour: 0.5 * 2 = 1
      expect(screen.getByText(/1\/2 cup/)).toBeInTheDocument() // sugar: 0.25 * 2 = 0.5
      expect(screen.getByText(/1\/4 cup/)).toBeInTheDocument() // butter: 0.125 * 2 = 0.25
    })

    it('handles typical ingredient scaling for 4 servings', () => {
      const ingredients = [
        createIngredient({ id: 'ing-1', ingredient_name: 'flour', quantity: 0.75, unit: 'cup' }),
      ]

      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={4} />)

      expect(screen.getByText(/3 cup/)).toBeInTheDocument() // 0.75 * 4 = 3
    })

    it('handles scaling that produces fractions: 1 cup for 2 servings, scaled to 6', () => {
      const ingredients = [
        createIngredient({ ingredient_name: 'flour', quantity: 1, unit: 'cup' }),
      ]

      render(<IngredientsTab ingredients={ingredients} servingsMultiplier={3} />)

      expect(screen.getByText(/3 cup/)).toBeInTheDocument() // 1 * 3 = 3
    })
  })
})
