import { useEffect, useRef, useState } from 'react'
import { ChevronDown, ChevronUp, X } from 'lucide-react'
import type { Theme } from '../../api/types'

export interface ThemeFilter {
  theme: string
  value: string
}

/** Themes tucked behind the "Advanced" toggle rather than shown in the bar. */
const ADVANCED_THEMES = ['ingredient']

interface ThemeBarProps {
  themes: Theme[]
  /** Theme whose page is showing ("See all"), if any. */
  activeTheme: string | null
  /** Values currently filtering the page; at most one per theme, applied together. */
  activeFilters: ThemeFilter[]
  /** Picking the already-selected value clears that theme's filter. */
  onSelectValue: (filter: ThemeFilter) => void
  onSeeAll: (theme: string) => void
  onClear: () => void
}

/**
 * ThemeBar — one dropdown per recipe theme (Cuisine, Dish type, ...).
 *
 * Picking values filters the current page; filters from different themes
 * apply together. "See all" opens the theme's page, where every list comes
 * from that theme. Less-used themes sit behind "Advanced". Wraps rather than
 * scrolls horizontally so dropdowns are never clipped.
 */
export default function ThemeBar({
  themes,
  activeTheme,
  activeFilters,
  onSelectValue,
  onSeeAll,
  onClear,
}: ThemeBarProps) {
  const [openTheme, setOpenTheme] = useState<string | null>(null)
  const barRef = useRef<HTMLDivElement>(null)

  const visible = themes.filter((t) => t.values.length > 0)
  const primary = visible.filter((t) => !ADVANCED_THEMES.includes(t.key))
  const advanced = visible.filter((t) => ADVANCED_THEMES.includes(t.key))
  const advancedInUse =
    advanced.some((t) => t.key === activeTheme) ||
    activeFilters.some((f) => ADVANCED_THEMES.includes(f.theme))
  const [advancedOpen, setAdvancedOpen] = useState(advancedInUse)
  const showAdvanced = advancedOpen || advancedInUse

  useEffect(() => {
    if (!openTheme) return
    const onPointerDown = (e: MouseEvent) => {
      if (barRef.current && !barRef.current.contains(e.target as Node)) setOpenTheme(null)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpenTheme(null)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [openTheme])

  const renderDropdown = (theme: Theme) => {
    const active = activeFilters.find((f) => f.theme === theme.key)
    const selectedLabel = active ? theme.values.find((v) => v.value === active.value)?.label : undefined
    const highlighted = !!active || activeTheme === theme.key
    const isOpen = openTheme === theme.key

    return (
      <div key={theme.key} className="relative">
        <button
          type="button"
          onClick={() => setOpenTheme(isOpen ? null : theme.key)}
          aria-haspopup="menu"
          aria-expanded={isOpen}
          className={`h-9 px-3 rounded-full border text-sm inline-flex items-center gap-1.5 transition-colors ${
            highlighted
              ? 'bg-olive text-white border-olive'
              : 'bg-white text-text-primary border-warm-border hover:border-text-tertiary'
          }`}
        >
          {selectedLabel ? `${theme.label}: ${selectedLabel}` : theme.label}
          <ChevronDown size={14} />
        </button>

        {isOpen && (
          <div
            role="menu"
            aria-label={theme.label}
            className="absolute left-0 top-full mt-1 z-30 min-w-[220px] max-h-80 overflow-y-auto bg-white rounded-card border border-warm-border shadow-md py-1"
          >
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpenTheme(null)
                onSeeAll(theme.key)
              }}
              className="w-full text-left px-3 py-2 text-sm font-medium text-olive hover:bg-warm-gray/40"
            >
              See all {theme.label.toLowerCase()}
            </button>
            <div className="my-1 border-t border-warm-border" />
            {theme.values.map((value) => {
              const total = value.library_count + value.collections.reduce((n, c) => n + c.card_count, 0)
              const selected = active?.value === value.value
              return (
                <button
                  key={value.value}
                  type="button"
                  role="menuitemradio"
                  aria-checked={selected}
                  onClick={() => {
                    setOpenTheme(null)
                    onSelectValue({ theme: theme.key, value: value.value })
                  }}
                  className={`w-full flex items-center justify-between gap-3 px-3 py-2 text-sm hover:bg-warm-gray/40 ${
                    selected ? 'text-olive font-medium' : 'text-text-primary'
                  }`}
                >
                  <span>{value.label}</span>
                  {total > 0 && <span className="text-xs text-text-tertiary">{total}</span>}
                </button>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  return (
    <nav ref={barRef} aria-label="Recipe themes" className="border-b border-warm-border pb-3 space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {primary.map(renderDropdown)}

        {advanced.length > 0 && (
          <button
            type="button"
            onClick={() => setAdvancedOpen(!showAdvanced)}
            aria-expanded={showAdvanced}
            // Can't collapse while an advanced filter is in use, or it would be hidden
            disabled={advancedInUse}
            className="h-9 px-3 rounded-full text-sm text-text-secondary hover:text-text-primary inline-flex items-center gap-1 disabled:cursor-default disabled:hover:text-text-secondary"
          >
            Advanced
            {showAdvanced ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}

        {(activeFilters.length > 0 || activeTheme) && (
          <button
            type="button"
            onClick={onClear}
            className="h-9 px-3 rounded-full text-sm text-text-secondary hover:text-text-primary inline-flex items-center gap-1"
          >
            <X size={14} />
            Clear
          </button>
        )}
      </div>

      {showAdvanced && advanced.length > 0 && (
        <div className="flex flex-wrap items-center gap-2" aria-label="Advanced filters" role="group">
          {advanced.map(renderDropdown)}
        </div>
      )}
    </nav>
  )
}
