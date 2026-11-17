import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router-dom'
import { renderWithProviders } from '../test/renderWithProviders'
import Welcome from './Welcome'
import { useAuth } from '../contexts/AuthContext'
import type { UserResponse } from '../api/types'

vi.mock('../contexts/AuthContext')
vi.mock('../api/hooks/useAuth', () => ({
  useUpdateProfile: vi.fn(),
}))
vi.mock('../api/hooks/useThemes', () => ({
  useThemes: vi.fn(),
}))
vi.mock('../components/layout/PageContainer', () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

import { useUpdateProfile } from '../api/hooks/useAuth'
import { useThemes } from '../api/hooks/useThemes'

const MOCK_THEMES = [
  {
    key: 'cuisine',
    label: 'Cuisine',
    values: [
      { value: 'italian', label: 'Italian', library_count: 5, library_tag: null, library_source_type: null, match_tags: [], match_source_types: [], collections: [] },
      { value: 'mexican', label: 'Mexican', library_count: 3, library_tag: null, library_source_type: null, match_tags: [], match_source_types: [], collections: [] },
    ],
  },
  {
    key: 'ingredient',
    label: 'Ingredient',
    values: [
      { value: 'chicken', label: 'Chicken', library_count: 10, library_tag: null, library_source_type: null, match_tags: [], match_source_types: [], collections: [] },
      { value: 'beef', label: 'Beef', library_count: 7, library_tag: null, library_source_type: null, match_tags: [], match_source_types: [], collections: [] },
    ],
  },
]

const BASE_USER: UserResponse = {
  id: 'u1',
  name: 'Test User',
  email: 'test@example.com',
  role: 'member',
  dietary_profile: [],
  allergies: [],
  disliked_ingredients: [],
  favorite_ingredients: [],
  taste_preferences: {},
  onboarded_at: null,
  failed_login_attempts: 0,
  lockout_until: null,
  lockout_count: 0,
}

describe('Welcome page', () => {
  let mockMutateAsync: ReturnType<typeof vi.fn>

  beforeEach(() => {
    mockMutateAsync = vi.fn().mockResolvedValue({ ...BASE_USER, onboarded_at: '2024-01-01' })

    vi.mocked(useAuth).mockReturnValue({
      currentUser: BASE_USER,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    vi.mocked(useUpdateProfile).mockReturnValue({
      mutateAsync: mockMutateAsync,
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      isSuccess: false,
      error: null,
      reset: vi.fn(),
      status: 'idle',
      variables: undefined,
      context: undefined,
      data: undefined,
      failureCount: 0,
      failureReason: null,
      isIdle: true,
      isPaused: false,
      submittedAt: 0,
    } as any) // eslint-disable-line @typescript-eslint/no-explicit-any

    vi.mocked(useThemes).mockReturnValue({
      data: MOCK_THEMES,
      isLoading: false,
      isError: false,
      error: null,
    } as any) // eslint-disable-line @typescript-eslint/no-explicit-any
  })

  it('renders step 1 (allergies) on initial load', () => {
    renderWithProviders(<Welcome />)
    expect(screen.getByTestId('welcome-step-1')).toBeInTheDocument()
    expect(screen.getByText('Step 1 of 4')).toBeInTheDocument()
  })

  it('Skip for now sends only { onboarded: true }', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Welcome />)

    await user.click(screen.getByRole('button', { name: /skip for now/i }))

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({ onboarded: true })
      expect(mockMutateAsync).toHaveBeenCalledTimes(1)
    })
  })

  it('Skip for now on a later step still sends only { onboarded: true }', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Welcome />)

    // Go to step 2
    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByTestId('welcome-step-2')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /skip for now/i }))

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({ onboarded: true })
    })
  })

  it('completing all four steps sends one update with collected data and onboarded: true', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Welcome />)

    // Step 1: add an allergy
    const allergyInput = screen.getByPlaceholderText(/type an allergy/i)
    await user.type(allergyInput, 'peanuts')
    await user.keyboard('{Enter}')
    await user.click(screen.getByRole('button', { name: /next/i }))

    // Step 2: select a diet
    expect(screen.getByTestId('welcome-step-2')).toBeInTheDocument()
    await user.click(screen.getByLabelText('Vegan'))
    await user.click(screen.getByRole('button', { name: /next/i }))

    // Step 3: tap a cuisine (Italian → love)
    expect(screen.getByTestId('welcome-step-3')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Italian' }))
    await user.click(screen.getByRole('button', { name: /next/i }))

    // Step 4: tap an ingredient (Chicken → love) and finish
    expect(screen.getByTestId('welcome-step-4')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Chicken' }))
    await user.click(screen.getByRole('button', { name: /finish/i }))

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith({
        allergies: ['peanuts'],
        dietary_profile: ['vegan'],
        taste_preferences: { italian: 'love', chicken: 'love' },
        onboarded: true,
      })
      expect(mockMutateAsync).toHaveBeenCalledTimes(1)
    })
  })

  it('cuisine tap cycles: tap twice reaches never, tap thrice clears', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Welcome />)

    // Go to step 3
    await user.click(screen.getByRole('button', { name: /next/i })) // step 2
    await user.click(screen.getByRole('button', { name: /next/i })) // step 3
    expect(screen.getByTestId('welcome-step-3')).toBeInTheDocument()

    const italianBtn = screen.getByRole('button', { name: 'Italian' })
    await user.click(italianBtn) // → love
    expect(screen.getByRole('button', { name: /♥ Italian/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /♥ Italian/i })) // → never
    expect(screen.getByRole('button', { name: /✕ Italian/i })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /✕ Italian/i })) // → clear
    expect(screen.getByRole('button', { name: 'Italian' })).toBeInTheDocument()
  })

  it('Back button returns to the previous step', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Welcome />)

    await user.click(screen.getByRole('button', { name: /next/i }))
    expect(screen.getByTestId('welcome-step-2')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /back/i }))
    expect(screen.getByTestId('welcome-step-1')).toBeInTheDocument()
  })

  it('redirects to / when user is already onboarded', async () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: { ...BASE_USER, onboarded_at: '2024-01-01T00:00:00Z' },
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    function LocationDisplay() {
      const { pathname } = useLocation()
      return <span data-testid="location-display">{pathname}</span>
    }

    renderWithProviders(
      <>
        <Welcome />
        <LocationDisplay />
      </>,
      { route: '/welcome' }
    )

    await waitFor(() => {
      // Exact match: /^\/$/ ensures we landed on '/', not still on '/welcome' (which contains '/')
      expect(screen.getByTestId('location-display')).toHaveTextContent(/^\/$/)
    })
  })
})
