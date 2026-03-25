/**
 * Date utilities for timezone-safe date parsing and formatting.
 *
 * The backend sends dates in ISO 8601 format (e.g., "2026-03-20" or "2026-03-20T00:00:00Z").
 * JavaScript's Date constructor interprets date-only strings (YYYY-MM-DD) as UTC midnight,
 * which can cause off-by-one errors when converted to local timezone.
 *
 * These utilities parse date-only strings safely by extracting components and creating
 * Date objects in the user's local timezone, avoiding timezone conversion issues.
 */

/**
 * Parse a date string (YYYY-MM-DD or ISO 8601) to a Date object at local midnight.
 *
 * Handles both date-only strings ("2026-03-20") and ISO datetime strings
 * ("2026-03-20T00:00:00Z") by extracting the date components and creating
 * a Date at midnight in the user's local timezone.
 *
 * This avoids timezone conversion issues where "2026-03-20" parsed as UTC
 * might become "2026-03-19" in timezones west of UTC.
 *
 * @param dateString - Date string in YYYY-MM-DD or ISO 8601 format
 * @returns Date object at midnight in local timezone
 */
export function parseDateOnly(dateString: string): Date {
  // Extract YYYY-MM-DD from the string (handles both date-only and ISO datetime formats)
  const dateMatch = dateString.match(/^(\d{4})-(\d{2})-(\d{2})/)

  if (!dateMatch) {
    throw new Error(`Invalid date format: ${dateString}. Expected YYYY-MM-DD or ISO 8601.`)
  }

  const year = parseInt(dateMatch[1], 10)
  const month = parseInt(dateMatch[2], 10) - 1 // JavaScript months are 0-indexed
  const day = parseInt(dateMatch[3], 10)

  // Create Date at midnight in local timezone using component values
  // This avoids timezone conversion issues from parsing ISO strings
  return new Date(year, month, day, 0, 0, 0, 0)
}

/**
 * Get today's date at midnight in local timezone.
 *
 * @returns Date object representing today at 00:00:00 local time
 */
export function getTodayAtMidnight(): Date {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  return today
}

/**
 * Calculate the number of days between today and a target date.
 *
 * Positive values mean the target date is in the future.
 * Negative values mean the target date is in the past.
 * Zero means the target date is today.
 *
 * @param dateString - Target date string in YYYY-MM-DD or ISO 8601 format
 * @returns Number of days until the target date (can be negative)
 */
export function getDaysUntilDate(dateString: string): number {
  const today = getTodayAtMidnight()
  const targetDate = parseDateOnly(dateString)

  const diffTime = targetDate.getTime() - today.getTime()
  const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24))

  return diffDays
}

/**
 * Calculate the number of days since a past date.
 *
 * Positive values mean the date was in the past.
 * Negative values mean the date is in the future.
 * Zero means the date is today.
 *
 * @param dateString - Past date string in YYYY-MM-DD or ISO 8601 format
 * @returns Number of days since the date (can be negative if in future)
 */
export function getDaysSinceDate(dateString: string): number {
  const today = getTodayAtMidnight()
  const pastDate = parseDateOnly(dateString)

  const diffTime = today.getTime() - pastDate.getTime()
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))

  return diffDays
}

/**
 * Format a date string as a relative time description.
 *
 * Examples (past dates):
 * - 0 days ago: "today"
 * - 1 day ago: "yesterday"
 * - 2-7 days ago: "2d ago", "3d ago", etc.
 * - 8+ days ago: "Mar 15", "Jan 3", etc.
 *
 * Examples (future dates):
 * - 0 days from now: "today"
 * - 1 day from now: "tomorrow"
 * - 2-7 days from now: "in 2d", "in 3d", etc.
 * - 8+ days from now: "Mar 25", "Apr 10", etc.
 *
 * @param dateString - Date string in YYYY-MM-DD or ISO 8601 format
 * @returns Human-readable relative date string
 */
export function formatRelativeDate(dateString: string): string {
  const daysSince = getDaysSinceDate(dateString)

  // Handle today
  if (daysSince === 0) return 'today'

  // Handle past dates
  if (daysSince === 1) return 'yesterday'
  if (daysSince >= 2 && daysSince <= 7) return `${daysSince}d ago`

  // Handle future dates
  if (daysSince === -1) return 'tomorrow'
  if (daysSince <= -2 && daysSince >= -7) return `in ${Math.abs(daysSince)}d`

  // For dates beyond 7 days (past or future), show "Mon DD" format
  const date = parseDateOnly(dateString)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

/**
 * Format an expiration date as a badge-friendly string.
 *
 * Examples:
 * - Expired: "expired"
 * - Expires today: "today"
 * - Expires tomorrow: "tomorrow"
 * - Expires in 2-7 days: "2d", "3d", etc.
 * - Expires in 8+ days: null (don't show badge)
 *
 * @param dateString - Expiration date string in YYYY-MM-DD or ISO 8601 format
 * @returns Badge text or null if more than 7 days away
 */
export function formatExpirationBadge(dateString: string): string | null {
  const daysUntil = getDaysUntilDate(dateString)

  if (daysUntil < 0) return 'expired'
  if (daysUntil === 0) return 'today'
  if (daysUntil === 1) return 'tomorrow'
  if (daysUntil >= 2 && daysUntil <= 7) return `${daysUntil}d`

  return null // Don't show badge if more than 7 days away
}
