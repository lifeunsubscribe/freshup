import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/renderWithProviders'
import TastePreferencesSection from './TastePreferencesSection'

vi.mock('../../api/hooks/useAuth', () => ({
  useUpdateProfile: vi.fn(),
}))
vi.mock('../../api/hooks/useThemes', () => ({
  useThemes: vi.fn(),
}))

import { useUpdateProfile } from '../../api/hooks/useAuth'
import { useThemes } from '../../api/hooks/useThemes'

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

describe('TastePreferencesSection', () => {
  let mockMutate: ReturnType<typeof vi.fn>

  beforeEach(() => {
    mockMutate = vi.fn()
    vi.mocked(useUpdateProfile).mockReturnValue({
      mutate: mockMutate,
      mutateAsync: vi.fn(),
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

  it('renders existing preferences grouped under Cuisines and Ingredients', () => {
    renderWithProviders(
      <TastePreferencesSection
        currentTastePreferences={{ italian: 'love', chicken: 'like' }}
      />
    )

    expect(screen.getByText('Cuisines')).toBeInTheDocument()
    expect(screen.getByText('Ingredients')).toBeInTheDocument()
    expect(screen.getByText('Italian')).toBeInTheDocument()
    expect(screen.getByText('Chicken')).toBeInTheDocument()
  })

  it('shows the active taste level as pressed', () => {
    renderWithProviders(
      <TastePreferencesSection
        currentTastePreferences={{ italian: 'love', chicken: 'like' }}
      />
    )

    // Find the pressed button in the Italian row by aria-pressed
    const pressedButtons = screen.getAllByRole('button').filter(
      btn => btn.getAttribute('aria-pressed') === 'true'
    )
    // Should have 2 pressed buttons (Love for Italian, Like for Chicken)
    expect(pressedButtons).toHaveLength(2)
    expect(pressedButtons[0]).toHaveTextContent('Love')
    expect(pressedButtons[1]).toHaveTextContent('Like')
  })

  it('changing a level calls useUpdateProfile with the whole updated map', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <TastePreferencesSection
        currentTastePreferences={{ italian: 'love', chicken: 'like' }}
      />
    )

    // Click the "Like" button on the Italian row (the first "Like" button)
    const likeButtons = screen.getAllByRole('button', { name: 'Like' })
    await user.click(likeButtons[0])

    expect(mockMutate).toHaveBeenCalledWith({
      taste_preferences: { italian: 'like', chicken: 'like' },
    })
  })

  it('removing a row calls useUpdateProfile with the entry removed from the map', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <TastePreferencesSection
        currentTastePreferences={{ italian: 'love', chicken: 'like' }}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Remove Italian' }))

    expect(mockMutate).toHaveBeenCalledWith({
      taste_preferences: { chicken: 'like' },
    })
  })

  it('adding a value from the picker adds it at like', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <TastePreferencesSection
        currentTastePreferences={{ italian: 'love' }}
      />
    )

    // Open the picker by clicking the input
    const pickerInput = screen.getByPlaceholderText('Add cuisine or ingredient…')
    await user.click(pickerInput)

    // The picker should show available values (Mexican, Chicken, Beef — not Italian)
    const mexicanBtn = await screen.findByRole('button', { name: /mexican/i })
    await user.click(mexicanBtn)

    expect(mockMutate).toHaveBeenCalledWith({
      taste_preferences: { italian: 'love', mexican: 'like' },
    })
  })

  it('filtering the picker by query narrows results', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <TastePreferencesSection currentTastePreferences={{}} />
    )

    const pickerInput = screen.getByPlaceholderText('Add cuisine or ingredient…')
    await user.type(pickerInput, 'chick')

    expect(screen.getByRole('button', { name: /chicken/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /italian/i })).not.toBeInTheDocument()
  })

  it('shows empty state when no preferences are set', () => {
    renderWithProviders(<TastePreferencesSection currentTastePreferences={{}} />)
    expect(
      screen.getByText('No taste preferences set. Use the picker below to add items.')
    ).toBeInTheDocument()
  })

  it('shows error message when update fails', () => {
    vi.mocked(useUpdateProfile).mockReturnValue({
      mutate: mockMutate,
      mutateAsync: vi.fn(),
      isPending: false,
      isError: true,
      isSuccess: false,
      error: new Error('Network error'),
      reset: vi.fn(),
      status: 'error',
      variables: undefined,
      context: undefined,
      data: undefined,
      failureCount: 1,
      failureReason: null,
      isIdle: false,
      isPaused: false,
      submittedAt: 0,
    } as any) // eslint-disable-line @typescript-eslint/no-explicit-any

    renderWithProviders(
      <TastePreferencesSection currentTastePreferences={{ italian: 'love' }} />
    )

    expect(screen.getByText('Network error')).toBeInTheDocument()
  })

  it('syncs preferences when prop changes', () => {
    const { rerender } = renderWithProviders(
      <TastePreferencesSection currentTastePreferences={{ italian: 'love' }} />
    )

    expect(screen.getByText('Italian')).toBeInTheDocument()

    rerender(
      <TastePreferencesSection currentTastePreferences={{ chicken: 'like' }} />
    )

    // Italian should no longer appear as a preference row (it goes back to available in picker)
    // Chicken should appear
    expect(screen.queryByRole('button', { name: 'Remove Italian' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove Chicken' })).toBeInTheDocument()
  })
})
