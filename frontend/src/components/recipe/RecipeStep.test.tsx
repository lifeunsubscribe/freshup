import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RecipeStep from './RecipeStep'
import type { RecipeIngredientResponse } from '../../api/types'

describe('RecipeStep', () => {
  const mockIngredients: RecipeIngredientResponse[] = [
    {
      id: 'ing-1',
      recipe_id: 'recipe-1',
      ingredient_name: 'olive oil',
      quantity: 2,
      unit: 'tbsp',
      variation_group: null,
      variation_diet: null,
      is_optional: false,
      step_index: 0,
    },
    {
      id: 'ing-2',
      recipe_id: 'recipe-1',
      ingredient_name: 'garlic',
      quantity: 3,
      unit: 'cloves',
      variation_group: null,
      variation_diet: null,
      is_optional: false,
      step_index: 0,
    },
  ]

  describe('basic rendering', () => {
    it('renders step number in olive circle', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Heat oil in a pan"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('1')).toBeInTheDocument()
    })

    it('renders instruction text', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Heat oil in a pan over medium heat"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('Heat oil in a pan over medium heat')).toBeInTheDocument()
    })

    it('displays step numbers correctly for different steps', () => {
      const { rerender } = render(
        <RecipeStep
          stepNumber={5}
          instruction="Test step"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('5')).toBeInTheDocument()

      rerender(
        <RecipeStep
          stepNumber={12}
          instruction="Test step"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('12')).toBeInTheDocument()
    })
  })

  describe('"Start N min" timer buttons', () => {
    it('renders a "Start N min" button when the step contains a plain duration', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 15 minutes, stirring occasionally"
          ingredients={[]}
          servingsMultiplier={1}
          onStartTimer={vi.fn()}
        />
      )
      expect(screen.getByRole('button', { name: /start 15 min/i })).toBeInTheDocument()
    })

    it('renders "Start N min" for "X min" shorthand', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Simmer for 30 min"
          ingredients={[]}
          servingsMultiplier={1}
          onStartTimer={vi.fn()}
        />
      )
      expect(screen.getByRole('button', { name: /start 30 min/i })).toBeInTheDocument()
    })

    it('renders "Start N hr" for 1-hour steps', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Bake for 1 hour until golden"
          ingredients={[]}
          servingsMultiplier={1}
          onStartTimer={vi.fn()}
        />
      )
      expect(screen.getByRole('button', { name: /start 1 hr/i })).toBeInTheDocument()
    })

    it('renders "Start N hr M min" for durations over 60 minutes', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Marinate for 1.5 hours"
          ingredients={[]}
          servingsMultiplier={1}
          onStartTimer={vi.fn()}
        />
      )
      expect(screen.getByRole('button', { name: /start 1 hr 30 min/i })).toBeInTheDocument()
    })

    it('renders multiple timer buttons for multiple durations', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 10 minutes, then simmer for 20 minutes"
          ingredients={[]}
          servingsMultiplier={1}
          onStartTimer={vi.fn()}
        />
      )
      expect(screen.getByRole('button', { name: /start 10 min/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /start 20 min/i })).toBeInTheDocument()
    })

    it('does not render timer buttons when no duration exists in the step', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Mix ingredients together thoroughly"
          ingredients={[]}
          servingsMultiplier={1}
          onStartTimer={vi.fn()}
        />
      )
      expect(screen.queryByRole('button', { name: /start/i })).not.toBeInTheDocument()
    })

    it('calls onStartTimer with the detected duration in minutes', async () => {
      const onStartTimer = vi.fn()
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 15 minutes"
          ingredients={[]}
          servingsMultiplier={1}
          onStartTimer={onStartTimer}
        />
      )
      await userEvent.click(screen.getByRole('button', { name: /start 15 min/i }))
      expect(onStartTimer).toHaveBeenCalledWith(15)
    })

    it('renders timer buttons disabled when onStartTimer is not provided', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 15 minutes"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      const btn = screen.getByRole('button', { name: /start 15 min/i })
      expect(btn).toBeDisabled()
    })

    it('handles singular "1 minute"', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 1 minute"
          ingredients={[]}
          servingsMultiplier={1}
          onStartTimer={vi.fn()}
        />
      )
      expect(screen.getByRole('button', { name: /start 1 min/i })).toBeInTheDocument()
    })

    it('handles case-insensitive patterns', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 5 MINUTES or 10 Min"
          ingredients={[]}
          servingsMultiplier={1}
          onStartTimer={vi.fn()}
        />
      )
      expect(screen.getByRole('button', { name: /start 5 min/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /start 10 min/i })).toBeInTheDocument()
    })
  })

  describe('ingredient pills', () => {
    it('displays ingredient pills when ingredients are provided', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Heat oil and add garlic"
          ingredients={mockIngredients}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText(/2 tbsp olive oil/)).toBeInTheDocument()
      expect(screen.getByText(/3 cloves garlic/)).toBeInTheDocument()
    })

    it('scales ingredient quantities by servings multiplier', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Heat oil and add garlic"
          ingredients={mockIngredients}
          servingsMultiplier={2}
        />
      )
      expect(screen.getByText(/4 tbsp olive oil/)).toBeInTheDocument()
      expect(screen.getByText(/6 cloves garlic/)).toBeInTheDocument()
    })

    it('does not display ingredient pills when no ingredients are provided', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Mix ingredients"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.queryByText(/tbsp/)).not.toBeInTheDocument()
      expect(screen.queryByText(/cloves/)).not.toBeInTheDocument()
    })

    it('displays both timer buttons and ingredient pills when both exist', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Heat oil for 5 minutes"
          ingredients={mockIngredients}
          servingsMultiplier={1}
          onStartTimer={vi.fn()}
        />
      )
      expect(screen.getByRole('button', { name: /start 5 min/i })).toBeInTheDocument()
      expect(screen.getByText(/2 tbsp olive oil/)).toBeInTheDocument()
    })
  })

  describe('styling', () => {
    it('displays timer buttons with terra background', () => {
      const { container } = render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 10 minutes"
          ingredients={[]}
          servingsMultiplier={1}
          onStartTimer={vi.fn()}
        />
      )
      const timerButton = container.querySelector('.bg-terra')
      expect(timerButton).toBeInTheDocument()
    })

    it('displays step number with olive background', () => {
      const { container } = render(
        <RecipeStep
          stepNumber={1}
          instruction="Test instruction"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      const stepCircle = container.querySelector('.bg-olive')
      expect(stepCircle).toBeInTheDocument()
    })
  })
})
