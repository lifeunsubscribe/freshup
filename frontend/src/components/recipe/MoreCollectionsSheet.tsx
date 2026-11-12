import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Sheet from '../ui/Sheet'
import type { CollectionSummary } from '../../api/types'

interface MoreCollectionsSheetProps {
  open: boolean
  onClose: () => void
  collections: CollectionSummary[]
}

export default function MoreCollectionsSheet({ open, onClose, collections }: MoreCollectionsSheetProps) {
  const [filter, setFilter] = useState('')
  const navigate = useNavigate()

  const filtered = collections.filter((c) =>
    c.name.toLowerCase().includes(filter.toLowerCase())
  )

  function handleSelect(slug: string) {
    onClose()
    navigate(`/browse/hellofresh/${slug}`)
  }

  return (
    <Sheet open={open} onClose={onClose} title="Collections">
      <div className="px-4 pt-2 pb-3">
        <input
          type="search"
          placeholder="Filter collections…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full h-10 rounded-md border border-warm-border bg-white px-3 text-sm text-text-primary placeholder:text-text-tertiary focus:outline-none focus:ring-2 focus:ring-olive/40"
          aria-label="Filter collections"
        />
      </div>

      <ul role="list" className="pb-4">
        {filtered.length === 0 && (
          <li className="px-4 py-3 text-sm text-text-secondary">No collections match.</li>
        )}
        {filtered.map((c) => (
          <li key={c.slug}>
            <button
              onClick={() => handleSelect(c.slug)}
              className="w-full text-left px-4 py-3 flex items-center justify-between hover:bg-warm-gray transition-colors"
              aria-label={c.name}
            >
              <span className="text-sm text-text-primary">{c.name}</span>
              {c.card_count > 0 && (
                <span className="text-xs text-text-secondary">
                  {c.card_count} recipe{c.card_count === 1 ? '' : 's'}
                </span>
              )}
            </button>
          </li>
        ))}
      </ul>
    </Sheet>
  )
}
