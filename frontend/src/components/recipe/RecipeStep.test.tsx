import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
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
      step_index: 0,
    },
    {
      id: 'ing-2',
      recipe_id: 'recipe-1',
      ingredient_name: 'garlic',
      quantity: 3,
      unit: 'cloves',
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

  describe('timer extraction', () => {
    it('displays timer badge for "X minutes" pattern', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 15 minutes, stirring occasionally"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('15 minutes')).toBeInTheDocument()
    })

    it('displays timer badge for "X min" pattern', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Simmer for 30 min"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('30 minutes')).toBeInTheDocument()
    })

    it('displays timer badge for "X hour" pattern', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Bake for 1 hour until golden"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('1 hour')).toBeInTheDocument()
    })

    it('displays timer badge for "X hours" pattern', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Marinate for 2 hours"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('2 hours')).toBeInTheDocument()
    })

    it('displays timer badge for "X hr" pattern', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Rest for 3 hr before serving"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('3 hours')).toBeInTheDocument()
    })

    it('displays multiple timer badges when step has multiple time references', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 10 minutes, then simmer for 20 minutes"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('10 minutes')).toBeInTheDocument()
      expect(screen.getByText('20 minutes')).toBeInTheDocument()
    })

    it('does not display timer badge when no time reference exists', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Mix ingredients together thoroughly"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.queryByText(/minute/)).not.toBeInTheDocument()
      expect(screen.queryByText(/hour/)).not.toBeInTheDocument()
    })

    it('handles singular time units correctly', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 1 minute"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('1 minute')).toBeInTheDocument()
    })

    it('handles case-insensitive time patterns', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 5 MINUTES or 10 Min"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('5 minutes')).toBeInTheDocument()
      expect(screen.getByText('10 minutes')).toBeInTheDocument()
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

    it('displays both timer badges and ingredient pills when both exist', () => {
      render(
        <RecipeStep
          stepNumber={1}
          instruction="Heat oil for 5 minutes"
          ingredients={mockIngredients}
          servingsMultiplier={1}
        />
      )
      expect(screen.getByText('5 minutes')).toBeInTheDocument()
      expect(screen.getByText(/2 tbsp olive oil/)).toBeInTheDocument()
    })
  })

  describe('styling', () => {
    it('displays timer badges with terra background', () => {
      const { container } = render(
        <RecipeStep
          stepNumber={1}
          instruction="Cook for 10 minutes"
          ingredients={[]}
          servingsMultiplier={1}
        />
      )
      const timerBadge = container.querySelector('.bg-terra')
      expect(timerBadge).toBeInTheDocument()
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
