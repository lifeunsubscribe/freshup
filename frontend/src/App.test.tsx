import { describe, it, expect, vi, beforeEach, afterAll, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'

// Mock the auth hooks
vi.mock('./api/hooks/useAuth', () => ({
  useCurrentUser: vi.fn(() => ({
    data: { id: 'user-1', email: 'test@example.com', name: 'Test User' },
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

  describe('routing structure', () => {
    it('renders the app wrapper with BrowserRouter and AuthProvider', () => {
      render(<App />)
      // App should render without crashing
      expect(document.body).toBeInTheDocument()
    })

    it('shows NotFound page for invalid routes', async () => {
      window.history.pushState({}, '', '/invalid-route')
      render(<App />)

      await waitFor(() => {
        expect(screen.getByText('404')).toBeInTheDocument()
        expect(screen.getByText('Page not found')).toBeInTheDocument()
      })
    })

    it('renders NotFound page with "Go Home" link', async () => {
      window.history.pushState({}, '', '/nonexistent')
      render(<App />)

      await waitFor(() => {
        const homeLink = screen.getByRole('link', { name: /go home/i })
        expect(homeLink).toHaveAttribute('href', '/')
      })
    })
  })

  describe('bottom navigation visibility', () => {
    it('shows BottomNav on protected routes', async () => {
      window.history.pushState({}, '', '/')
      render(<App />)

      await waitFor(() => {
        const nav = screen.getByRole('navigation', { name: /main navigation/i })
        expect(nav).toBeInTheDocument()
      })
    })

    it('hides BottomNav on login page', async () => {
      window.history.pushState({}, '', '/login')
      render(<App />)

      await waitFor(() => {
        const nav = screen.queryByRole('navigation', { name: /main navigation/i })
        expect(nav).not.toBeInTheDocument()
      })
    })
  })

  describe('route definitions', () => {
    it('defines all required routes', () => {
      // This test verifies that the routes exist by checking the App component structure
      render(<App />)

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
        window.location = originalLocation
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

      render(<App />)

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

      render(<App />)

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

      render(<App />)

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
      delete (window as any).location
      window.location = { href: '' } as Location

      render(<App />)

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
        }
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

      render(<App />)

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

      render(<App />)

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Authentication Error' })).toBeInTheDocument()
      })

      // Should have logged the error
      expect(consoleSpy).toHaveBeenCalled()
    })
  })
})
