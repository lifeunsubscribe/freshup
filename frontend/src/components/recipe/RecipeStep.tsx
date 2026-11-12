import { Clock } from 'lucide-react'
import Pill from '../ui/Pill'
import type { RecipeIngredientResponse } from '../../api/types'
import { durationsInStep, formatStartLabel } from '../../utils/stepDurations'

interface RecipeStepProps {
  stepNumber: number
  instruction: string
  ingredients: RecipeIngredientResponse[]
  servingsMultiplier: number
  onStartTimer?: (durationMinutes: number) => void
}

/**
 * RecipeStep component for displaying cooking steps.
 *
 * Features:
 * - Step number in olive circle
 * - Step instruction text
 * - "Start N min" buttons for each distinct duration detected in the step
 * - Inline ingredient pills for ingredients matched to this step
 * - Scaled ingredient quantities
 */
export default function RecipeStep({
  stepNumber,
  instruction,
  ingredients,
  servingsMultiplier,
  onStartTimer,
}: RecipeStepProps) {
  const durations = durationsInStep(instruction)

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

        {/* "Start N min" timer buttons — one per distinct detected duration */}
        {durations.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {durations.map((mins) => (
              <button
                key={mins}
                onClick={() => onStartTimer?.(mins)}
                disabled={!onStartTimer}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-terra text-text-primary text-xs font-medium disabled:opacity-60"
                aria-label={`${formatStartLabel(mins)} timer`}
              >
                <Clock size={14} className="flex-shrink-0" />
                <span>{formatStartLabel(mins)}</span>
              </button>
            ))}
          </div>
        )}

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
