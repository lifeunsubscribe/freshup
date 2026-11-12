import { ExternalLink } from 'lucide-react'
import { sourceName } from '../../utils/sourceNames'

interface SourceLineProps {
  sourceType: string
  sourceUrl: string
}

/**
 * "From {Name} · View original" attribution line.
 *
 * Only rendered when source_url is set. Falls back to hostname when the
 * source_type key is not in the display-name map.
 */
export default function SourceLine({ sourceType, sourceUrl }: SourceLineProps) {
  const knownName = sourceName(sourceType)
  const displayName =
    knownName !== sourceType
      ? knownName
      : (() => {
          try {
            return new URL(sourceUrl).hostname.replace(/^www\./, '')
          } catch {
            return sourceType
          }
        })()

  const safeHref = (() => {
    try {
      const { protocol } = new URL(sourceUrl)
      return protocol === 'https:' || protocol === 'http:' ? sourceUrl : '#'
    } catch {
      return '#'
    }
  })()

  return (
    <p className="text-sm text-text-secondary flex items-center gap-1 flex-wrap">
      <span>From {displayName}</span>
      <span aria-hidden="true">·</span>
      <a
        href={safeHref}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-0.5 text-olive hover:text-olive-dark transition-colors"
      >
        View original
        <ExternalLink size={12} aria-hidden="true" />
      </a>
    </p>
  )
}
