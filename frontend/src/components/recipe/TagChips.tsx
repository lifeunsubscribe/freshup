import type { TagOption } from '../../api/types'

interface TagChipsProps {
  options: TagOption[]
  /** Tags a card must have. */
  included: string[]
  /** Tags a card must not have. */
  excluded: string[]
  onChange: (included: string[], excluded: string[]) => void
}

/**
 * In-list tag filter: the tags this list's own cards share (3+ cards each),
 * split into what the dish is and what it is served with.
 *
 * Each chip cycles off -> include -> exclude ("no Chicken") -> off. A card
 * passes when it has every included tag and none of the excluded ones, so
 * "Has carrots" + "no Chicken" keeps carrot dishes without chicken.
 */
export default function TagChips({ options, included, excluded, onChange }: TagChipsProps) {
  if (options.length === 0) return null

  const cycle = (key: string) => {
    if (included.includes(key)) {
      onChange(included.filter((k) => k !== key), [...excluded, key])
    } else if (excluded.includes(key)) {
      onChange(included, excluded.filter((k) => k !== key))
    } else {
      onChange([...included, key], excluded)
    }
  }

  const groups: Array<{ kind: TagOption['kind']; label: string }> = [
    { kind: 'main', label: 'Has' },
    { kind: 'side', label: 'Served with' },
  ]

  return (
    <div className="space-y-2">
      {groups.map(({ kind, label }) => {
        const group = options.filter((o) => o.kind === kind)
        if (group.length === 0) return null
        return (
          <div key={kind} role="group" aria-label={label} className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-text-tertiary w-20 shrink-0">{label}</span>
            {group.map((option) => {
              const state = included.includes(option.key) ? 'include' : excluded.includes(option.key) ? 'exclude' : 'off'
              return (
                <button
                  key={option.key}
                  type="button"
                  onClick={() => cycle(option.key)}
                  aria-pressed={state === 'off' ? false : state === 'include' ? true : 'mixed'}
                  aria-label={
                    state === 'exclude'
                      ? `no ${option.label}`
                      : `${option.label} ${option.count}`
                  }
                  title={
                    state === 'off' ? 'Click to require' : state === 'include' ? 'Click to exclude' : 'Click to clear'
                  }
                  className={`px-3 py-1 rounded-full text-xs border transition-colors ${
                    state === 'include'
                      ? 'bg-olive text-cream border-olive'
                      : state === 'exclude'
                        ? 'bg-white text-mocha border-mocha'
                        : 'bg-white text-text-primary border-warm-border hover:bg-warm-gray/30'
                  }`}
                >
                  {state === 'exclude' ? (
                    <>no {option.label}</>
                  ) : (
                    <>
                      {option.label}{' '}
                      <span className={state === 'include' ? 'text-cream/80' : 'text-text-tertiary'}>{option.count}</span>
                    </>
                  )}
                </button>
              )
            })}
          </div>
        )
      })}

      {excluded.length > 0 && (
        <p className="text-xs text-text-tertiary">
          “No” filters only know what recipe names, descriptions and other HelloFresh lists mention — not
          safe for allergies.
        </p>
      )}
    </div>
  )
}
