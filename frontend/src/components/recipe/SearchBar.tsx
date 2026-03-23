import { Search, X } from 'lucide-react'

interface SearchBarProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

/**
 * SearchBar component for recipe search
 *
 * Features:
 * - Search icon on left
 * - Clear button (X) on right when text is present
 * - Auto-triggers grid view when user types
 * - Returns to carousel view when cleared
 */
export default function SearchBar({ value, onChange, placeholder = 'Search recipes...' }: SearchBarProps) {
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
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full pl-10 pr-10 py-2.5 rounded-lg border border-warm-border bg-white text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-olive focus:border-transparent"
      />

      {/* Clear button */}
      {value && (
        <button
          onClick={() => onChange('')}
          className="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-warm-gray rounded-full transition-colors"
          aria-label="Clear search"
        >
          <X size={16} className="text-text-tertiary" />
        </button>
      )}
    </div>
  )
}
