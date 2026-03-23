import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import ProtectedRoute from './ProtectedRoute'
import { AuthProvider } from '../../contexts/AuthContext'

// Mock the auth hooks
const mockUseCurrentUser = vi.fn()
const mockUseLogin = vi.fn(() => ({ mutateAsync: vi.fn() }))
const mockUseLogout = vi.fn(() => ({ mutateAsync: vi.fn() }))
const mockUseSwitchUser = vi.fn(() => ({ mutateAsync: vi.fn() }))

vi.mock('../../api/hooks/useAuth', () => ({
  useCurrentUser: () => mockUseCurrentUser(),
  useLogin: () => mockUseLogin(),
  useLogout: () => mockUseLogout(),
  useSwitchUser: () => mockUseSwitchUser(),
}))

// Mock the auth check function
const mockIsAuthenticated = vi.fn()
vi.mock('../../api/client', () => ({
  isAuthenticated: () => mockIsAuthenticated(),
  ApiException: class ApiException extends Error {},
}))

// Helper component to wrap ProtectedRoute with routing context
const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

describe('ProtectedRoute', () => {
  describe('authenticated user', () => {
    it('renders children when user is authenticated', () => {
      mockIsAuthenticated.mockReturnValue(true)
      mockUseCurrentUser.mockReturnValue({
        data: { id: 'user-1', email: 'test@example.com', name: 'Test User' },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      })

      render(<TestWrapper />)

      expect(screen.getByText('Protected Content')).toBeInTheDocument()
      expect(screen.queryByText('Login Page')).not.toBeInTheDocument()
    })

    it('renders children when user data is loaded', () => {
      mockIsAuthenticated.mockReturnValue(true)
      mockUseCurrentUser.mockReturnValue({
        data: {
          id: 'user-123',
          email: 'authenticated@example.com',
          name: 'Authenticated User',
        },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      })

      render(<TestWrapper />)

      expect(screen.getByText('Protected Content')).toBeInTheDocument()
    })
  })

  describe('unauthenticated user', () => {
    it('redirects to /login when user is not authenticated', () => {
      mockIsAuthenticated.mockReturnValue(false)
      mockUseCurrentUser.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      })

      render(<TestWrapper />)

      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
      expect(screen.getByText('Login Page')).toBeInTheDocument()
    })

    it('redirects when token is invalid (no current user)', () => {
      mockIsAuthenticated.mockReturnValue(true)
      mockUseCurrentUser.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      })

      render(<TestWrapper />)

      // Should redirect because isAuthenticated requires BOTH token AND user data
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
      expect(screen.getByText('Login Page')).toBeInTheDocument()
    })
  })

  describe('loading state', () => {
    it('shows loading spinner when checking authentication', () => {
      mockIsAuthenticated.mockReturnValue(true)
      mockUseCurrentUser.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        refetch: vi.fn(),
      })

      render(<TestWrapper />)

      expect(screen.getByText('Loading...')).toBeInTheDocument()
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
      expect(screen.queryByText('Login Page')).not.toBeInTheDocument()
    })

    it('shows loading state with cream background', () => {
      mockIsAuthenticated.mockReturnValue(true)
      mockUseCurrentUser.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        refetch: vi.fn(),
      })

      const { container } = render(<TestWrapper />)

      const loadingContainer = container.querySelector('.bg-cream')
      expect(loadingContainer).toBeInTheDocument()
    })

    it('shows spinner with olive color', () => {
      mockIsAuthenticated.mockReturnValue(true)
      mockUseCurrentUser.mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        refetch: vi.fn(),
      })

      const { container } = render(<TestWrapper />)

      const spinner = container.querySelector('.border-olive')
      expect(spinner).toBeInTheDocument()
    })

    it('stops showing loading when auth check completes with error', () => {
      mockIsAuthenticated.mockReturnValue(false)
      mockUseCurrentUser.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        refetch: vi.fn(),
      })

      render(<TestWrapper />)

      // Should redirect to login instead of showing loading
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
      expect(screen.getByText('Login Page')).toBeInTheDocument()
    })
  })

  describe('error handling', () => {
    it('redirects to login when user data fails to load', () => {
      mockIsAuthenticated.mockReturnValue(true)
      mockUseCurrentUser.mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        refetch: vi.fn(),
      })

      render(<TestWrapper />)

      // Failed to load user data means not authenticated
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
      expect(screen.getByText('Login Page')).toBeInTheDocument()
    })
  })

  describe('rendering children', () => {
    it('renders multiple child elements', () => {
      mockIsAuthenticated.mockReturnValue(true)
      mockUseCurrentUser.mockReturnValue({
        data: { id: 'user-1', email: 'test@example.com', name: 'Test User' },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      })

      render(
        <BrowserRouter>
          <AuthProvider>
            <ProtectedRoute>
              <div>First Child</div>
              <div>Second Child</div>
            </ProtectedRoute>
          </AuthProvider>
        </BrowserRouter>
      )

      expect(screen.getByText('First Child')).toBeInTheDocument()
      expect(screen.getByText('Second Child')).toBeInTheDocument()
    })

    it('renders complex nested components', () => {
      mockIsAuthenticated.mockReturnValue(true)
      mockUseCurrentUser.mockReturnValue({
        data: { id: 'user-1', email: 'test@example.com', name: 'Test User' },
        isLoading: false,
        isError: false,
        refetch: vi.fn(),
      })

      const ComplexComponent = () => (
        <div>
          <header>Header</header>
          <main>Main Content</main>
          <footer>Footer</footer>
        </div>
      )

      render(
        <BrowserRouter>
          <AuthProvider>
            <ProtectedRoute>
              <ComplexComponent />
            </ProtectedRoute>
          </AuthProvider>
        </BrowserRouter>
      )

      expect(screen.getByText('Header')).toBeInTheDocument()
      expect(screen.getByText('Main Content')).toBeInTheDocument()
      expect(screen.getByText('Footer')).toBeInTheDocument()
    })
  })
})
