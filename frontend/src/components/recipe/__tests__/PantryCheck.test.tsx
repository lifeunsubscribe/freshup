import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
    variation_group: null,
    variation_diet: null,
    is_optional: false,
    step_index: null,
    ...overrides,
  })

  const baseStockStatus: PantryCheckResult = {
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

  describe('card text', () => {
    it('shows k-of-n line', () => {
      render(<PantryCheck stockStatus={baseStockStatus} onReview={vi.fn()} />)
      expect(screen.getByText('2 of 3 in the pantry.')).toBeInTheDocument()
    })

    it('shows the review prompt subtitle', () => {
      render(<PantryCheck stockStatus={baseStockStatus} onReview={vi.fn()} />)
      expect(screen.getByText('Tap to review before adding.')).toBeInTheDocument()
    })

    it('calls onReview when tapped', async () => {
      const onReview = vi.fn()
      render(<PantryCheck stockStatus={baseStockStatus} onReview={onReview} />)
      await userEvent.click(screen.getByRole('button'))
      expect(onReview).toHaveBeenCalledTimes(1)
    })
  })

  describe('inventory error state', () => {
    it('shows unavailable text when inventoryError is true', () => {
      render(
        <PantryCheck
          stockStatus={baseStockStatus}
          onReview={vi.fn()}
          inventoryError
        />
      )
      expect(screen.getByText('Pantry unavailable right now.')).toBeInTheDocument()
    })

    it('does not render a button when inventoryError is true', () => {
      render(
        <PantryCheck
          stockStatus={baseStockStatus}
          onReview={vi.fn()}
          inventoryError
        />
      )
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })

    it('does not call onReview when inventoryError is true (no button to click)', () => {
      const onReview = vi.fn()
      render(
        <PantryCheck
          stockStatus={baseStockStatus}
          onReview={onReview}
          inventoryError
        />
      )
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
      expect(onReview).not.toHaveBeenCalled()
    })
  })

  describe('empty ingredient list', () => {
    it('does not render when totalCount is 0', () => {
      const emptyStatus: PantryCheckResult = {
        inStock: [],
        outOfStock: [],
        totalCount: 0,
        inStockCount: 0,
      }
      const { container } = render(<PantryCheck stockStatus={emptyStatus} onReview={vi.fn()} />)
      expect(container.firstChild).toBeNull()
    })

    it('does not render even with inventoryError when totalCount is 0', () => {
      const emptyStatus: PantryCheckResult = {
        inStock: [],
        outOfStock: [],
        totalCount: 0,
        inStockCount: 0,
      }
      const { container } = render(
        <PantryCheck stockStatus={emptyStatus} onReview={vi.fn()} inventoryError />
      )
      expect(container.firstChild).toBeNull()
    })
  })
})
