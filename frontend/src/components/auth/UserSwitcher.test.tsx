import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import UserSwitcher from './UserSwitcher'
import { useAuth } from '../../contexts/AuthContext'
import { useUsers } from '../../api/hooks/useUsers'
import { UserRole } from '../../api/types'
import type { UserResponse, UserListResponse } from '../../api/types'

// Mock the hooks
vi.mock('../../contexts/AuthContext')
vi.mock('../../api/hooks/useUsers')

describe('UserSwitcher', () => {
  let queryClient: QueryClient

  const mockCoordinator: UserResponse = {
    id: '1',
    name: 'Coordinator User',
    email: 'coord@example.com',
    role: UserRole.COORDINATOR,
    dietary_profile: ['vegetarian'],
    allergies: [],
    disliked_ingredients: [],
    favorite_ingredients: [],
    failed_login_attempts: 0,
    lockout_until: null,
    lockout_count: 0,
  }

  const mockMember: UserResponse = {
    id: '2',
    name: 'Member User',
    email: 'member@example.com',
    role: UserRole.MEMBER,
    dietary_profile: [],
    allergies: [],
    disliked_ingredients: [],
    favorite_ingredients: [],
    failed_login_attempts: 0,
    lockout_until: null,
    lockout_count: 0,
  }

  const mockHouseholdMembers: UserListResponse[] = [
    {
      id: '1',
      name: 'Coordinator User',
      role: UserRole.COORDINATOR,
      dietary_profile: ['vegetarian'],
      allergies: [],
      disliked_ingredients: [],
      favorite_ingredients: [],
    },
    {
      id: '2',
      name: 'Member User',
      role: UserRole.MEMBER,
      dietary_profile: ['vegan'],
      allergies: [],
      disliked_ingredients: [],
      favorite_ingredients: [],
    },
    {
      id: '3',
      name: 'Another Member',
      role: UserRole.MEMBER,
      dietary_profile: [],
      allergies: [],
      disliked_ingredients: [],
      favorite_ingredients: [],
    },
  ]

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

  it('does not render for non-coordinator users', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockMember,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    const { container } = renderWithProviders(<UserSwitcher />)
    expect(container.firstChild).toBeNull()
  })

  it('renders for coordinator users', () => {
    const mockSwitchUser = vi.fn()
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockCoordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: mockSwitchUser,
    })

    vi.mocked(useUsers).mockReturnValue({
      data: mockHouseholdMembers,
      isLoading: false,
      error: null,
    } as any)

    renderWithProviders(<UserSwitcher />)
    expect(screen.getByText('Who are you?')).toBeInTheDocument()
  })

  it('displays loading state while fetching users', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockCoordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    vi.mocked(useUsers).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    } as any)

    renderWithProviders(<UserSwitcher />)
    expect(screen.getByText('Loading household members...')).toBeInTheDocument()
  })

  it('renders all household members', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockCoordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    vi.mocked(useUsers).mockReturnValue({
      data: mockHouseholdMembers,
      isLoading: false,
      error: null,
    } as any)

    renderWithProviders(<UserSwitcher />)
    expect(screen.getByText('Coordinator User (current)')).toBeInTheDocument()
    expect(screen.getByText('Member User')).toBeInTheDocument()
    expect(screen.getByText('Another Member')).toBeInTheDocument()
  })

  it('highlights current user', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockCoordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    vi.mocked(useUsers).mockReturnValue({
      data: mockHouseholdMembers,
      isLoading: false,
      error: null,
    } as any)

    renderWithProviders(<UserSwitcher />)
    const currentUserButton = screen.getByText('Coordinator User (current)').closest('button')
    expect(currentUserButton?.className).toContain('bg-olive/20')
    expect(currentUserButton).toBeDisabled()
  })

  it('calls switchUser when clicking another user', async () => {
    const mockSwitchUser = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockCoordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: mockSwitchUser,
    })

    vi.mocked(useUsers).mockReturnValue({
      data: mockHouseholdMembers,
      isLoading: false,
      error: null,
    } as any)

    renderWithProviders(<UserSwitcher />)

    const memberButton = screen.getByText('Member User').closest('button')
    fireEvent.click(memberButton!)

    await waitFor(() => {
      expect(mockSwitchUser).toHaveBeenCalledWith({ user_id: '2' })
    })
  })

  it('does not call switchUser when clicking current user', () => {
    const mockSwitchUser = vi.fn()
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockCoordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: mockSwitchUser,
    })

    vi.mocked(useUsers).mockReturnValue({
      data: mockHouseholdMembers,
      isLoading: false,
      error: null,
    } as any)

    renderWithProviders(<UserSwitcher />)

    const currentUserButton = screen.getByText('Coordinator User (current)').closest('button')
    fireEvent.click(currentUserButton!)

    expect(mockSwitchUser).not.toHaveBeenCalled()
  })

  it('displays dietary profiles for users', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockCoordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    vi.mocked(useUsers).mockReturnValue({
      data: mockHouseholdMembers,
      isLoading: false,
      error: null,
    } as any)

    renderWithProviders(<UserSwitcher />)
    expect(screen.getByText('vegetarian')).toBeInTheDocument()
    expect(screen.getByText('vegan')).toBeInTheDocument()
  })

  it('does not render when no users are available', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: mockCoordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    vi.mocked(useUsers).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    } as any)

    const { container } = renderWithProviders(<UserSwitcher />)
    expect(container.firstChild).toBeNull()
  })

  it('does not render when currentUser is null', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: undefined,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    const { container } = renderWithProviders(<UserSwitcher />)
    expect(container.firstChild).toBeNull()
  })
})
