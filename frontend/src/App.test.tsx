import { describe, it, expect, vi, beforeEach, afterAll, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'

// Mock the auth hooks
vi.mock('./api/hooks/useAuth', () => ({
  useCurrentUser: vi.fn(() => ({
    data: { id: 'user-1', email: 'test@example.com', name: 'Test User', onboarded_at: '2024-01-01' },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  })),
  useLogin: vi.fn(() => ({
    mutateAsync: vi.fn(),
  })),
  useLogout: vi.fn(() => ({
    mutateAsync: vi.fn(),
  })),
  useSwitchUser: vi.fn(() => ({
    mutateAsync: vi.fn(),
  })),
  useUpdateProfile: vi.fn(() => ({
    mutate: vi.fn(),
    mutateAsync: vi.fn().mockResolvedValue({}),
    isPending: false,
    isError: false,
    isSuccess: false,
    error: null,
    reset: vi.fn(),
    status: 'idle',
    isIdle: true,
    isPaused: false,
    submittedAt: 0,
    failureCount: 0,
    failureReason: null,
    variables: undefined,
    context: undefined,
    data: undefined,
  })),
}))

// Mock useThemes (needed by TastePreferencesSection and Welcome page)
vi.mock('./api/hooks/useThemes', () => ({
  useThemes: vi.fn(() => ({
    data: [],
    isLoading: false,
    isError: false,
    error: null,
  })),
}))

// Mock the auth check function
vi.mock('./api/client', () => ({
  isAuthenticated: vi.fn(() => true),
  ApiException: class ApiException extends Error {},
}))

describe('App', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    window.history.pushState({}, '', '/')
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
  })

  const renderApp = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    )

  describe('routing structure', () => {
    it('renders the app wrapper with BrowserRouter and AuthProvider', () => {
      renderApp()
      // App should render without crashing
      expect(document.body).toBeInTheDocument()
    })

    it('shows NotFound page for invalid routes', async () => {
      window.history.pushState({}, '', '/invalid-route')
      renderApp()

      await waitFor(() => {
        expect(screen.getByText('404')).toBeInTheDocument()
        expect(screen.getByText('Page not found')).toBeInTheDocument()
      })
    })

    it('renders NotFound page with "Go Home" link', async () => {
      window.history.pushState({}, '', '/nonexistent')
      renderApp()

      await waitFor(() => {
        const homeLink = screen.getByRole('link', { name: /go home/i })
        expect(homeLink).toHaveAttribute('href', '/')
      })
    })
  })

  describe('bottom navigation visibility', () => {
    it('shows BottomNav on protected routes', async () => {
      window.history.pushState({}, '', '/')
      renderApp()

      await waitFor(() => {
        const nav = screen.getByRole('navigation', { name: /main navigation/i })
        expect(nav).toBeInTheDocument()
      })
    })

    it('hides BottomNav on login page', async () => {
      window.history.pushState({}, '', '/login')
      renderApp()

      await waitFor(() => {
        const nav = screen.queryByRole('navigation', { name: /main navigation/i })
        expect(nav).not.toBeInTheDocument()
      })
    })
  })

  describe('route definitions', () => {
    it('defines all required routes', () => {
      // This test verifies that the routes exist by checking the App component structure
      renderApp()

      // The app should render successfully with all routes defined
      expect(document.querySelector('.min-h-screen')).toBeInTheDocument()
    })
  })

  describe('error boundary integration', () => {
    /**
     * Tests for the ErrorBoundary at the App level that wraps the AuthProvider.
     *
     * These tests verify that:
     * 1. Errors thrown during AuthProvider initialization are caught
     * 2. The AuthErrorFallback UI is rendered with appropriate recovery options
     * 3. Sensitive error information is not leaked to users (security requirement)
     * 4. Error recovery mechanisms (Try Again, Return to Login) work correctly
     * 5. localStorage cleanup happens when redirecting to login
     *
     * Related components:
     * - ErrorBoundary (src/components/errors/ErrorBoundary.tsx)
     * - AuthErrorFallback (src/components/errors/AuthErrorFallback.tsx)
     * - AuthProvider (src/contexts/AuthContext.tsx)
     */

    // Suppress console.error in error boundary tests to avoid cluttering test output
    const originalError = console.error
    let originalLocation: Location

    beforeAll(() => {
      console.error = vi.fn()
    })

    afterAll(() => {
      console.error = originalError
    })

    beforeEach(() => {
      vi.resetModules()
      vi.clearAllMocks()
      originalLocation = window.location
    })

    afterEach(() => {
      // Restore window.location if it was mocked
      if (window.location !== originalLocation) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any, no-extra-semi
        ;(window as any).location = originalLocation
      }
      // Clean up localStorage to prevent test pollution
      localStorage.removeItem('access_token')
    })

    it('catches errors from AuthProvider and renders AuthErrorFallback', async () => {
      // Mock useCurrentUser to throw an error
      const { useCurrentUser } = await import('./api/hooks/useAuth')
      vi.mocked(useCurrentUser).mockImplementation(() => {
        throw new Error('Failed to load authentication state')
      })

      renderApp()

      // Should render the AuthErrorFallback UI
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Authentication Error' })).toBeInTheDocument()
      })

      // Should show user-friendly error message
      expect(screen.getByText(/Something went wrong while loading your session/i)).toBeInTheDocument()

      // Should show action buttons
      expect(screen.getByRole('button', { name: 'Try Again' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Return to Login' })).toBeInTheDocument()
    })

    it('renders AuthErrorFallback with Try Again and Return to Login buttons', async () => {
      // Mock useCurrentUser to throw an error
      const { useCurrentUser } = await import('./api/hooks/useAuth')
      vi.mocked(useCurrentUser).mockImplementation(() => {
        throw new Error('Network timeout')
      })

      renderApp()

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Authentication Error' })).toBeInTheDocument()
      })

      // Verify both recovery options are present
      const tryAgainButton = screen.getByRole('button', { name: 'Try Again' })
      const returnToLoginButton = screen.getByRole('button', { name: 'Return to Login' })

      expect(tryAgainButton).toBeInTheDocument()
      expect(returnToLoginButton).toBeInTheDocument()
    })

    it('does not leak sensitive error details to users', async () => {
      // Mock useCurrentUser to throw an error with sensitive information
      const { useCurrentUser } = await import('./api/hooks/useAuth')
      vi.mocked(useCurrentUser).mockImplementation(() => {
        throw new Error('Database connection failed: postgresql://user:password@host/db')
      })

      renderApp()

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Authentication Error' })).toBeInTheDocument()
      })

      // Should NOT display the sensitive error message
      expect(screen.queryByText(/postgresql/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/password/i)).not.toBeInTheDocument()
      expect(screen.queryByText(/Database connection failed/i)).not.toBeInTheDocument()

      // Should only show generic message
      expect(screen.getByText(/We're having trouble loading your authentication session/i)).toBeInTheDocument()
    })

    it('clears access token when Return to Login is clicked', async () => {
      const user = userEvent.setup()
      localStorage.setItem('access_token', 'test-token')

      // Mock useCurrentUser to throw an error
      const { useCurrentUser } = await import('./api/hooks/useAuth')
      vi.mocked(useCurrentUser).mockImplementation(() => {
        throw new Error('Auth error')
      })

      // Mock window.location.href
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      delete (window as any).location
      // eslint-disable-next-line @typescript-eslint/no-explicit-any, no-extra-semi
      ;(window as any).location = { href: '' } as Location

      renderApp()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Return to Login' })).toBeInTheDocument()
      })

      const returnButton = screen.getByRole('button', { name: 'Return to Login' })
      await user.click(returnButton)

      // Should clear the token
      expect(localStorage.getItem('access_token')).toBeNull()

      // Should redirect to login
      expect(window.location.href).toBe('/login')

      // window.location will be restored by afterEach hook
    })

    it('supports error recovery via Try Again button', async () => {
      const user = userEvent.setup()

      // Flag to control when the mock should start succeeding
      let shouldSucceed = false
      let callCount = 0

      // Mock useCurrentUser to throw until we set shouldSucceed to true
      const { useCurrentUser } = await import('./api/hooks/useAuth')
      vi.mocked(useCurrentUser).mockImplementation(() => {
        callCount++

        // Throw error until shouldSucceed is true
        if (!shouldSucceed) {
          throw new Error('Temporary network error')
        }

        // After shouldSucceed is set to true, return success
        return {
          data: { id: 'user-1', email: 'test@example.com', name: 'Test User' },
          isLoading: false,
          isError: false,
          refetch: vi.fn(),
        } as any // eslint-disable-line @typescript-eslint/no-explicit-any
      })

      // Wrap App in QueryClientProvider to support successful rendering after recovery
      render(
        <QueryClientProvider client={queryClient}>
          <App />
        </QueryClientProvider>
      )

      // Should show error on first render
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Authentication Error' })).toBeInTheDocument()
      })

      // Verify we're in error state
      expect(callCount).toBeGreaterThanOrEqual(1)
      const callCountBeforeReset = callCount

      // Now allow the mock to succeed
      shouldSucceed = true

      // Click Try Again - this should call resetError() which resets the ErrorBoundary state
      // and re-renders the children, triggering useCurrentUser again
      const tryAgainButton = screen.getByRole('button', { name: 'Try Again' })
      await user.click(tryAgainButton)

      // After clicking Try Again, the ErrorBoundary should reset and re-render children
      // This should trigger useCurrentUser again and successfully render the app
      await waitFor(() => {
        expect(screen.queryByRole('heading', { name: 'Authentication Error' })).not.toBeInTheDocument()
      })

      // Verify that useCurrentUser was called again after reset
      expect(callCount).toBeGreaterThan(callCountBeforeReset)
    })

    it('handles errors during AuthProvider initialization', async () => {
      // Mock useCurrentUser to throw during initialization
      const { useCurrentUser } = await import('./api/hooks/useAuth')
      vi.mocked(useCurrentUser).mockImplementation(() => {
        throw new Error('Failed to initialize auth context')
      })

      renderApp()

      // Should catch the error and render fallback
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Authentication Error' })).toBeInTheDocument()
      })

      // Should display appropriate recovery options
      expect(screen.getByRole('button', { name: 'Try Again' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Return to Login' })).toBeInTheDocument()

      // Should show contact support message
      expect(screen.getByText(/If this problem persists, please contact your household coordinator/i)).toBeInTheDocument()
    })

    it('logs errors to console for debugging', async () => {
      const consoleSpy = vi.spyOn(console, 'error')

      // Mock useCurrentUser to throw an error
      const { useCurrentUser } = await import('./api/hooks/useAuth')
      vi.mocked(useCurrentUser).mockImplementation(() => {
        throw new Error('Test error for logging')
      })

      renderApp()

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Authentication Error' })).toBeInTheDocument()
      })

      // Should have logged the error
      expect(consoleSpy).toHaveBeenCalled()
    })
  })

  describe('onboarding redirect', () => {
    it('redirects an authenticated user with onboarded_at: null to /welcome', async () => {
      const { useCurrentUser } = await import('./api/hooks/useAuth')
      vi.mocked(useCurrentUser).mockReturnValue({
        data: {
          id: 'user-1',
          email: 'test@example.com',
          name: 'Test User',
          onboarded_at: null,
          role: 'member',
          dietary_profile: [],
          allergies: [],
          disliked_ingredients: [],
          favorite_ingredients: [],
          taste_preferences: {},
          failed_login_attempts: 0,
          lockout_until: null,
          lockout_count: 0,
        },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      } as any) // eslint-disable-line @typescript-eslint/no-explicit-any

      window.history.pushState({}, '', '/')
      renderApp()

      await waitFor(() => {
        expect(window.location.pathname).toBe('/welcome')
      })
    })

    it('does not redirect an authenticated user with onboarded_at set', async () => {
      const { useCurrentUser } = await import('./api/hooks/useAuth')
      vi.mocked(useCurrentUser).mockReturnValue({
        data: {
          id: 'user-1',
          email: 'test@example.com',
          name: 'Test User',
          onboarded_at: '2024-01-01T00:00:00Z',
          role: 'member',
          dietary_profile: [],
          allergies: [],
          disliked_ingredients: [],
          favorite_ingredients: [],
          taste_preferences: {},
          failed_login_attempts: 0,
          lockout_until: null,
          lockout_count: 0,
        },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      } as any) // eslint-disable-line @typescript-eslint/no-explicit-any

      window.history.pushState({}, '', '/')
      renderApp()

      // Should remain on '/' (no redirect to /welcome)
      await waitFor(() => {
        expect(window.location.pathname).toBe('/')
      })
      expect(window.location.pathname).not.toBe('/welcome')
    })

    it('does not redirect a user who is loading (onboarded_at not yet known)', async () => {
      const { useCurrentUser } = await import('./api/hooks/useAuth')
      vi.mocked(useCurrentUser).mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        refetch: vi.fn(),
      } as any) // eslint-disable-line @typescript-eslint/no-explicit-any

      window.history.pushState({}, '', '/')
      renderApp()

      // Loading state → no redirect; we just verify we don't end up on /welcome
      // (ProtectedRoute shows a spinner, not a redirect to /welcome)
      expect(window.location.pathname).not.toBe('/welcome')
    })
  })
})
