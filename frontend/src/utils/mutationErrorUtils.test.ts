/**
 * Tests for mutation error handling utilities.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useMutationErrorHandler } from './mutationErrorUtils'

describe('useMutationErrorHandler', () => {
  beforeEach(() => {
    // Clear console.error mock before each test
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('should initialize with null error message', () => {
    const { result } = renderHook(() => useMutationErrorHandler())
    expect(result.current.errorMessage).toBeNull()
  })

  it('should set error message when handleError is called', () => {
    const { result } = renderHook(() => useMutationErrorHandler())
    const testError = new Error('Test error')
    const userMessage = 'Failed to perform action. Please try again.'

    act(() => {
      result.current.handleError(testError, userMessage)
    })

    expect(result.current.errorMessage).toBe(userMessage)
    expect(console.error).toHaveBeenCalledWith(userMessage, testError)
  })

  it('should clear error message when clearError is called', () => {
    const { result } = renderHook(() => useMutationErrorHandler())
    const testError = new Error('Test error')

    act(() => {
      result.current.handleError(testError, 'Error message')
    })

    expect(result.current.errorMessage).toBe('Error message')

    act(() => {
      result.current.clearError()
    })

    expect(result.current.errorMessage).toBeNull()
  })

  it('should auto-dismiss error after default timeout (5 seconds)', { timeout: 7000 }, async () => {
    const { result } = renderHook(() => useMutationErrorHandler())
    const testError = new Error('Test error')

    act(() => {
      result.current.handleError(testError, 'Error message')
    })

    expect(result.current.errorMessage).toBe('Error message')

    // Wait for auto-dismiss (5000ms + buffer)
    await waitFor(
      () => {
        expect(result.current.errorMessage).toBeNull()
      },
      { timeout: 6000 }
    )
  })

  it('should auto-dismiss error after custom timeout', async () => {
    const customTimeout = 1000
    const { result } = renderHook(() => useMutationErrorHandler(customTimeout))
    const testError = new Error('Test error')

    act(() => {
      result.current.handleError(testError, 'Error message')
    })

    expect(result.current.errorMessage).toBe('Error message')

    // Wait for auto-dismiss (1000ms + buffer)
    await waitFor(
      () => {
        expect(result.current.errorMessage).toBeNull()
      },
      { timeout: 2000 }
    )
  })

  it('should clear timeout when clearError is called before auto-dismiss', async () => {
    const { result } = renderHook(() => useMutationErrorHandler())
    const testError = new Error('Test error')

    act(() => {
      result.current.handleError(testError, 'Error message')
    })

    expect(result.current.errorMessage).toBe('Error message')

    // Clear before timeout
    act(() => {
      result.current.clearError()
    })

    expect(result.current.errorMessage).toBeNull()

    // Wait to ensure no auto-dismiss happens after manual clear
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(result.current.errorMessage).toBeNull()
  })

  it('should handle multiple errors in succession', () => {
    const { result } = renderHook(() => useMutationErrorHandler())
    const error1 = new Error('Error 1')
    const error2 = new Error('Error 2')

    act(() => {
      result.current.handleError(error1, 'First error message')
    })

    expect(result.current.errorMessage).toBe('First error message')

    act(() => {
      result.current.handleError(error2, 'Second error message')
    })

    expect(result.current.errorMessage).toBe('Second error message')
    expect(console.error).toHaveBeenCalledTimes(2)
  })

  it('should maintain stable function references', () => {
    const { result, rerender } = renderHook(() => useMutationErrorHandler())

    const initialClearError = result.current.clearError
    const initialHandleError = result.current.handleError

    rerender()

    expect(result.current.clearError).toBe(initialClearError)
    expect(result.current.handleError).toBe(initialHandleError)
  })
})
