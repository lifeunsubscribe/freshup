import { useState, useEffect, useMemo, useRef } from 'react'
import { X, ChevronDown } from 'lucide-react'
import { useUpdateProfile } from '../../api/hooks/useAuth'
import { useThemes } from '../../api/hooks/useThemes'
import type { TasteLevel } from '../../api/types'

interface TastePreferencesSectionProps {
  currentTastePreferences: Record<string, TasteLevel>
}

const TASTE_LEVELS: { value: TasteLevel; label: string }[] = [
  { value: 'love', label: 'Love' },
  { value: 'like', label: 'Like' },
  { value: 'less', label: 'Less often' },
  { value: 'never', label: 'Never suggest' },
]

export default function TastePreferencesSection({
  currentTastePreferences,
}: TastePreferencesSectionProps) {
  const [preferences, setPreferences] = useState<Record<string, TasteLevel>>(
    currentTastePreferences
  )
  const [pickerQuery, setPickerQuery] = useState('')
  const [pickerOpen, setPickerOpen] = useState(false)
  const pickerRef = useRef<HTMLDivElement>(null)
  const updateProfile = useUpdateProfile()
  const { data: themes } = useThemes()

  useEffect(() => {
    setPreferences(currentTastePreferences)
  }, [currentTastePreferences])

  // Close picker on outside click
  useEffect(() => {
    if (!pickerOpen) return
    const handler = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setPickerOpen(false)
        setPickerQuery('')
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [pickerOpen])

  const cuisineValues = useMemo(
    () => themes?.find(t => t.key === 'cuisine')?.values ?? [],
    [themes]
  )
  const ingredientValues = useMemo(
    () => themes?.find(t => t.key === 'ingredient')?.values ?? [],
    [themes]
  )

  const valueLabelMap = useMemo(() => {
    const map: Record<string, string> = {}
    for (const v of cuisineValues) map[v.value] = v.label
    for (const v of ingredientValues) map[v.value] = v.label
    return map
  }, [cuisineValues, ingredientValues])

  const cuisineKeys = useMemo(() => new Set(cuisineValues.map(v => v.value)), [cuisineValues])
  const ingredientKeys = useMemo(
    () => new Set(ingredientValues.map(v => v.value)),
    [ingredientValues]
  )

  const cuisinePrefs = useMemo(
    () => Object.entries(preferences).filter(([k]) => cuisineKeys.has(k)),
    [preferences, cuisineKeys]
  )
  const ingredientPrefs = useMemo(
    () => Object.entries(preferences).filter(([k]) => ingredientKeys.has(k)),
    [preferences, ingredientKeys]
  )
  const otherPrefs = useMemo(
    () =>
      Object.entries(preferences).filter(
        ([k]) => !cuisineKeys.has(k) && !ingredientKeys.has(k)
      ),
    [preferences, cuisineKeys, ingredientKeys]
  )

  const availableValues = useMemo(() => {
    const all = [
      ...cuisineValues.map(v => ({ ...v, group: 'Cuisines' })),
      ...ingredientValues.map(v => ({ ...v, group: 'Ingredients' })),
    ]
    return all
      .filter(v => !(v.value in preferences))
      .filter(
        v =>
          !pickerQuery ||
          v.label.toLowerCase().includes(pickerQuery.toLowerCase())
      )
  }, [cuisineValues, ingredientValues, preferences, pickerQuery])

  const savePrefs = (newPrefs: Record<string, TasteLevel>) => {
    setPreferences(newPrefs)
    updateProfile.mutate({ taste_preferences: newPrefs })
  }

  const handleSetLevel = (key: string, level: TasteLevel) => {
    savePrefs({ ...preferences, [key]: level })
  }

  const handleRemove = (key: string) => {
    const newPrefs = { ...preferences }
    delete newPrefs[key]
    savePrefs(newPrefs)
  }

  const handleAdd = (value: string) => {
    savePrefs({ ...preferences, [value]: 'like' })
    setPickerQuery('')
    setPickerOpen(false)
  }

  const renderRow = (key: string, level: TasteLevel) => (
    <div key={key} className="flex items-center gap-2 py-2">
      <span className="w-28 text-sm font-medium text-text-primary truncate flex-shrink-0">
        {valueLabelMap[key] ?? key}
      </span>
      <div className="flex gap-1 flex-1 min-w-0">
        {TASTE_LEVELS.map(tl => (
          <button
            key={tl.value}
            onClick={() => handleSetLevel(key, tl.value)}
            aria-pressed={level === tl.value}
            className={`flex-1 min-w-0 px-1.5 py-1 rounded-button text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-olive focus:ring-offset-1 ${
              level === tl.value
                ? 'bg-olive text-cream'
                : 'bg-cream-dark text-text-secondary hover:bg-mocha/10'
            }`}
          >
            {tl.label}
          </button>
        ))}
      </div>
      <button
        onClick={() => handleRemove(key)}
        className="ml-1 p-1 rounded-full hover:bg-mocha/10 text-text-secondary transition-colors flex-shrink-0"
        aria-label={`Remove ${valueLabelMap[key] ?? key}`}
      >
        <X size={14} />
      </button>
    </div>
  )

  const renderGroup = (label: string, entries: [string, TasteLevel][]) =>
    entries.length > 0 ? (
      <div className="mb-4">
        <p className="text-xs font-semibold text-text-secondary uppercase tracking-wide mb-2">
          {label}
        </p>
        <div className="divide-y divide-warm-border">
          {entries.map(([k, v]) => renderRow(k, v))}
        </div>
      </div>
    ) : null

  return (
    <div className="bg-white rounded-card border border-warm-border p-6">
      <h2 className="text-xl font-semibold text-text-primary mb-1">Tastes.</h2>
      <p className="text-sm text-text-secondary mb-6">
        Shapes what we suggest. Your own searches still show everything.
      </p>

      {renderGroup('Cuisines', cuisinePrefs)}
      {renderGroup('Ingredients', ingredientPrefs)}
      {otherPrefs.length > 0 && (
        <div className="mb-4 divide-y divide-warm-border">
          {otherPrefs.map(([k, v]) => renderRow(k, v))}
        </div>
      )}

      {Object.keys(preferences).length === 0 && (
        <div className="mb-4 p-4 rounded-button bg-cream-dark border border-warm-border">
          <p className="text-sm text-text-secondary text-center">
            No taste preferences set. Use the picker below to add items.
          </p>
        </div>
      )}

      {/* Add picker */}
      <div className="relative mt-4" ref={pickerRef}>
        <div className="flex gap-2 items-center">
          <input
            type="text"
            value={pickerQuery}
            onChange={e => {
              setPickerQuery(e.target.value)
              setPickerOpen(true)
            }}
            onFocus={() => setPickerOpen(true)}
            placeholder="Add cuisine or ingredient…"
            className="flex-1 px-4 py-2 rounded-button border border-warm-border focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent text-sm"
          />
          <button
            onClick={() => setPickerOpen(o => !o)}
            className="p-2 rounded-button border border-warm-border hover:bg-cream-dark transition-colors"
            aria-label="Toggle picker"
          >
            <ChevronDown size={16} />
          </button>
        </div>
        {pickerOpen && availableValues.length > 0 && (
          <div
            data-testid="picker-dropdown"
            className="absolute left-0 right-0 top-full mt-1 bg-white border border-warm-border rounded-card shadow-lg z-10 max-h-60 overflow-y-auto"
          >
            {availableValues.map(v => (
              <button
                key={v.value}
                onClick={() => handleAdd(v.value)}
                className="w-full text-left px-4 py-2 text-sm hover:bg-cream-dark transition-colors"
              >
                <span className="font-medium">{v.label}</span>
                <span className="ml-2 text-xs text-text-secondary">{v.group}</span>
              </button>
            ))}
          </div>
        )}
        {pickerOpen && availableValues.length === 0 && pickerQuery && (
          <div className="absolute left-0 right-0 top-full mt-1 bg-white border border-warm-border rounded-card shadow-lg z-10 p-3">
            <p className="text-sm text-text-secondary">No matches found.</p>
          </div>
        )}
      </div>

      {updateProfile.isError && (
        <div className="mt-4 rounded-button border border-terra bg-terra/10 p-3">
          <p className="text-sm text-terra-dark">
            {updateProfile.error instanceof Error
              ? updateProfile.error.message
              : 'Failed to update taste preferences. Please try again.'}
          </p>
        </div>
      )}
    </div>
  )
}
