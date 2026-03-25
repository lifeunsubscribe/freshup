import { Clock } from 'lucide-react'
import Pill from '../ui/Pill'
import type { RecipeIngredientResponse } from '../../api/types'

interface RecipeStepProps {
  stepNumber: number
  instruction: string
  ingredients: RecipeIngredientResponse[]
  servingsMultiplier: number
}

/**
 * Extracts time references from instruction text
 * Matches patterns like "30 minutes", "2 hours", "15 min", "1 hr"
 */
function extractTimers(text: string): string[] {
  const timerRegex = /(\d+)\s*(minute|min|hour|hr)s?/gi
  const matches = text.matchAll(timerRegex)
  const timers: string[] = []

  for (const match of matches) {
    const value = match[1]
    const unit = match[2].toLowerCase()
    // Normalize to full unit name
    const normalizedUnit = unit.startsWith('h') ? 'hour' : 'minute'
    const displayUnit = normalizedUnit + (parseInt(value) !== 1 ? 's' : '')
    timers.push(`${value} ${displayUnit}`)
  }

  return timers
}

/**
 * RecipeStep component for displaying cooking steps
 *
 * Features:
 * - Step number in olive circle
 * - Step instruction text
 * - Timer callout badges for steps containing time references
 * - Inline ingredient pills for ingredients used in this step
 * - Scaled ingredient quantities
 */
export default function RecipeStep({
  stepNumber,
  instruction,
  ingredients,
  servingsMultiplier,
}: RecipeStepProps) {
  const timers = extractTimers(instruction)

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

        {/* Timer callouts */}
        {timers.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2">
            {timers.map((timer, idx) => (
              <div
                key={idx}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-terra text-text-primary"
              >
                <Clock size={14} className="flex-shrink-0" />
                <span className="text-xs font-medium">{timer}</span>
              </div>
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
