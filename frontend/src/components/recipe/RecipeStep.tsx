import Pill from '../ui/Pill'
import type { RecipeIngredientResponse } from '../../api/types'

interface RecipeStepProps {
  stepNumber: number
  instruction: string
  ingredients: RecipeIngredientResponse[]
  servingsMultiplier: number
}

/**
 * RecipeStep component for displaying cooking steps
 *
 * Features:
 * - Step number in olive circle
 * - Step instruction text
 * - Inline ingredient pills for ingredients used in this step
 * - Scaled ingredient quantities
 */
export default function RecipeStep({
  stepNumber,
  instruction,
  ingredients,
  servingsMultiplier,
}: RecipeStepProps) {
  return (
    <div className="flex gap-4 mb-6">
      {/* Step number circle */}
      <div className="flex-shrink-0">
        <div className="w-8 h-8 rounded-full bg-olive flex items-center justify-center">
          <span className="text-sm font-medium text-cream">{stepNumber}</span>
        </div>
      </div>

      {/* Step content */}
      <div className="flex-1">
        {/* Instruction text */}
        <p className="text-sm text-text-primary mb-2 leading-relaxed">{instruction}</p>

        {/* Inline ingredient pills */}
        {ingredients.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {ingredients.map((ingredient) => {
              const scaledQuantity = ingredient.quantity * servingsMultiplier
              return (
                <Pill key={ingredient.id} variant="default">
                  {scaledQuantity} {ingredient.unit} {ingredient.ingredient_name}
                </Pill>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
