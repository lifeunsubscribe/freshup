import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, fireEvent, within } from '@testing-library/react'
import Plan from './Plan'
import { renderWithProviders } from '../test/renderWithProviders'
import {
  useWeekPlan,
  useGenerateDraft,
  useConfirmEntry,
  useSwapEntry,
  useOpenCard,
} from '../api'
import type { MealPlanEntryDisplay, WeekViewResponse } from '../api/types'

vi.mock('../api', () => ({
  useWeekPlan: vi.fn(),
  useGenerateDraft: vi.fn(),
  useConfirmEntry: vi.fn(),
  useSwapEntry: vi.fn(),
  useOpenCard: vi.fn(),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

// Wednesday 2026-11-18; its week starts Monday 2026-11-16.
const NOW = new Date('2026-11-18T10:00:00')
const THIS_WEEK = '2026-11-16'

function entry(date: string, overrides: Partial<MealPlanEntryDisplay> = {}): MealPlanEntryDisplay {
  return {
    id: `entry-${date}`,
    date,
    meal_type: 'dinner',
    recipe_id: null,
    catalog_card_id: `card-${date}`,
    prepared_food_id: null,
    planned_servings: 2,
    status: 'draft',
    notes: null,
    display: {
      name: `Dinner ${date}`,
      image_url: `https://img.test/${date}.jpg`,
      prep_time_minutes: 35,
      source_type: 'hellofresh_web',
    },
    ...overrides,
  }
}

const generateMutate = vi.fn()
const generateReset = vi.fn()
const confirmMutate = vi.fn()
const swapMutate = vi.fn()
const openCardMutate = vi.fn()

/** Weeks the mocked GET /plan/week knows about; any other week is empty. */
let weeks: Record<string, Partial<WeekViewResponse>> = {}

function setup({
  generate = {},
  weekQuery = {},
}: {
  generate?: { isPending?: boolean; isError?: boolean }
  weekQuery?: { isLoading?: boolean; isError?: boolean }
} = {}) {
  vi.mocked(useWeekPlan).mockImplementation(((weekStart: string) => ({
    data:
      weekQuery.isLoading || weekQuery.isError
        ? undefined
        : { week_start: weekStart, confirmed_entries: [], draft_entries: [], ...weeks[weekStart] },
    isLoading: weekQuery.isLoading ?? false,
    isError: weekQuery.isError ?? false,
    refetch: vi.fn(),
  })) as unknown as typeof useWeekPlan)

  vi.mocked(useGenerateDraft).mockReturnValue({
    mutate: generateMutate,
    reset: generateReset,
    isPending: generate.isPending ?? false,
    isError: generate.isError ?? false,
  } as unknown as ReturnType<typeof useGenerateDraft>)
  vi.mocked(useConfirmEntry).mockReturnValue({
    mutate: confirmMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useConfirmEntry>)
  vi.mocked(useSwapEntry).mockReturnValue({
    mutate: swapMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useSwapEntry>)
  vi.mocked(useOpenCard).mockReturnValue({
    mutate: openCardMutate,
  } as unknown as ReturnType<typeof useOpenCard>)
}

function rowFor(day: string) {
  const row = screen.getByText(new RegExp(`${day}$`)).closest('li')
  if (!row) throw new Error(`no row for ${day}`)
  return within(row)
}

describe('Plan page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    weeks = {}
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('the week', () => {
    it('shows this week, a row per day, with today marked', () => {
      weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
      setup()

      renderWithProviders(<Plan />)

      expect(screen.getByText('This week')).toBeInTheDocument()
      expect(screen.getByText('Nov 16 – 22')).toBeInTheDocument()
      expect(screen.getAllByRole('listitem')).toHaveLength(7)
      expect(screen.getByText('Today · Wednesday')).toBeInTheDocument()
      expect(vi.mocked(useWeekPlan)).toHaveBeenLastCalledWith(THIS_WEEK)
    })

    it('shows a planned dinner with its source and time, and "Nothing planned" on empty days', () => {
      weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
      setup()

      renderWithProviders(<Plan />)

      const monday = rowFor('Monday')
      expect(monday.getByText('Dinner 2026-11-16')).toBeInTheDocument()
      expect(monday.getByText('HelloFresh · 35 min')).toBeInTheDocument()
      expect(rowFor('Tuesday').getByText('Nothing planned')).toBeInTheDocument()
    })

    it('lets an accepted dinner win over a suggestion on the same day', () => {
      weeks[THIS_WEEK] = {
        draft_entries: [entry('2026-11-16')],
        confirmed_entries: [
          entry('2026-11-16', {
            id: 'accepted',
            status: 'approved',
            recipe_id: 'recipe-1',
            display: {
              name: 'Roast chicken',
              image_url: null,
              prep_time_minutes: null,
              source_type: 'manual',
            },
          }),
        ],
      }
      setup()

      renderWithProviders(<Plan />)

      const monday = rowFor('Monday')
      expect(monday.getByText('Roast chicken')).toBeInTheDocument()
      expect(monday.getByText('Your recipes')).toBeInTheDocument()
      expect(monday.getByText('Planned')).toBeInTheDocument()
      expect(monday.queryByRole('button', { name: 'Accept Monday dinner' })).not.toBeInTheDocument()
    })

    it('moves to next week and back', () => {
      weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
      weeks['2026-11-23'] = { draft_entries: [entry('2026-11-23')] }
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(screen.getByRole('button', { name: 'Next week' }))

      expect(screen.getByText('Next week')).toBeInTheDocument()
      expect(screen.getByText('Nov 23 – 29')).toBeInTheDocument()
      expect(screen.getByText('Dinner 2026-11-23')).toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'Previous week' }))
      fireEvent.click(screen.getByRole('button', { name: 'Previous week' }))

      expect(screen.getByText('Last week')).toBeInTheDocument()
      expect(vi.mocked(useWeekPlan)).toHaveBeenLastCalledWith('2026-11-09')
    })
  })

  describe('an empty week', () => {
    it('asks for suggestions once when the current week is empty', () => {
      setup()

      const { rerender } = renderWithProviders(<Plan />)
      rerender(<Plan />)

      expect(generateMutate).toHaveBeenCalledTimes(1)
      expect(generateMutate).toHaveBeenCalledWith(THIS_WEEK)
    })

    it('asks for suggestions for an empty future week', () => {
      weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
      setup()

      renderWithProviders(<Plan />)
      expect(generateMutate).not.toHaveBeenCalled()

      fireEvent.click(screen.getByRole('button', { name: 'Next week' }))

      expect(generateMutate).toHaveBeenCalledWith('2026-11-23')
    })

    it('does not fill a past week, and says nothing was planned', () => {
      weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(screen.getByRole('button', { name: 'Previous week' }))

      expect(generateMutate).not.toHaveBeenCalled()
      expect(screen.getByText('Nothing was planned this week.')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Suggest dinners' })).not.toBeInTheDocument()
    })

    it('offers a button when the automatic attempt produced nothing', () => {
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(screen.getByRole('button', { name: 'Suggest dinners' }))

      expect(generateMutate).toHaveBeenCalledTimes(2)
      expect(generateMutate).toHaveBeenLastCalledWith(THIS_WEEK)
    })

    it('says so while choosing, and offers a retry when it fails', () => {
      setup({ generate: { isPending: true } })
      const { unmount } = renderWithProviders(<Plan />)
      expect(screen.getByText('Choosing dinners for this week...')).toBeInTheDocument()
      unmount()

      setup({ generate: { isError: true } })
      renderWithProviders(<Plan />)
      generateMutate.mockClear()
      fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

      expect(generateMutate).toHaveBeenCalledWith(THIS_WEEK)
    })
  })

  describe('acting on a suggestion', () => {
    beforeEach(() => {
      weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16'), entry('2026-11-17')] }
    })

    it('accepts it and reports what went on the grocery list', () => {
      confirmMutate.mockImplementation((_id, options) =>
        options.onSuccess({ entry: entry('2026-11-16'), grocery_items_added: 8 })
      )
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(screen.getByRole('button', { name: 'Accept Monday dinner' }))

      expect(confirmMutate).toHaveBeenCalledWith('entry-2026-11-16', expect.anything())
      expect(screen.getByRole('status')).toHaveTextContent('Added 8 items to your grocery list.')
    })

    it('shows why an accept failed, on that day only', () => {
      confirmMutate.mockImplementation((_id, options) =>
        options.onError(new Error('Could not bring this recipe in. Try again.'))
      )
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(screen.getByRole('button', { name: 'Accept Tuesday dinner' }))

      expect(rowFor('Tuesday').getByRole('alert')).toHaveTextContent(
        'Could not bring this recipe in. Try again.'
      )
      expect(rowFor('Monday').queryByRole('alert')).not.toBeInTheDocument()
    })

    it('swaps it', () => {
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(screen.getByRole('button', { name: 'Swap Monday dinner' }))

      expect(swapMutate).toHaveBeenCalledWith('entry-2026-11-16', expect.anything())
    })

    it('opens a catalog suggestion by importing it first', () => {
      openCardMutate.mockImplementation((_vars, options) => options.onSuccess({ id: 'recipe-9' }))
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(screen.getByRole('button', { name: 'Open Dinner 2026-11-16' }))

      expect(openCardMutate).toHaveBeenCalledWith(
        { cardId: 'card-2026-11-16', source: 'hellofresh_web', collectionSlug: '' },
        expect.anything()
      )
      expect(mockNavigate).toHaveBeenCalledWith('/recipes/recipe-9')
    })

    it('opens a recipe-backed dinner directly', () => {
      weeks[THIS_WEEK] = {
        confirmed_entries: [
          entry('2026-11-16', { status: 'approved', recipe_id: 'recipe-1', catalog_card_id: null }),
        ],
      }
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(screen.getByRole('button', { name: 'Open Dinner 2026-11-16' }))

      expect(mockNavigate).toHaveBeenCalledWith('/recipes/recipe-1')
      expect(openCardMutate).not.toHaveBeenCalled()
    })
  })

  describe('loading and failure', () => {
    it('shows loading', () => {
      setup({ weekQuery: { isLoading: true } })

      renderWithProviders(<Plan />)

      expect(screen.getByText('Loading...')).toBeInTheDocument()
      expect(generateMutate).not.toHaveBeenCalled()
    })

    it('offers a retry when the week cannot be loaded', () => {
      setup({ weekQuery: { isError: true } })

      renderWithProviders(<Plan />)

      expect(screen.getByText(/Could not load this week/)).toBeInTheDocument()
      expect(generateMutate).not.toHaveBeenCalled()
    })
  })
})
