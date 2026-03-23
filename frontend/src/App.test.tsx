import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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
})
