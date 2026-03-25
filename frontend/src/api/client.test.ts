/**
 * Unit tests for API client authentication token handling.
 *
 * Tests cover:
 * - Token storage and retrieval
 * - Token expiration validation
 * - API client error handling for expired tokens
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import {
  setAuthToken,
  getAuthToken,
  clearAuthToken,
  isAuthenticated,
  apiClient,
  ApiException,
} from './client'

describe('Auth Token Storage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('setAuthToken', () => {
    it('stores token in localStorage', () => {
      const token = 'test-token-123'
      setAuthToken(token)
      expect(localStorage.getItem('auth_token')).toBe(token)
    })
  })

  describe('getAuthToken', () => {
    it('retrieves token from localStorage', () => {
      const token = 'test-token-456'
      localStorage.setItem('auth_token', token)
      expect(getAuthToken()).toBe(token)
    })

    it('returns null when no token exists', () => {
      expect(getAuthToken()).toBeNull()
    })
  })

  describe('clearAuthToken', () => {
    it('removes token from localStorage', () => {
      localStorage.setItem('auth_token', 'test-token-789')
      clearAuthToken()
      expect(localStorage.getItem('auth_token')).toBeNull()
    })
  })
})

describe('isAuthenticated', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  afterEach(() => {
    localStorage.clear()
  })

  describe('with no token', () => {
    it('returns false when no token exists', () => {
      expect(isAuthenticated()).toBe(false)
    })
  })

  describe('with malformed tokens', () => {
    it('returns false for empty string token', () => {
      setAuthToken('')
      expect(isAuthenticated()).toBe(false)
    })

    it('returns false for token with wrong number of parts', () => {
      setAuthToken('invalid.token')
      expect(isAuthenticated()).toBe(false)
    })

    it('returns false for token with four parts', () => {
      setAuthToken('invalid.token.with.toomany')
      expect(isAuthenticated()).toBe(false)
    })

    it('returns false for token with invalid base64url encoding', () => {
      // Create a token with invalid base64url in payload section
      setAuthToken('header.@@@invalid@@@.signature')
      expect(isAuthenticated()).toBe(false)
    })

    it('returns false for token with non-JSON payload', () => {
      // Create a token with valid base64url but invalid JSON
      // "not-json" in base64url is "bm90LWpzb24"
      setAuthToken('header.bm90LWpzb24.signature')
      expect(isAuthenticated()).toBe(false)
    })
  })

  describe('with valid token structure', () => {
    /**
     * Helper function to create a JWT-like token for testing.
     * Creates a token with header.payload.signature structure where:
     * - header: {"alg":"HS256","typ":"JWT"} (standard JWT header)
     * - payload: contains exp claim with provided timestamp
     * - signature: fake signature (we're only testing expiration logic)
     */
    function createTestToken(expirationTimestamp: number): string {
      const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
      const payload = btoa(JSON.stringify({ sub: 'user-123', exp: expirationTimestamp }))
      const signature = 'fake-signature'
      return `${header}.${payload}.${signature}`
    }

    it('returns true for valid non-expired token', () => {
      // Create token that expires 1 hour in the future
      const futureTime = Math.floor(Date.now() / 1000) + 3600
      const token = createTestToken(futureTime)
      setAuthToken(token)
      expect(isAuthenticated()).toBe(true)
    })

    it('returns false for expired token', () => {
      // Create token that expired 1 hour ago
      const pastTime = Math.floor(Date.now() / 1000) - 3600
      const token = createTestToken(pastTime)
      setAuthToken(token)
      expect(isAuthenticated()).toBe(false)
    })

    it('returns false for token expiring exactly now', () => {
      // Create token that expires at current second
      const currentTime = Math.floor(Date.now() / 1000)
      const token = createTestToken(currentTime)
      setAuthToken(token)
      expect(isAuthenticated()).toBe(false)
    })

    it('returns false for token expired by 1 second', () => {
      // Create token that expired 1 second ago
      const justExpired = Math.floor(Date.now() / 1000) - 1
      const token = createTestToken(justExpired)
      setAuthToken(token)
      expect(isAuthenticated()).toBe(false)
    })

    it('returns true for token expiring in 1 second', () => {
      // Create token that expires in 1 second
      const aboutToExpire = Math.floor(Date.now() / 1000) + 1
      const token = createTestToken(aboutToExpire)
      setAuthToken(token)
      expect(isAuthenticated()).toBe(true)
    })

    it('returns true for token without exp claim', () => {
      // Create token without expiration (edge case - shouldn't happen with proper JWTs)
      const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
      const payload = btoa(JSON.stringify({ sub: 'user-123' }))
      const signature = 'fake-signature'
      const token = `${header}.${payload}.${signature}`
      setAuthToken(token)
      expect(isAuthenticated()).toBe(true)
    })
  })

  describe('with base64url encoding edge cases', () => {
    /**
     * JWT uses base64url encoding (RFC 4648), which differs from standard base64:
     * - Uses '-' instead of '+'
     * - Uses '_' instead of '/'
     * - Omits padding '=' characters
     */
    it('correctly decodes base64url with special characters', () => {
      // Create a payload that requires base64url special characters
      const payload = {
        sub: 'user-123',
        exp: Math.floor(Date.now() / 1000) + 3600,
        data: 'test>>data',
      }

      // Manually encode using base64url
      const jsonStr = JSON.stringify(payload)
      const base64 = btoa(jsonStr)
      const base64url = base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')

      const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
      const token = `${header}.${base64url}.signature`
      setAuthToken(token)

      expect(isAuthenticated()).toBe(true)
    })

    it('handles payload requiring padding', () => {
      // Create short payload that needs padding when decoded
      const payload = { sub: 'u1', exp: Math.floor(Date.now() / 1000) + 3600 }
      const jsonStr = JSON.stringify(payload)
      const base64 = btoa(jsonStr)
      const base64url = base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '')

      const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
      const token = `${header}.${base64url}.signature`
      setAuthToken(token)

      expect(isAuthenticated()).toBe(true)
    })
  })
})

describe('apiClient with expired tokens', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  function createTestToken(expirationTimestamp: number): string {
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
    const payload = btoa(JSON.stringify({ sub: 'user-123', exp: expirationTimestamp }))
    const signature = 'fake-signature'
    return `${header}.${payload}.${signature}`
  }

  describe('token expiration handling', () => {
    it('clears token on 401 Unauthorized response', async () => {
      const futureTime = Math.floor(Date.now() / 1000) + 3600
      const token = createTestToken(futureTime)
      setAuthToken(token)

      // Mock fetch to return 401
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'Token has expired' }),
      })

      // Verify token exists before request
      expect(getAuthToken()).toBe(token)

      // Make request that will fail with 401
      await expect(apiClient('/auth/me')).rejects.toThrow(ApiException)

      // Verify token was cleared after 401 response
      expect(getAuthToken()).toBeNull()
    })

    it('does not clear token on other error status codes', async () => {
      const futureTime = Math.floor(Date.now() / 1000) + 3600
      const token = createTestToken(futureTime)
      setAuthToken(token)

      // Mock fetch to return 500 Internal Server Error
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'Server error' }),
      })

      // Verify token exists before request
      expect(getAuthToken()).toBe(token)

      // Make request that will fail with 500
      await expect(apiClient('/auth/me')).rejects.toThrow(ApiException)

      // Verify token was NOT cleared after non-401 error
      expect(getAuthToken()).toBe(token)
    })

    it('throws ApiException with 401 status for expired token', async () => {
      const futureTime = Math.floor(Date.now() / 1000) + 3600
      const token = createTestToken(futureTime)
      setAuthToken(token)

      // Mock fetch to return 401 with token expired message
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: 'Not authenticated' }),
      })

      try {
        await apiClient('/auth/me')
        expect.fail('Should have thrown ApiException')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiException)
        expect((error as ApiException).status).toBe(401)
        expect((error as ApiException).message).toBe('Not authenticated')
      }
    })

    it('includes error detail in ApiException', async () => {
      const futureTime = Math.floor(Date.now() / 1000) + 3600
      const token = createTestToken(futureTime)
      setAuthToken(token)

      const errorDetail = 'Token signature verification failed'
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: 'Unauthorized',
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ detail: errorDetail }),
      })

      try {
        await apiClient('/auth/me')
        expect.fail('Should have thrown ApiException')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiException)
        expect((error as ApiException).detail).toBe(errorDetail)
      }
    })
  })

  describe('authentication requirements', () => {
    it('throws error when no token exists for authenticated endpoint', async () => {
      // No token set
      expect(getAuthToken()).toBeNull()

      try {
        await apiClient('/auth/me')
        expect.fail('Should have thrown ApiException')
      } catch (error) {
        expect(error).toBeInstanceOf(ApiException)
        expect((error as ApiException).status).toBe(401)
        expect((error as ApiException).message).toBe('Authentication required')
      }
    })

    it('allows requests without token when requiresAuth is false', async () => {
      // No token set
      expect(getAuthToken()).toBeNull()

      // Mock successful response
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ message: 'success' }),
      })

      const result = await apiClient('/public/endpoint', { requiresAuth: false })
      expect(result).toEqual({ message: 'success' })
    })

    it('includes Authorization header for authenticated requests', async () => {
      const futureTime = Math.floor(Date.now() / 1000) + 3600
      const token = createTestToken(futureTime)
      setAuthToken(token)

      // Mock successful response
      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => ({ data: 'protected' }),
      })
      global.fetch = mockFetch

      await apiClient('/auth/me')

      // Verify fetch was called with Authorization header
      expect(mockFetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${token}`,
          }),
        })
      )
    })
  })
})
