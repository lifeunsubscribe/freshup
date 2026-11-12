import { Link } from 'react-router-dom'
import { failingSources } from '../../api/hooks/useSourceHealth'
import { sourceName } from '../../utils/sourceNames'
import type { SourceStatus } from '../../api/types'

interface Props {
  statuses: SourceStatus[] | undefined
  isLoading: boolean
  isError: boolean
  isCoordinator: boolean
}

// Returns day name for dates within the past 7 days, otherwise a relative string.
function formatSince(failingSince: string | null): string | null {
  if (!failingSince) return null
  const date = new Date(failingSince)
  if (isNaN(date.getTime())) return null
  const diffDays = Math.floor((Date.now() - date.getTime()) / (1000 * 60 * 60 * 24))
  if (diffDays < 7) return date.toLocaleDateString('en-US', { weekday: 'long' })
  if (diffDays < 14) return 'last week'
  return `${Math.floor(diffDays / 7)} weeks ago`
}

export default function SourceFailingAlert({ statuses, isLoading, isError, isCoordinator }: Props) {
  if (isLoading || isError || !statuses) return null

  const failing = failingSources(statuses)
  if (failing.length === 0) return null

  let mainText: string
  if (failing.length === 1) {
    const f = failing[0]
    const name = sourceName(f.source_type)
    const since = formatSince(f.failing_since)
    mainText = since
      ? `${name} imports have been failing since ${since}.`
      : `${name} imports have been failing.`
  } else {
    const names = failing.map(f => sourceName(f.source_type))
    const joined =
      names.length === 2
        ? `${names[0]} and ${names[1]}`
        : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`
    mainText = `${joined} imports have been failing.`
  }

  return (
    <div className="mx-4 mb-3 p-3 rounded-card bg-mocha-light border border-mocha-border">
      <p className="text-[13px] leading-normal text-text-primary">{mainText}</p>
      <p className="text-[12px] leading-[1.4] text-mocha-dark mt-0.5">
        The saved page still works in the meantime.
      </p>
      {isCoordinator && (
        <Link
          to="/profile#recipe-sources"
          className="inline-flex items-center min-h-[44px] -mb-3 text-[12px] text-olive"
        >
          See what the check found →
        </Link>
      )}
    </div>
  )
}
