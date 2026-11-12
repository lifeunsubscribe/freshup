import { useState } from 'react'
import { ChevronDown, ChevronUp } from 'lucide-react'
import type { SourceStatus } from '../../api/types'
import { sourceName } from '../../utils/sourceNames'
import { relativeTime } from '../../utils/relativeTime'

interface Props {
  source: SourceStatus
  isLoading?: boolean
}

export default function SourceHealthRow({ source, isLoading = false }: Props) {
  const [open, setOpen] = useState(false)

  const name = sourceName(source.source_type)

  if (isLoading) {
    return (
      <div className="flex items-center gap-3 px-3 min-h-[64px] py-2 border-b border-warm-divider last:border-0">
        <span className="w-2 h-2 rounded-full bg-warm flex-shrink-0" aria-hidden="true" />
        <span className="flex-1 min-w-0">
          <span className="block text-[14px] font-medium text-text-primary">{name}</span>
          <span className="block text-[12px] text-text-secondary">Checking…</span>
        </span>
      </div>
    )
  }

  if (source.status === 'healthy') {
    return (
      <div className="flex items-center gap-3 px-3 min-h-[64px] py-2 border-b border-warm-divider last:border-0">
        <span className="w-2 h-2 rounded-full bg-olive flex-shrink-0" aria-hidden="true" />
        <span className="flex-1 min-w-0">
          <span className="block text-[14px] font-medium text-text-primary">{name}</span>
          <span className="block text-[12px] text-olive-dark">
            Checked {source.checked_at ? relativeTime(source.checked_at) : '—'}
          </span>
        </span>
      </div>
    )
  }

  if (source.status === 'never_checked') {
    return (
      <div className="flex items-center gap-3 px-3 min-h-[64px] py-2 border-b border-warm-divider last:border-0">
        <span className="w-2 h-2 rounded-full bg-text-muted flex-shrink-0" aria-hidden="true" />
        <span className="flex-1 min-w-0">
          <span className="block text-[14px] font-medium text-text-primary">{name}</span>
          <span className="block text-[12px] text-text-secondary">Not checked yet</span>
        </span>
      </div>
    )
  }

  // failing state — disclosure row
  const stillWorks =
    source.import_mode === 'link'
      ? 'Pasting a saved page still works.'
      : 'Saved pages are the normal way in for this source; the check could not read one.'

  return (
    <div className="border-b border-warm-divider last:border-0">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-3 min-h-[64px] py-2 text-left"
        aria-expanded={open}
      >
        <span className="w-2 h-2 rounded-full bg-terra flex-shrink-0" aria-hidden="true" />
        <span className="flex-1 min-w-0">
          <span className="block text-[14px] font-medium text-text-primary">{name}</span>
          <span className="block text-[12px] text-terra-dark">
            Failing since {source.failing_since ? relativeTime(source.failing_since) : '—'}
          </span>
        </span>
        {open ? (
          <ChevronUp size={16} className="text-text-tertiary flex-shrink-0" />
        ) : (
          <ChevronDown size={16} className="text-text-tertiary flex-shrink-0" />
        )}
      </button>

      {open && (
        <div className="px-3 pb-3">
          <div className="p-3 rounded-card bg-terra-light">
            {source.detail && (
              <>
                <p className="text-[13px] font-medium text-text-primary">What the check found.</p>
                <p className="text-[13px] leading-normal text-text-primary mt-1">{source.detail}</p>
              </>
            )}
            <p className="text-[12px] leading-[1.4] text-text-secondary mt-2">{stillWorks}</p>
          </div>
        </div>
      )}
    </div>
  )
}
