import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Profile from './Profile'
import { useAuth } from '../contexts/AuthContext'
import type { UserResponse } from '../api/types'

// Mock all the child components
vi.mock('../components/layout/PageContainer', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))
vi.mock('../components/auth/UserSwitcher', () => ({
  default: () => <div data-testid="user-switcher">UserSwitcher</div>,
}))
vi.mock('../components/profile/ProfileHeader', () => ({
  default: () => <div data-testid="profile-header">ProfileHeader</div>,
}))
vi.mock('../components/profile/DietarySection', () => ({
  default: () => <div data-testid="dietary-section">DietarySection</div>,
}))
vi.mock('../components/profile/AllergiesSection', () => ({
  default: () => <div data-testid="allergies-section">AllergiesSection</div>,
}))
vi.mock('../components/profile/DislikedIngredientsSection', () => ({
  default: () => <div data-testid="disliked-section">DislikedIngredientsSection</div>,
}))
vi.mock('../components/profile/SubstitutionsSection', () => ({
  default: () => <div data-testid="substitutions-section">SubstitutionsSection</div>,
}))

// Mock the auth context
vi.mock('../contexts/AuthContext')

describe('Profile Page', () => {
  let queryClient: QueryClient

  const mockUser: UserResponse = {
    id: '1',
    name: 'Test User',
    email: 'test@example.com',
    role: 'coordinator',
    dietary_profile: ['vegetarian', 'vegan'],
    allergies: ['peanuts', 'shellfish'],
    disliked_ingredients: ['cilantro'],
    favorite_ingredients: [],
    failed_login_attempts: 0,
    lockout_until: null,
    lockout_count: 0,
  }

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
  })

  const renderWithProviders = (component: React.ReactElement) => {
    return render(<QueryClientProvider client={queryClient}>{component}</QueryClientProvider>)
  }

  it('renders page title and description', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockUser,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    renderWithProviders(<Profile />)
    expect(screen.getByText('Profile')).toBeInTheDocument()
    expect(screen.getByText('Manage your preferences and settings')).toBeInTheDocument()
  })

  it('renders all profile sections when user is loaded', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockUser,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    renderWithProviders(<Profile />)

    expect(screen.getByTestId('profile-header')).toBeInTheDocument()
    expect(screen.getByTestId('dietary-section')).toBeInTheDocument()
    expect(screen.getByTestId('allergies-section')).toBeInTheDocument()
    expect(screen.getByTestId('disliked-section')).toBeInTheDocument()
    expect(screen.getByTestId('substitutions-section')).toBeInTheDocument()
    expect(screen.getByTestId('user-switcher')).toBeInTheDocument()
  })

  it('displays loading state when currentUser is null', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: undefined,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    renderWithProviders(<Profile />)
    expect(screen.getByText('Loading profile...')).toBeInTheDocument()
  })

  it('does not render profile sections when loading', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: undefined,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    renderWithProviders(<Profile />)

    expect(screen.queryByTestId('profile-header')).not.toBeInTheDocument()
    expect(screen.queryByTestId('dietary-section')).not.toBeInTheDocument()
    expect(screen.queryByTestId('allergies-section')).not.toBeInTheDocument()
    expect(screen.queryByTestId('disliked-section')).not.toBeInTheDocument()
    expect(screen.queryByTestId('substitutions-section')).not.toBeInTheDocument()
    expect(screen.queryByTestId('user-switcher')).not.toBeInTheDocument()
  })

  it('renders sections in correct order', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockUser,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    const { container } = renderWithProviders(<Profile />)
    const sections = container.querySelectorAll('[data-testid]')

    expect(sections[0]).toHaveAttribute('data-testid', 'profile-header')
    expect(sections[1]).toHaveAttribute('data-testid', 'dietary-section')
    expect(sections[2]).toHaveAttribute('data-testid', 'allergies-section')
    expect(sections[3]).toHaveAttribute('data-testid', 'disliked-section')
    expect(sections[4]).toHaveAttribute('data-testid', 'substitutions-section')
    expect(sections[5]).toHaveAttribute('data-testid', 'user-switcher')
  })
})
