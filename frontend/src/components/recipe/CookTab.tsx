import RecipeStep from './RecipeStep'
import SourceLine from './SourceLine'
import type { RecipeIngredientResponse } from '../../api/types'

interface CookTabProps {
  steps: string[]
  ingredients: RecipeIngredientResponse[]
  servingsMultiplier: number
  sourceType?: string
  sourceUrl?: string | null
}

/**
 * CookTab component displays recipe cooking steps
 *
 * Features:
 * - Numbered steps with olive circle indicators
 * - Step-by-step instructions
 * - Inline ingredient pills below each step (for ingredients with matching step_index)
 * - Scaled ingredient quantities
 * - Source attribution after the last step
 */
export default function CookTab({ steps, ingredients, servingsMultiplier, sourceType, sourceUrl }: CookTabProps) {
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

      {sourceUrl && sourceType && (
        <div className="mt-4 pb-2">
          <SourceLine sourceType={sourceType} sourceUrl={sourceUrl} />
        </div>
      )}
    </div>
  )
}
