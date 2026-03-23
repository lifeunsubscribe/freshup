import RecipeStep from './RecipeStep'
import type { RecipeIngredientResponse } from '../../api/types'

interface CookTabProps {
  steps: string[]
  ingredients: RecipeIngredientResponse[]
  servingsMultiplier: number
}

/**
 * CookTab component displays recipe cooking steps
 *
 * Features:
 * - Numbered steps with olive circle indicators
 * - Step-by-step instructions
 * - Inline ingredient pills below each step (for ingredients with matching step_index)
 * - Scaled ingredient quantities
 */
export default function CookTab({ steps, ingredients, servingsMultiplier }: CookTabProps) {
  if (steps.length === 0) {
    return (
      <div className="text-center py-8 text-text-secondary">
        No cooking steps provided for this recipe.
      </div>
    )
  }

  return (
    <div>
      {steps.map((step, index) => {
        const stepIndex = index
        const stepIngredients = ingredients.filter(
          (ing) => ing.step_index === stepIndex
        )

        return (
          <RecipeStep
            key={stepIndex}
            stepNumber={stepIndex + 1}
            instruction={step}
            ingredients={stepIngredients}
            servingsMultiplier={servingsMultiplier}
          />
        )
      })}
    </div>
  )
}
