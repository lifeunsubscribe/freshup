/**
 * Utilities for handling mutation errors in React Query mutations.
 *
 * Provides a custom hook for consistent error handling across all mutation operations:
 * - Auto-dismissing error messages (5 second timeout)
 * - Clear error on retry to prevent stale error messages
 * - Standardized error handler for onError callbacks
 */

import { useState, useEffect, useCallback } from 'react'

export interface MutationErrorHandler {
  /** Current error message, null if no error */
  errorMessage: string | null
  /** Clear the current error message immediately */
  clearError: () => void
  /** Handle an error from a mutation onError callback */
  handleError: (error: Error, userMessage: string) => void
}

/**
 * Custom hook for handling mutation errors with auto-dismiss functionality.
 *
 * Features:
 * - Automatically dismisses error after 5 seconds
 * - Provides clearError function to clear on retry
 * - Provides handleError function for consistent onError callbacks
 * - Logs errors to console for debugging
 *
 * @param autoDismissMs - Time in milliseconds before auto-dismissing (default: 5000)
 * @returns Object with errorMessage, clearError, and handleError
 *
 * @example
 * ```tsx
 * const { errorMessage, clearError, handleError } = useMutationErrorHandler()
 *
 * const mutation = useSomeMutation()
 *
 * const handleAction = () => {
 *   clearError() // Clear stale errors on retry
 *   mutation.mutate(data, {
 *     onError: (error) => handleError(error, 'Failed to perform action. Please try again.')
 *   })
 * }
 *
 * return (
 *   <div>
 *     <button onClick={handleAction}>Do Something</button>
 *     <ErrorBanner message={errorMessage} />
 *   </div>
 * )
 * ```
 */
export function useMutationErrorHandler(
  autoDismissMs: number = 5000
): MutationErrorHandler {
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Auto-dismiss error after specified time
  useEffect(() => {
    if (errorMessage) {
      const timer = setTimeout(() => setErrorMessage(null), autoDismissMs)
      return () => clearTimeout(timer)
    }
  }, [errorMessage, autoDismissMs])

  // Clear error immediately (for retry scenarios)
  const clearError = useCallback(() => {
    setErrorMessage(null)
  }, [])

  // Handle error from mutation onError callback
  const handleError = useCallback((error: Error, userMessage: string) => {
    console.error(userMessage, error)
    setErrorMessage(userMessage)
  }, [])

  return {
    errorMessage,
    clearError,
    handleError,
  }
}
