import { Lock } from 'lucide-react'

interface ServingsControlProps {
  selectedServings: 2 | 4 | 6
  onServingsChange: (servings: 2 | 4 | 6) => void
  baseServings?: number // Recipe's original serving size
}

/**
 * ServingsControl - Segmented control for selecting serving sizes
 *
 * Features:
 * - Three options: 2, 4, 6 servings
 * - Segmented button group styling
 * - Active state with olive background
 * - Defaults to recipe's base_servings when provided
 * - Phase 3 treatment for non-base options (grayed out with lock icon)
 * - Scales ingredient quantities in parent component
 */
export default function ServingsControl({ selectedServings, onServingsChange, baseServings }: ServingsControlProps) {
  const servingsOptions: Array<2 | 4 | 6> = [2, 4, 6]

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-text-primary mb-2">
        Servings
      </label>
      <div className="inline-flex rounded-button border border-warm-border bg-cream overflow-hidden">
        {servingsOptions.map((servings) => {
          const isBase = baseServings === servings
          const isPhase3 = baseServings !== undefined && !isBase

          return (
            <button
              key={servings}
              onClick={() => onServingsChange(servings)}
              disabled={isPhase3}
              className={`
                px-6 py-2 text-sm font-medium transition-colors relative
                ${selectedServings === servings
                  ? 'bg-olive text-cream'
                  : isPhase3
                    ? 'bg-cream text-text-secondary opacity-50 cursor-not-allowed'
                    : 'bg-cream text-text-primary hover:bg-cream-dark'
                }
                ${servings !== servingsOptions[servingsOptions.length - 1] ? 'border-r border-warm-border' : ''}
              `}
              aria-label={`${servings} servings${isPhase3 ? ' (coming in Phase 3)' : ''}`}
              aria-pressed={selectedServings === servings}
              title={isPhase3 ? 'Servings scaling coming in Phase 3' : undefined}
            >
              <span className="inline-flex items-center gap-1">
                {servings}
                {isPhase3 && <Lock size={12} className="opacity-60" />}
              </span>
            </button>
          )
        })}
      </div>
      {baseServings !== undefined && servingsOptions.includes(baseServings as 2 | 4 | 6) && (
        <p className="text-xs text-text-secondary mt-1">
          Servings scaling coming in Phase 3
        </p>
      )}
    </div>
  )
}
