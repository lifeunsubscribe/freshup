type ModeType = 'scan' | 'list' | 'manual'

interface ModeSelectorProps {
  activeMode: ModeType
  onModeChange: (mode: ModeType) => void
}

/**
 * ModeSelector component for I Shopped flow navigation
 *
 * Features:
 * - Three tabs: Scan receipt | From list | Add manually
 * - Active tab indicated with olive underline
 * - Horizontal scroll on mobile if needed
 */
export default function ModeSelector({ activeMode, onModeChange }: ModeSelectorProps) {
  const modes: Array<{ id: ModeType; label: string }> = [
    { id: 'scan', label: 'Scan receipt' },
    { id: 'list', label: 'From list' },
    { id: 'manual', label: 'Add manually' },
  ]

  return (
    <div className="border-b border-warm-border mb-6">
      <div className="flex gap-6 overflow-x-auto">
        {modes.map((mode) => (
          <button
            key={mode.id}
            onClick={() => onModeChange(mode.id)}
            className={`
              pb-3 px-1 text-sm font-medium whitespace-nowrap transition-colors
              ${activeMode === mode.id
                ? 'text-olive border-b-2 border-olive'
                : 'text-text-secondary hover:text-text-primary'
              }
            `}
            aria-label={mode.label}
            aria-current={activeMode === mode.id ? 'page' : undefined}
          >
            {mode.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export type { ModeType }
