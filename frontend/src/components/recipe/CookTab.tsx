import RecipeStep from './RecipeStep'
import SourceLine from './SourceLine'
import type { RecipeIngredientResponse } from '../../api/types'
import { ingredientsForStep } from '../../utils/stepIngredients'

interface CookTabProps {
  steps: string[]
  ingredients: RecipeIngredientResponse[]
  servingsMultiplier: number
  sourceType?: string
  sourceUrl?: string | null
  onStartTimer?: (durationMinutes: number, stepNumber: number) => void
}

/**
 * CookTab displays recipe cooking steps with ingredient pills and timer buttons.
 *
 * Ingredient matching:
 *   - If the recipe has step_index on any ingredient, uses step_index (manual recipes).
 *   - Otherwise matches ingredient names against step text (imported recipes).
 */
export default function CookTab({
  steps,
  ingredients,
  servingsMultiplier,
  sourceType,
  sourceUrl,
  onStartTimer,
}: CookTabProps) {
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
        const stepIngredients = ingredientsForStep(index, step, ingredients)
        const stepNumber = index + 1

        return (
          <RecipeStep
            key={index}
            stepNumber={stepNumber}
            instruction={step}
            ingredients={stepIngredients}
            servingsMultiplier={servingsMultiplier}
            onStartTimer={onStartTimer ? (mins) => onStartTimer(mins, stepNumber) : undefined}
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
