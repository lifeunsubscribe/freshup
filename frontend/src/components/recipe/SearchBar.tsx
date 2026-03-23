import { Search, X } from 'lucide-react'
import { useState, useEffect } from 'react'

interface SearchBarProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  debounceMs?: number
}

/**
 * SearchBar component for recipe search
 *
 * Features:
 * - Search icon on left
 * - Clear button (X) on right when text is present
 * - Auto-triggers grid view when user types
 * - Returns to carousel view when cleared
 * - Debounced input to prevent excessive updates
 */
export default function SearchBar({ value, onChange, placeholder = 'Search recipes...', debounceMs = 300 }: SearchBarProps) {
  const [localValue, setLocalValue] = useState(value)

  // Sync local value with prop value when it changes externally (e.g., clear button from parent)
  useEffect(() => {
    setLocalValue(value)
  }, [value])

  // Debounce the onChange callback
  useEffect(() => {
    const timer = setTimeout(() => {
      if (localValue !== value) {
        onChange(localValue)
      }
    }, debounceMs)

    return () => clearTimeout(timer)
  }, [localValue, debounceMs, onChange, value])

  const handleClear = () => {
    setLocalValue('')
    onChange('')
  }

  return (
    <div className="relative">
      {/* Search icon */}
      <Search
        size={18}
        className="absolute left-3 top-1/2 -translate-y-1/2 text-text-tertiary"
      />

      {/* Input field */}
      <input
        type="text"
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-10 pr-10 py-2.5 rounded-lg border border-warm-border bg-white text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
      />

      {/* Clear button */}
      {localValue && (
        <button
          onClick={handleClear}
          className="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-warm-gray rounded-full transition-colors"
          aria-label="Clear search"
        >
          <X size={16} className="text-text-tertiary" />
        </button>
      )}
    </div>
  )
}
