import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, fireEvent, within, act } from '@testing-library/react'
import { Routes, Route } from 'react-router-dom'
import PlanWeek from './PlanWeek'
import { renderWithProviders } from '../test/renderWithProviders'
import {
  planEntry as entry,
  planMocks,
  resetPlanMocks,
  setupPlanMocks as setup,
  suggestedCard,
} from '../test/planWeekMocks'
import { useWeekPlan } from '../api'

vi.mock('../api', () => ({
  useWeekPlan: vi.fn(),
  useGenerateDraft: vi.fn(),
  useConfirmEntry: vi.fn(),
  useSwapEntry: vi.fn(),
  useOpenCard: vi.fn(),
  useCreatePlanEntry: vi.fn(),
  useRemixWeek: vi.fn(),
  useRemovePlanEntry: vi.fn(),
  useWeekShopping: vi.fn(),
  useAddWeekShopping: vi.fn(),
}))

vi.mock('../api/hooks/useRecipes', () => ({
  useRecommendations: vi.fn(),
}))

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ currentUser: { name: 'Sarah' } }),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

// Wednesday 2026-11-18; its week starts Sunday 2026-11-15.
const NOW = new Date('2026-11-18T10:00:00')
const THIS_WEEK = '2026-11-15'

function renderWeek(day: string = THIS_WEEK) {
  return renderWithProviders(
    <Routes>
      <Route path="/plan" element={<div>All plans page</div>} />
      <Route path="/plan/:weekStart" element={<PlanWeek />} />
    </Routes>,
    { route: `/plan/${day}` }
  )
}

function rowFor(day: string) {
  const row = screen.getByText(new RegExp(`${day}$`)).closest('li')
  if (!row) throw new Error(`no row for ${day}`)
  return within(row)
}

describe('Week editor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    resetPlanMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('the week', () => {
    it('shows the week in the address, a row per day, with today marked', () => {
      planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
      setup()

      renderWeek()

      expect(screen.getByText('This week')).toBeInTheDocument()
      expect(screen.getByText('Nov 15 – 21')).toBeInTheDocument()
      const rows = within(screen.getByRole('list', { name: 'Dinners this week' }))
      expect(rows.getAllByRole('listitem')).toHaveLength(7)
      expect(screen.getByText('Today · Wednesday')).toBeInTheDocument()
      expect(vi.mocked(useWeekPlan)).toHaveBeenLastCalledWith(THIS_WEEK)
    })

    it('opens the week that holds any day given in the address', () => {
      setup()

      renderWeek('2026-11-19')

      expect(vi.mocked(useWeekPlan)).toHaveBeenLastCalledWith(THIS_WEEK)
    })

    it('goes back to the plans when the address is not a date', () => {
      setup()

      renderWeek('soon')

      expect(screen.getByText('All plans page')).toBeInTheDocument()
    })

    it('summarises the week and says whose plan it is', () => {
      planMocks.weeks[THIS_WEEK] = {
        draft_entries: [entry('2026-11-17'), entry('2026-11-18')],
        confirmed_entries: [entry('2026-11-16', { status: 'approved', recipe_id: 'recipe-1' })],
      }
      setup()

      renderWeek()

      expect(screen.getByText('1 planned · 2 suggested · about 1 h 45 min of cooking')).toBeInTheDocument()
      expect(screen.getByLabelText('People on this plan: just you')).toHaveTextContent('S')
      const glance = within(screen.getByRole('list', { name: 'The week at a glance' }))
      expect(glance.getByLabelText('Monday: planned')).toBeInTheDocument()
      expect(glance.getByLabelText('Tuesday: suggested')).toBeInTheDocument()
      expect(glance.getByLabelText('Thursday: nothing planned')).toBeInTheDocument()
    })

    it('shows a planned dinner with its source and time, and "Nothing planned" on empty days', () => {
      planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
      setup()

      renderWeek()

      const monday = rowFor('Monday')
      expect(monday.getByText('Dinner 2026-11-16')).toBeInTheDocument()
      expect(monday.getByText('HelloFresh · 35 min')).toBeInTheDocument()
      expect(rowFor('Tuesday').getByText('Nothing planned')).toBeInTheDocument()
    })

    it('lets an accepted dinner win over a suggestion on the same day', () => {
      planMocks.weeks[THIS_WEEK] = {
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

      renderWeek()

      const monday = rowFor('Monday')
      expect(monday.getByText('Roast chicken')).toBeInTheDocument()
      expect(monday.getByText('Your recipes')).toBeInTheDocument()
      expect(monday.getByText('Planned')).toBeInTheDocument()
      expect(monday.queryByRole('button', { name: 'Accept Monday dinner' })).not.toBeInTheDocument()
    })

    it('steps to the next and previous week', () => {
      planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: 'Next week' }))
      fireEvent.click(screen.getByRole('button', { name: 'Previous week' }))

      expect(mockNavigate).toHaveBeenNthCalledWith(1, '/plan/2026-11-22')
      expect(mockNavigate).toHaveBeenNthCalledWith(2, '/plan/2026-11-08')
    })

    it('names other weeks by where they are', () => {
      setup()

      renderWeek('2026-11-23')
      expect(screen.getByText('Next week')).toBeInTheDocument()
      expect(screen.getByText('Nov 22 – 28')).toBeInTheDocument()
    })
  })

  describe('an empty week', () => {
    it('asks for suggestions once when the current week is empty', () => {
      setup()

      const { rerender } = renderWeek()
      rerender(
        <Routes>
          <Route path="/plan/:weekStart" element={<PlanWeek />} />
        </Routes>
      )

      expect(planMocks.generateMutate).toHaveBeenCalledTimes(1)
      expect(planMocks.generateMutate).toHaveBeenCalledWith(THIS_WEEK)
    })

    it('asks for suggestions for an empty future week', () => {
      setup()

      renderWeek('2026-11-23')

      expect(planMocks.generateMutate).toHaveBeenCalledWith('2026-11-22')
    })

    it('does not fill a past week, and says nothing was planned', () => {
      setup()

      renderWeek('2026-11-09')

      expect(screen.getByText('Last week')).toBeInTheDocument()
      expect(planMocks.generateMutate).not.toHaveBeenCalled()
      expect(screen.getByText('Nothing was planned this week.')).toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Suggest dinners' })).not.toBeInTheDocument()
    })

    it('offers a button when the automatic attempt produced nothing', () => {
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: 'Suggest dinners' }))

      expect(planMocks.generateMutate).toHaveBeenCalledTimes(2)
      expect(planMocks.generateMutate).toHaveBeenLastCalledWith(THIS_WEEK)
    })

    it('says so while choosing, and offers a retry when it fails', () => {
      setup({ generate: { isPending: true } })
      const { unmount } = renderWeek()
      expect(screen.getByText('Choosing dinners for this week...')).toBeInTheDocument()
      unmount()

      setup({ generate: { isError: true } })
      renderWeek()
      planMocks.generateMutate.mockClear()
      fireEvent.click(screen.getByRole('button', { name: 'Try again' }))

      expect(planMocks.generateMutate).toHaveBeenCalledWith(THIS_WEEK)
    })
  })

  describe('a week with empty days', () => {
    it('offers suggestions for the empty days from today on', () => {
      // Today is Wednesday the 18th. Sunday and Tuesday are empty but past.
      planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16'), entry('2026-11-19')] }
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: 'Suggest for 3 empty days' }))

      expect(planMocks.generateMutate).toHaveBeenCalledTimes(1)
      expect(planMocks.generateMutate).toHaveBeenCalledWith({
        weekStart: THIS_WEEK,
        fromDate: '2026-11-18',
      })
    })

    it('offers nothing when the only empty days are past, or the week is full', () => {
      planMocks.weeks[THIS_WEEK] = {
        draft_entries: ['2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21'].map((d) => entry(d)),
      }
      setup()

      renderWeek()

      expect(screen.queryByRole('button', { name: /Suggest for/ })).not.toBeInTheDocument()
    })
  })

  describe('acting on suggestions', () => {
    beforeEach(() => {
      planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16'), entry('2026-11-17')] }
    })

    it('accepts one, without touching the grocery list', () => {
      planMocks.confirmMutate.mockImplementation((_id, options) =>
        options.onSuccess({ entry: entry('2026-11-16'), grocery_items_added: 0 })
      )
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: 'Accept Monday dinner' }))

      expect(planMocks.confirmMutate).toHaveBeenCalledWith('entry-2026-11-16', expect.anything())
      expect(screen.getByRole('status')).toHaveTextContent(
        'Accepted.'
      )
    })

    it('shows why an accept failed, on that day only', () => {
      planMocks.confirmMutate.mockImplementation((_id, options) =>
        options.onError(new Error('Could not bring this recipe in. Try again.'))
      )
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: 'Accept Tuesday dinner' }))

      expect(rowFor('Tuesday').getByRole('alert')).toHaveTextContent(
        'Could not bring this recipe in. Try again.'
      )
      expect(rowFor('Monday').queryByRole('alert')).not.toBeInTheDocument()
    })

    it('does not offer "Accept all" for the week in progress', () => {
      setup()

      renderWeek()

      expect(screen.queryByRole('button', { name: /Accept all/ })).not.toBeInTheDocument()
    })

    it('accepts all of a later week in order', async () => {
      planMocks.weeks['2026-11-22'] = { draft_entries: [entry('2026-11-23'), entry('2026-11-24')] }
      planMocks.confirmMutateAsync
        .mockResolvedValueOnce({ grocery_items_added: 0 })
        .mockResolvedValueOnce({ grocery_items_added: 0 })
      setup()

      renderWeek('2026-11-22')
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Accept all 2' }))
      })

      expect(planMocks.confirmMutateAsync.mock.calls.map(([id]) => id)).toEqual([
        'entry-2026-11-23',
        'entry-2026-11-24',
      ])
      expect(screen.getByRole('status')).toHaveTextContent(
        'Accepted 2 dinners.'
      )
    })

    it('stops accepting all at the first failure and says which day', async () => {
      planMocks.weeks['2026-11-22'] = { draft_entries: [entry('2026-11-23'), entry('2026-11-24')] }
      planMocks.confirmMutateAsync
        .mockResolvedValueOnce({ grocery_items_added: 8 })
        .mockRejectedValueOnce(new Error('Could not bring this recipe in. Try again.'))
      setup()

      renderWeek('2026-11-22')
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Accept all 2' }))
      })

      expect(screen.getByRole('status')).toHaveTextContent('Accepted 1 dinner.')
      expect(rowFor('Tuesday').getByRole('alert')).toHaveTextContent(
        'Could not bring this recipe in. Try again.'
      )
    })

    it('adds something to an empty day from a band under that day', async () => {
      planMocks.recommendations = [suggestedCard('card-1', 'Lemon Chicken')]
      planMocks.createMutateAsync.mockResolvedValue({ id: 'new-entry' })
      planMocks.confirmMutateAsync.mockResolvedValue({ grocery_items_added: 3 })
      setup()

      renderWeek()
      const wednesday = screen.getByText('Today · Wednesday').closest('li')
      fireEvent.click(screen.getByRole('button', { name: 'Add something for Wednesday' }))
      // The band opens inside that day's row, not elsewhere on the page.
      expect(screen.getByRole('region', { name: 'Add a dinner for Wednesday' }).closest('li')).toBe(
        wednesday
      )
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Add Lemon Chicken' }))
      })

      expect(planMocks.createMutateAsync).toHaveBeenCalledWith({
        date: '2026-11-18',
        meal_type: 'dinner',
        catalog_card_id: 'card-1',
      })
      expect(planMocks.confirmMutateAsync).toHaveBeenCalledWith('new-entry')
      expect(screen.queryByRole('region', { name: 'Add a dinner for Wednesday' })).not.toBeInTheDocument()
    })

    it('leaves a dinner that could not be accepted on the day as a suggestion', async () => {
      planMocks.recommendations = [suggestedCard('card-1', 'Lemon Chicken')]
      planMocks.createMutateAsync.mockResolvedValue({ id: 'entry-2026-11-17' })
      planMocks.confirmMutateAsync.mockRejectedValue(
        new Error('Could not bring this recipe in. Try again.')
      )
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: 'Add something for Wednesday' }))
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Add Lemon Chicken' }))
      })

      // The mocked week still shows Tuesday's suggestion under the same id.
      expect(rowFor('Tuesday').getByRole('alert')).toHaveTextContent(
        'Could not bring this recipe in. Try again.'
      )
    })

    it('remixes the week from today on', () => {
      // Today is Wednesday the 18th; give the week a suggestion that is still ahead.
      planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16'), entry('2026-11-20')] }
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: "Remix this week's suggestions" }))

      expect(planMocks.remixMutate).toHaveBeenCalledWith(
        { weekStart: THIS_WEEK, fromDate: '2026-11-18' },
        expect.anything()
      )
      expect(screen.getByLabelText('Meals in this plan: dinner')).toBeInTheDocument()
    })

    it('removes a dinner and says what came off the grocery list', () => {
      planMocks.weeks[THIS_WEEK] = {
        confirmed_entries: [entry('2026-11-16', { status: 'approved', recipe_id: 'recipe-1' })],
        draft_entries: [entry('2026-11-17')],
      }
      planMocks.removeMutate.mockImplementation((_id, options) =>
        options.onSuccess({ grocery_items_removed: 5 })
      )
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: 'Remove Monday dinner' }))

      expect(planMocks.removeMutate).toHaveBeenCalledWith('entry-2026-11-16', expect.anything())
      expect(screen.getByRole('status')).toHaveTextContent(
        'Removed. Took 5 items off your grocery list.'
      )
      // A suggestion can be removed too.
      expect(screen.getByRole('button', { name: 'Remove Tuesday dinner' })).toBeInTheDocument()
    })

    it('says only "Removed." when nothing was on the grocery list for it', () => {
      planMocks.removeMutate.mockImplementation((_id, options) =>
        options.onSuccess({ grocery_items_removed: 0 })
      )
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: 'Remove Monday dinner' }))

      expect(screen.getByRole('status')).toHaveTextContent(/^Removed\.$/)
    })

    it('swaps one', () => {
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: 'Swap Monday dinner' }))

      expect(planMocks.swapMutate).toHaveBeenCalledWith('entry-2026-11-16', expect.anything())
    })

    it('opens a catalog suggestion by importing it first', () => {
      planMocks.openCardMutate.mockImplementation((_vars, options) =>
        options.onSuccess({ id: 'recipe-9' })
      )
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: 'Open Dinner 2026-11-16' }))

      expect(planMocks.openCardMutate).toHaveBeenCalledWith(
        { cardId: 'card-2026-11-16', source: 'hellofresh_web', collectionSlug: '' },
        expect.anything()
      )
      expect(mockNavigate).toHaveBeenCalledWith('/recipes/recipe-9')
    })

    it('opens a recipe-backed dinner directly', () => {
      planMocks.weeks[THIS_WEEK] = {
        confirmed_entries: [
          entry('2026-11-16', { status: 'approved', recipe_id: 'recipe-1', catalog_card_id: null }),
        ],
      }
      setup()

      renderWeek()
      fireEvent.click(screen.getByRole('button', { name: 'Open Dinner 2026-11-16' }))

      expect(mockNavigate).toHaveBeenCalledWith('/recipes/recipe-1')
      expect(planMocks.openCardMutate).not.toHaveBeenCalled()
    })
  })

  describe('loading and failure', () => {
    it('shows loading', () => {
      setup({ weekQuery: { isLoading: true } })

      renderWeek()

      expect(screen.getByText('Loading...')).toBeInTheDocument()
      expect(planMocks.generateMutate).not.toHaveBeenCalled()
    })

    it('offers a retry when the week cannot be loaded', () => {
      setup({ weekQuery: { isError: true } })

      renderWeek()

      expect(screen.getByText(/Could not load this week/)).toBeInTheDocument()
      expect(planMocks.generateMutate).not.toHaveBeenCalled()
    })
  })
})
