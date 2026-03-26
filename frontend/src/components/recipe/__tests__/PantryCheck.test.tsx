import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PantryCheck from '../PantryCheck'
import type { PantryCheckResult } from '../../../utils/pantryMatcher'
import type { RecipeIngredientResponse } from '../../../api/types'

describe('PantryCheck', () => {
  const createIngredient = (overrides: Partial<RecipeIngredientResponse> = {}): RecipeIngredientResponse => ({
    id: 'ing-1',
    recipe_id: 'recipe-1',
    ingredient_name: 'flour',
    quantity: 1,
    unit: 'cup',
    step_index: null,
    ...overrides,
  })

  it('displays correct stock count summary', () => {
    const stockStatus: PantryCheckResult = {
      inStock: [
        { ingredient: createIngredient({ id: 'ing-1', ingredient_name: 'flour' }), inStock: true },
        { ingredient: createIngredient({ id: 'ing-2', ingredient_name: 'sugar' }), inStock: true },
      ],
      outOfStock: [
        { ingredient: createIngredient({ id: 'ing-3', ingredient_name: 'salt' }), inStock: false },
      ],
      totalCount: 3,
      inStockCount: 2,
    }

    render(<PantryCheck stockStatus={stockStatus} />)

    expect(screen.getByText(/2 of 3 ingredients in stock/i)).toBeInTheDocument()
  })

  it('lists in-stock ingredient names', () => {
    const stockStatus: PantryCheckResult = {
      inStock: [
        { ingredient: createIngredient({ id: 'ing-1', ingredient_name: 'flour' }), inStock: true },
        { ingredient: createIngredient({ id: 'ing-2', ingredient_name: 'sugar' }), inStock: true },
      ],
      outOfStock: [],
      totalCount: 2,
      inStockCount: 2,
    }

    render(<PantryCheck stockStatus={stockStatus} />)

    expect(screen.getByText(/flour, sugar are in stock/i)).toBeInTheDocument()
  })

  it('uses singular "ingredient" for single item', () => {
    const stockStatus: PantryCheckResult = {
      inStock: [
        { ingredient: createIngredient({ ingredient_name: 'flour' }), inStock: true },
      ],
      outOfStock: [],
      totalCount: 1,
      inStockCount: 1,
    }

    render(<PantryCheck stockStatus={stockStatus} />)

    expect(screen.getByText(/1 of 1 ingredient in stock/i)).toBeInTheDocument()
    expect(screen.getByText(/flour is in stock/i)).toBeInTheDocument()
  })

  it('shows missing ingredients count', () => {
    const stockStatus: PantryCheckResult = {
      inStock: [
        { ingredient: createIngredient({ ingredient_name: 'flour' }), inStock: true },
      ],
      outOfStock: [
        { ingredient: createIngredient({ id: 'ing-2', ingredient_name: 'sugar' }), inStock: false },
        { ingredient: createIngredient({ id: 'ing-3', ingredient_name: 'salt' }), inStock: false },
      ],
      totalCount: 3,
      inStockCount: 1,
    }

    render(<PantryCheck stockStatus={stockStatus} />)

    expect(screen.getByText(/2 ingredients needed from the store/i)).toBeInTheDocument()
  })

  it('uses singular "ingredient" for single missing item', () => {
    const stockStatus: PantryCheckResult = {
      inStock: [],
      outOfStock: [
        { ingredient: createIngredient({ ingredient_name: 'flour' }), inStock: false },
      ],
      totalCount: 1,
      inStockCount: 0,
    }

    render(<PantryCheck stockStatus={stockStatus} />)

    expect(screen.getByText(/1 ingredient needed from the store/i)).toBeInTheDocument()
  })

  it('shows all ingredients in stock message when nothing is missing', () => {
    const stockStatus: PantryCheckResult = {
      inStock: [
        { ingredient: createIngredient({ id: 'ing-1', ingredient_name: 'flour' }), inStock: true },
        { ingredient: createIngredient({ id: 'ing-2', ingredient_name: 'sugar' }), inStock: true },
      ],
      outOfStock: [],
      totalCount: 2,
      inStockCount: 2,
    }

    render(<PantryCheck stockStatus={stockStatus} />)

    expect(screen.getByText(/All ingredients are in stock!/i)).toBeInTheDocument()
  })

  it('does not render when no ingredients', () => {
    const stockStatus: PantryCheckResult = {
      inStock: [],
      outOfStock: [],
      totalCount: 0,
      inStockCount: 0,
    }

    const { container } = render(<PantryCheck stockStatus={stockStatus} />)

    expect(container.firstChild).toBeNull()
  })

  it('handles empty in-stock list gracefully', () => {
    const stockStatus: PantryCheckResult = {
      inStock: [],
      outOfStock: [
        { ingredient: createIngredient({ ingredient_name: 'flour' }), inStock: false },
      ],
      totalCount: 1,
      inStockCount: 0,
    }

    render(<PantryCheck stockStatus={stockStatus} />)

    expect(screen.getByText(/0 of 1 ingredient in stock/i)).toBeInTheDocument()
    expect(screen.getByText(/1 ingredient needed from the store/i)).toBeInTheDocument()
    expect(screen.queryByText(/are in stock/i)).not.toBeInTheDocument()
  })
})
