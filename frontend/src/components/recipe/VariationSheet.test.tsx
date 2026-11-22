import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import VariationSheet from './VariationSheet'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { RecipeResponse } from '../../api/types'

const saveMutate = vi.fn()
vi.mock('../../api/hooks/useRecipes', () => ({
  useSaveVariation: () => ({ mutate: saveMutate, isPending: false, isError: false, reset: vi.fn() }),
}))

const recipe: RecipeResponse = {
  id: 'r1',
  name: 'Fried Rice',
  source_type: 'hellofresh',
  source_url: null,
  source_image: null,
  steps: ['Cook rice.', 'Fry it.'],
  created_by: 'someone',
  notes: null,
  tags: [],
  cook_time_minutes: null,
  prep_time_minutes: null,
  base_servings: 2,
  times_cooked: 0,
  is_persisted: true,
  variation_groups: null,
  nutritional_info: null,
  ingredients: [
    { id: 'i1', recipe_id: 'r1', ingredient_name: 'Rice', quantity: 1, unit: 'cup', variation_group: null, variation_diet: null, is_optional: false, step_index: null },
    { id: 'i2', recipe_id: 'r1', ingredient_name: 'Salt', quantity: 0.001, unit: '', variation_group: null, variation_diet: null, is_optional: false, step_index: null },
  ],
}

function renderSheet(isOwnVersion = false, onSaved = vi.fn()) {
  renderWithProviders(
    <VariationSheet open onClose={vi.fn()} recipe={recipe} isOwnVersion={isOwnVersion} onSaved={onSaved} />
  )
  return onSaved
}

describe('VariationSheet', () => {
  beforeEach(() => vi.clearAllMocks())

  it('starts from the recipe, with "to taste" amounts left empty', () => {
    renderSheet()

    expect(screen.getByRole('dialog', { name: 'Make it your own' })).toBeInTheDocument()
    expect(screen.getByLabelText('Ingredient 1')).toHaveValue('Rice')
    expect(screen.getByLabelText('Amount for ingredient 1')).toHaveValue('1')
    expect(screen.getByLabelText('Amount for ingredient 2')).toHaveValue('')
    expect(screen.getByLabelText('Steps')).toHaveValue('Cook rice.\n\nFry it.')
    expect(screen.getByText(/The original stays as it is/)).toBeInTheDocument()
  })

  it('saves the changed ingredients and steps as the user\'s version', () => {
    const onSaved = renderSheet()
    saveMutate.mockImplementation((_vars, options) => options.onSuccess({ ...recipe, id: 'v1' }))

    fireEvent.change(screen.getByLabelText('Ingredient 1'), { target: { value: 'Brown rice' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add an ingredient' }))
    fireEvent.change(screen.getByLabelText('Ingredient 3'), { target: { value: 'Tofu' } })
    fireEvent.change(screen.getByLabelText('Amount for ingredient 3'), { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText('Unit for ingredient 3'), { target: { value: 'oz' } })
    fireEvent.change(screen.getByLabelText('Steps'), { target: { value: 'Cook rice.\n\nFry the tofu.\n\n' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save as my version' }))

    expect(saveMutate).toHaveBeenCalledWith(
      {
        recipeId: 'r1',
        changes: {
          ingredients: [
            { ingredient_name: 'Brown rice', quantity: 1, unit: 'cup' },
            { ingredient_name: 'Salt', quantity: 0.001, unit: '' },
            { ingredient_name: 'Tofu', quantity: 7, unit: 'oz' },
          ],
          steps: ['Cook rice.', 'Fry the tofu.'],
        },
      },
      expect.anything()
    )
    expect(onSaved).toHaveBeenCalledWith(expect.objectContaining({ id: 'v1' }), true)
  })

  it('removes an ingredient, and refuses an amount that is not a number', () => {
    renderSheet()

    fireEvent.click(screen.getByRole('button', { name: 'Remove Salt' }))
    expect(screen.queryByDisplayValue('Salt')).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Amount for ingredient 1'), { target: { value: 'a bit' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save as my version' }))

    expect(screen.getByRole('alert')).toHaveTextContent('"a bit" is not an amount for Rice.')
    expect(saveMutate).not.toHaveBeenCalled()
  })

  it('lets the user rename their own version, and saves it in place', () => {
    renderSheet(true)

    expect(screen.getByRole('dialog', { name: 'Edit your version' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Tofu Fried Rice' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(saveMutate.mock.calls[0][0].changes.name).toBe('Tofu Fried Rice')
  })
})
