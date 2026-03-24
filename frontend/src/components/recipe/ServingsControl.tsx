interface ServingsControlProps {
  selectedServings: 2 | 4 | 6
  onServingsChange: (servings: 2 | 4 | 6) => void
}

/**
 * ServingsControl - Segmented control for selecting serving sizes
 *
 * Features:
 * - Three options: 2, 4, 6 servings
 * - Segmented button group styling
 * - Active state with olive background
 * - Scales ingredient quantities in parent component
 */
export default function ServingsControl({ selectedServings, onServingsChange }: ServingsControlProps) {
  const servingsOptions: Array<2 | 4 | 6> = [2, 4, 6]

  return (
    <div className="mb-4">
      <label className="block text-sm font-medium text-text-primary mb-2">
        Servings
      </label>
      <div className="inline-flex rounded-button border border-warm-border bg-cream overflow-hidden">
        {servingsOptions.map((servings) => (
          <button
            key={servings}
            onClick={() => onServingsChange(servings)}
            className={`
              px-6 py-2 text-sm font-medium transition-colors
              ${selectedServings === servings
                ? 'bg-olive text-cream'
                : 'bg-cream text-text-primary hover:bg-cream-dark'
              }
              ${servings !== servingsOptions[servingsOptions.length - 1] ? 'border-r border-warm-border' : ''}
            `}
            aria-label={`${servings} servings`}
            aria-pressed={selectedServings === servings}
          >
            {servings}
          </button>
        ))}
      </div>
    </div>
  )
}
