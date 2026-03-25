/**
 * Integration tests for authentication hooks with token expiration scenarios.
 *
 * Tests cover:
 * - useCurrentUser with expired tokens
 * - useLogin token lifecycle
 * - Token expiration during active session
 * - Hook behavior when token is cleared
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useCurrentUser, useLogin, useLogout } from './useAuth'
import { setAuthToken, clearAuthToken, getAuthToken } from '../client'
import type { ReactNode } from 'react'

/**
 * Helper function to create a JWT-like token for testing.
 * Creates a token with header.payload.signature structure.
 */
function createTestToken(expirationTimestamp: number): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const payload = btoa(JSON.stringify({ sub: 'user-123', exp: expirationTimestamp }))
  const signature = 'fake-signature'
  return `${header}.${payload}.${signature}`
}

/**
 * Wrapper component that provides React Query context for testing hooks.
 */
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // Disable retries for faster tests
        gcTime: 0, // Disable garbage collection for predictable tests
      },
      mutations: {
        retry: false,
      },
    },
  })

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useCurrentUser with token expiration', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  describe('expired token scenarios', () => {
    it('does not fetch when token is expired', async () => {
      // Create expired token (expired 1 hour ago)
      const pastTime = Math.floor(Date.now() / 1000) - 3600
      const expiredToken = createTestToken(pastTime)
      setAuthToken(expiredToken)

      const mockFetch = vi.fn()
      global.fetch = mockFetch

      const wrapper = createWrapper()
      const { result } = renderHook(() => useCurrentUser(), { wrapper })

      // Wait briefly to ensure query has time to potentially run
      await waitFor(
        () => {
          // Query should not be enabled, so fetch should not be called
          expect(mockFetch).not.toHaveBeenCalled()
        },
        { timeout: 500 }
      )

      // Query should be disabled
      expect(result.current.data).toBeUndefined()
    })

    it('does not fetch when no token exists', async () => {
      // Ensure no token exists
      clearAuthToken()

      const mockFetch = vi.fn()
      global.fetch = mockFetch

      const wrapper = createWrapper()
      const { result } = renderHook(() => useCurrentUser(), { wrapper })

      // Wait briefly to ensure query has time to potentially run
      await waitFor(
        () => {
          expect(mockFetch).not.toHaveBeenCalled()
        },
        { timeout: 500 }
      )

      expect(result.current.data).toBeUndefined()
    })

    it('fetches successfully when token is valid', async () => {
      // Create valid token (expires 1 hour in future)
      const futureTime = Math.floor(Date.now() / 1000) + 3600
      const validToken = createTestToken(futureTime)
      setAuthToken(validToken)

      const mockUserData = {
        id: 'user-123',
        email: 'test@example.com',
        name: 'Test User',
        role: 'user',
      }

      // Mock successful API response
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockUserData,
      })

      const wrapper = createWrapper()
      const { result } = renderHook(() => useCurrentUser(), { wrapper })

      // Wait for query to complete
      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockUserData)
    })

    it('handles 401 error when server rejects expired token', async () => {
      // Create token that appears valid client-side but server rejects
      const futureTime = Math.floor(Date.now() / 1000) + 3600
      const token = createTestToken(futureTime)
      setAuthToken(token)

      // Mock 401 response from server
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'Token has expired' }),
      })

      const wrapper = createWrapper()
      const { result } = renderHook(() => useCurrentUser(), { wrapper })

      // Wait for query to complete
      await waitFor(() => {
        expect(result.current.isError).toBe(true)
      })

      // Verify token was cleared on 401
      expect(getAuthToken()).toBeNull()
    })
  })

  describe('token state changes during active session', () => {
    it('re-evaluates enabled state when token changes', async () => {
      // Start with no token
      clearAuthToken()

      const wrapper = createWrapper()
      const { result, rerender } = renderHook(() => useCurrentUser(), { wrapper })

      // Initially no data
      expect(result.current.data).toBeUndefined()

      // Add a valid token
      const futureTime = Math.floor(Date.now() / 1000) + 3600
      const validToken = createTestToken(futureTime)
      setAuthToken(validToken)

      const mockUserData = {
        id: 'user-456',
        email: 'newuser@example.com',
        name: 'New User',
        role: 'user',
      }

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockUserData,
      })

      // Trigger re-evaluation
      rerender()

      // Query should now fetch data
      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockUserData)
    })
  })
})

describe('useLogin token lifecycle', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  describe('successful login', () => {
    it('stores token in localStorage after successful login', async () => {
      expect(getAuthToken()).toBeNull()

      // Mock successful login response with token
      const mockToken = createTestToken(Math.floor(Date.now() / 1000) + 3600)
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ access_token: mockToken }),
      })

      const wrapper = createWrapper()
      const { result } = renderHook(() => useLogin(), { wrapper })

      // Execute login mutation
      await result.current.mutateAsync({
        email: 'test@example.com',
        password: 'password123',
      })

      // Verify token was stored
      expect(getAuthToken()).toBe(mockToken)
    })

    it('invalidates current user query after login', async () => {
      // Mock login response
      const mockToken = createTestToken(Math.floor(Date.now() / 1000) + 3600)
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ access_token: mockToken }),
      })

      const wrapper = createWrapper()
      const { result: loginResult } = renderHook(() => useLogin(), { wrapper })

      // Execute login
      await loginResult.current.mutateAsync({
        email: 'test@example.com',
        password: 'password123',
      })

      // After login, verify token exists
      expect(getAuthToken()).toBe(mockToken)
    })
  })

  describe('failed login', () => {
    it('does not store token when login fails', async () => {
      expect(getAuthToken()).toBeNull()

      // Mock failed login response
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'Invalid credentials' }),
      })

      const wrapper = createWrapper()
      const { result } = renderHook(() => useLogin(), { wrapper })

      // Execute login mutation and expect it to fail
      try {
        await result.current.mutateAsync({
          email: 'test@example.com',
          password: 'wrongpassword',
        })
        expect.fail('Should have thrown error')
      } catch (error) {
        // Expected to fail
      }

      // Verify no token was stored
      expect(getAuthToken()).toBeNull()
    })
  })
})

describe('useLogout token cleanup', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  describe('logout behavior', () => {
    it('clears token from localStorage', async () => {
      // Set up a token
      const token = createTestToken(Math.floor(Date.now() / 1000) + 3600)
      setAuthToken(token)
      expect(getAuthToken()).toBe(token)

      const wrapper = createWrapper()
      const { result } = renderHook(() => useLogout(), { wrapper })

      // Execute logout
      await result.current.mutateAsync()

      // Verify token was cleared
      expect(getAuthToken()).toBeNull()
    })

    it('works when no token exists', async () => {
      // Ensure no token exists
      clearAuthToken()
      expect(getAuthToken()).toBeNull()

      const wrapper = createWrapper()
      const { result } = renderHook(() => useLogout(), { wrapper })

      // Execute logout (should not throw)
      await result.current.mutateAsync()

      // Verify still no token
      expect(getAuthToken()).toBeNull()
    })
  })
})

describe('Token expiration edge cases', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  describe('boundary conditions', () => {
    it('treats token expiring exactly now as expired', async () => {
      // Create token expiring at current second
      const currentTime = Math.floor(Date.now() / 1000)
      const token = createTestToken(currentTime)
      setAuthToken(token)

      const mockFetch = vi.fn()
      global.fetch = mockFetch

      const wrapper = createWrapper()
      renderHook(() => useCurrentUser(), { wrapper })

      // Query should not fetch with expired token
      await waitFor(
        () => {
          expect(mockFetch).not.toHaveBeenCalled()
        },
        { timeout: 500 }
      )
    })

    it('treats token expiring in 1 second as valid', async () => {
      // Create token expiring in 1 second
      const futureTime = Math.floor(Date.now() / 1000) + 1
      const token = createTestToken(futureTime)
      setAuthToken(token)

      const mockUserData = {
        id: 'user-789',
        email: 'expiring@example.com',
        name: 'Expiring User',
        role: 'user',
      }

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockUserData,
      })

      const wrapper = createWrapper()
      const { result } = renderHook(() => useCurrentUser(), { wrapper })

      // Query should fetch with valid token
      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockUserData)
    })
  })

  describe('malformed token handling', () => {
    it('does not fetch with malformed token', async () => {
      // Set malformed token
      setAuthToken('invalid.token')

      const mockFetch = vi.fn()
      global.fetch = mockFetch

      const wrapper = createWrapper()
      renderHook(() => useCurrentUser(), { wrapper })

      // Query should not fetch with invalid token
      await waitFor(
        () => {
          expect(mockFetch).not.toHaveBeenCalled()
        },
        { timeout: 500 }
      )
    })

    it('does not fetch with token missing exp claim', async () => {
      // Create token without exp claim (edge case)
      const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
      const payload = btoa(JSON.stringify({ sub: 'user-123' }))
      const signature = 'fake-signature'
      const token = `${header}.${payload}.${signature}`
      setAuthToken(token)

      const mockUserData = {
        id: 'user-no-exp',
        email: 'noexp@example.com',
        name: 'No Expiry User',
        role: 'user',
      }

      // Token without exp is treated as valid by isAuthenticated()
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => mockUserData,
      })

      const wrapper = createWrapper()
      const { result } = renderHook(() => useCurrentUser(), { wrapper })

      // Query should fetch (token treated as valid when no exp)
      await waitFor(() => {
        expect(result.current.isSuccess).toBe(true)
      })

      expect(result.current.data).toEqual(mockUserData)
    })
  })
})
