/**
 * ErrorBanner component for displaying mutation error messages.
 *
 * Provides consistent error message styling across the application with:
 * - Red background (bg-red-50) with red border (border-red-200)
 * - Red text (text-red-800) for readability
 * - Rounded corners (rounded-md)
 * - Proper ARIA attributes for accessibility
 * - Null/undefined handling (renders nothing if no message)
 */

export interface ErrorBannerProps {
  /** Error message to display, or null/undefined to hide */
  message: string | null | undefined
}

/**
 * Display an error message banner.
 *
 * @example
 * ```tsx
 * <ErrorBanner message={errorMessage} />
 * ```
 */
export default function ErrorBanner({ message }: ErrorBannerProps) {
  if (!message) return null

  return (
    <div
      className="mt-1 px-3 py-2 bg-red-50 border border-red-200 rounded-md text-sm text-red-800"
      role="alert"
    >
      {message}
    </div>
  )
}
