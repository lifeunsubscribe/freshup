/**
 * Returns a human-readable relative time string for an ISO datetime string.
 *
 * Examples: "just now", "3 hours ago", "2 days ago", "1 hour ago"
 *
 * Uses the coarser of the two relevant units: minutes < 2 → "just now",
 * minutes < 60 → minutes, hours < 24 → hours, else days.
 */
export function relativeTime(isoString: string): string {
  const then = new Date(isoString).getTime()
  const diffMs = Date.now() - then
  const diffMinutes = Math.floor(diffMs / (1000 * 60))

  if (diffMinutes < 2) return 'just now'

  if (diffMinutes < 60) {
    return diffMinutes === 1 ? '1 minute ago' : `${diffMinutes} minutes ago`
  }

  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) {
    return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`
  }

  const diffDays = Math.floor(diffHours / 24)
  return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`
}
