import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, fireEvent, within, act } from '@testing-library/react'
import Plan from './Plan'
import { renderWithProviders } from '../test/renderWithProviders'
import {
  planEntry as entry,
  planMocks,
  resetPlanMocks,
  setupPlanMocks as setup,
  suggestedCard,
  suggestedRecipe,
} from '../test/planWeekMocks'
import { useWeekPlan } from '../api'
import type { WeekShoppingResponse } from '../api/types'

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

// Wednesday 2026-11-18; its week starts Sunday 2026-11-15.
const NOW = new Date('2026-11-18T10:00:00')
const THIS_WEEK = '2026-11-15'
const WEEK_DAYS = ['2026-11-15', '2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19', '2026-11-20', '2026-11-21']

function card(title: string) {
  return within(screen.getByRole('region', { name: title }))
}

function weeksAsked(): string[] {
  return [...new Set(vi.mocked(useWeekPlan).mock.calls.map(([weekStart]) => weekStart))]
}

describe('Plan page', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
    resetPlanMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows this week as a plan card, then two sample weeks', () => {
    planMocks.weeks[THIS_WEEK] = { draft_entries: WEEK_DAYS.map((d) => entry(d)) }
    setup()

    renderWithProviders(<Plan />)

    expect(screen.getByRole('region', { name: 'This week' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Next week' })).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Week of Nov 29' })).toBeInTheDocument()
    expect(weeksAsked()).toEqual([THIS_WEEK, '2026-11-22', '2026-11-29'])
  })

  it('heads each card with its dates, its people and where the week stands', () => {
    planMocks.weeks[THIS_WEEK] = {
      draft_entries: WEEK_DAYS.slice(2).map((d) => entry(d)),
      confirmed_entries: WEEK_DAYS.slice(0, 2).map((d) =>
        entry(d, { status: 'approved', recipe_id: `recipe-${d}` })
      ),
    }
    setup()

    renderWithProviders(<Plan />)

    const thisWeek = card('This week')
    expect(thisWeek.getByText('Nov 15 – 21')).toBeInTheDocument()
    expect(thisWeek.getByLabelText('People on this plan: just you')).toBeInTheDocument()
    expect(thisWeek.getByText('2 planned · 5 suggested · about 4 h 5 min of cooking')).toBeInTheDocument()
    expect(thisWeek.getByLabelText('Sunday: planned')).toBeInTheDocument()
    expect(thisWeek.getByLabelText('Monday: planned')).toBeInTheDocument()
    expect(thisWeek.getByLabelText('Saturday: suggested')).toBeInTheDocument()
  })

  it('lays the week out as a carousel of dinners, one per day', () => {
    planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
    setup()

    renderWithProviders(<Plan />)

    const dinners = within(card('This week').getByRole('list', { name: 'This week dinners' }))
    expect(dinners.getAllByRole('listitem')).toHaveLength(7)
    expect(dinners.getByLabelText('Monday: Dinner 2026-11-16')).toBeInTheDocument()
    expect(dinners.getByLabelText('Tuesday: nothing planned')).toBeInTheDocument()
    expect(dinners.getByText('Today · Wed')).toBeInTheDocument()
  })

  it('fills each empty week with suggestions', () => {
    setup()

    renderWithProviders(<Plan />)

    expect(planMocks.generateMutate.mock.calls.map(([weekStart]) => weekStart)).toEqual([
      THIS_WEEK,
      '2026-11-22',
      '2026-11-29',
    ])
  })

  it('adds a further week on request', () => {
    setup()

    renderWithProviders(<Plan />)
    fireEvent.click(screen.getByRole('button', { name: 'Show another week' }))

    expect(screen.getByRole('region', { name: 'Week of Dec 6' })).toBeInTheDocument()
  })

  it('links each card to its week editor, and to last week', () => {
    setup()

    renderWithProviders(<Plan />)

    expect(screen.getByRole('link', { name: 'Edit this week' })).toHaveAttribute('href', '/plan/2026-11-15')
    expect(screen.getByRole('link', { name: 'Edit next week' })).toHaveAttribute('href', '/plan/2026-11-22')
    expect(screen.getByRole('link', { name: 'Last week' })).toHaveAttribute('href', '/plan/2026-11-08')
  })

  it('accepts and swaps a dinner from its card', () => {
    planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
    planMocks.weeks['2026-11-22'] = { draft_entries: [entry('2026-11-23')] }
    setup()

    renderWithProviders(<Plan />)
    fireEvent.click(card('This week').getByRole('button', { name: 'Accept Monday dinner' }))
    fireEvent.click(card('Next week').getByRole('button', { name: 'Swap Monday dinner' }))

    expect(planMocks.confirmMutate).toHaveBeenCalledWith('entry-2026-11-16', expect.anything())
    expect(planMocks.swapMutate).toHaveBeenCalledWith('entry-2026-11-23', expect.anything())
  })

  it('offers to fill the empty days of a week that is under way', () => {
    planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
    planMocks.weeks['2026-11-22'] = { draft_entries: [entry('2026-11-22')] }
    setup()

    renderWithProviders(<Plan />)
    // Today is Wednesday the 18th: Wednesday to Saturday are empty this week.
    fireEvent.click(card('This week').getByRole('button', { name: 'Fill 4 empty days' }))
    expect(card('Next week').getByRole('button', { name: 'Fill 6 empty days' })).toBeInTheDocument()

    expect(planMocks.generateMutate).toHaveBeenCalledWith({
      weekStart: THIS_WEEK,
      fromDate: '2026-11-18',
    })
  })

  it('accepts a whole sample week from its card, but not the week in progress', async () => {
    planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16'), entry('2026-11-17')] }
    planMocks.weeks['2026-11-22'] = { draft_entries: [entry('2026-11-23'), entry('2026-11-24')] }
    planMocks.confirmMutateAsync.mockResolvedValue({ grocery_items_added: 0 })
    setup()

    renderWithProviders(<Plan />)
    expect(card('This week').queryByRole('button', { name: /Accept all/ })).not.toBeInTheDocument()
    await act(async () => {
      fireEvent.click(card('Next week').getByRole('button', { name: 'Accept all 2' }))
    })

    expect(planMocks.confirmMutateAsync.mock.calls.map(([id]) => id)).toEqual([
      'entry-2026-11-23',
      'entry-2026-11-24',
    ])
    expect(card('Next week').getByRole('status')).toHaveTextContent(
      'Accepted 2 dinners.'
    )
  })

  it('remixes a week\'s suggestions from today on, and says when nothing changed', () => {
    // Today is Wednesday the 18th.
    planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16'), entry('2026-11-19')] }
    planMocks.weeks['2026-11-22'] = { draft_entries: [entry('2026-11-23')] }
    planMocks.remixMutate.mockImplementation((_vars, options) => options.onSuccess({ changed: 0 }))
    setup()

    renderWithProviders(<Plan />)
    fireEvent.click(card('This week').getByRole('button', { name: 'Remix this week' }))

    expect(planMocks.remixMutate).toHaveBeenCalledWith(
      { weekStart: THIS_WEEK, fromDate: '2026-11-18' },
      expect.anything()
    )
    expect(card('This week').getByRole('status')).toHaveTextContent(
      'Nothing else to suggest for this week right now.'
    )
    expect(card('Next week').getByRole('button', { name: 'Remix next week' })).toBeInTheDocument()
  })

  it('offers no remix when a week has no suggestion left to change', () => {
    planMocks.weeks[THIS_WEEK] = {
      // One suggestion, on a day already past; the rest accepted.
      draft_entries: [entry('2026-11-16')],
      confirmed_entries: [entry('2026-11-19', { status: 'approved', recipe_id: 'recipe-1' })],
    }
    setup()

    renderWithProviders(<Plan />)

    expect(card('This week').queryByRole('button', { name: /Remix/ })).not.toBeInTheDocument()
  })

  it('removes a dinner from its card', () => {
    planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
    setup()

    renderWithProviders(<Plan />)
    fireEvent.click(card('This week').getByRole('button', { name: 'Remove Monday dinner' }))

    expect(planMocks.removeMutate).toHaveBeenCalledWith('entry-2026-11-16', expect.anything())
  })

  describe('the week\'s grocery list', () => {
    const line = (name: string, extra: Partial<WeekShoppingResponse['lines'][number]> = {}) => ({
      key: `${name.toLowerCase()}|count`,
      name,
      unit: 'count',
      to_taste: false,
      quantity: 2,
      add_quantity: 2,
      suggested: true,
      pantry_quantity: null,
      pantry_unit: null,
      pantry_counted: false,
      listed_quantity: 0,
      listed_otherwise: false,
      needs: [
        { recipe_name: 'Fried Rice', date: '2026-11-16', quantity: 1 },
        { recipe_name: 'Tofu Bowl', date: '2026-11-18', quantity: 1 },
      ],
      ...extra,
    })

    beforeEach(() => {
      planMocks.weeks[THIS_WEEK] = {
        confirmed_entries: [entry('2026-11-16', { status: 'approved', recipe_id: 'recipe-1' })],
      }
      planMocks.shopping[THIS_WEEK] = {
        week_start: THIS_WEEK,
        dinners: 2,
        lines: [
          line('Onion'),
          line('Garlic', { unit: 'clove', quantity: 5, add_quantity: 3, pantry_quantity: 2, pantry_unit: 'clove', pantry_counted: true }),
          line('Tofu', { add_quantity: 0, suggested: false, pantry_quantity: 3, pantry_unit: 'count', pantry_counted: true }),
          line('Shrimp', { unit: 'oz', quantity: 10, add_quantity: 10, suggested: false, pantry_quantity: 1, pantry_unit: 'lb' }),
        ],
      }
    })

    it('is offered on a week with an accepted dinner, and not on one without', () => {
      setup()

      renderWithProviders(<Plan />)

      expect(card('This week').getByRole('button', { name: 'Grocery list for this week' })).toBeInTheDocument()
      expect(card('Next week').queryByRole('button', { name: /Grocery list/ })).not.toBeInTheDocument()
    })

    it('opens a checklist of the week\'s ingredients with the suggested ones checked', () => {
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(card('This week').getByRole('button', { name: 'Grocery list for this week' }))

      const sheet = within(screen.getByRole('dialog', { name: 'Shopping for this week' }))
      expect(sheet.getByText(/From 2 accepted dinners/)).toBeInTheDocument()
      const box = (name: string) => sheet.getByRole('checkbox', { name: new RegExp(`^${name}`) })
      expect(box('Onion')).toBeChecked()
      expect(box('Garlic')).toBeChecked()
      // Enough in the pantry: nothing to add, so it cannot be checked.
      expect(box('Tofu')).not.toBeChecked()
      expect(box('Tofu')).toBeDisabled()
      // Pantry stock in another unit: shown, left for the user to decide.
      expect(box('Shrimp')).not.toBeChecked()
      expect(sheet.getByText('You have 1 lb; check whether it is enough')).toBeInTheDocument()
      expect(sheet.getByText('You have 2 clove, counted')).toBeInTheDocument()
      expect(sheet.getAllByText('For Fried Rice, Tofu Bowl')).toHaveLength(4)
      expect(sheet.getByRole('button', { name: 'Add 2 items to grocery list' })).toBeInTheDocument()
    })

    it('adds what is checked, and says so with a link to the list', () => {
      planMocks.addShoppingMutate.mockImplementation((_vars, options) =>
        options.onSuccess({ added: 3, skipped: [] })
      )
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(card('This week').getByRole('button', { name: 'Grocery list for this week' }))
      const sheet = within(screen.getByRole('dialog', { name: 'Shopping for this week' }))
      fireEvent.click(sheet.getByRole('checkbox', { name: /^Shrimp/ }))
      fireEvent.click(sheet.getByRole('checkbox', { name: /^Onion/ }))
      fireEvent.click(sheet.getByRole('button', { name: 'Add 2 items to grocery list' }))

      expect(planMocks.addShoppingMutate).toHaveBeenCalledWith(
        { weekStart: THIS_WEEK, keys: ['garlic|count', 'shrimp|count'] },
        expect.anything()
      )
      expect(sheet.getByRole('status')).toHaveTextContent('Added 3 items to your grocery list.')
      expect(sheet.getByRole('link', { name: 'Open the list' })).toHaveAttribute('href', '/grocery')
    })
  })

  it('says which meal the plan covers', () => {
    planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16')] }
    setup()

    renderWithProviders(<Plan />)

    expect(card('This week').getByLabelText('Meals in this plan: dinner')).toHaveTextContent('Dinner')
  })

  describe('adding something to an empty day', () => {
    beforeEach(() => {
      planMocks.weeks[THIS_WEEK] = {
        draft_entries: [entry('2026-11-16', { catalog_card_id: 'card-held' })],
      }
      planMocks.recommendations = [
        suggestedCard('card-held', 'Already on Monday'),
        suggestedCard('card-1', 'Lemon Chicken'),
        suggestedRecipe('recipe-1', 'Roast Vegetables'),
      ]
    })

    it('opens a band of suggestions under the week, without what the week already holds', () => {
      setup()

      renderWithProviders(<Plan />)
      expect(screen.queryByRole('region', { name: 'Add a dinner for Sunday' })).not.toBeInTheDocument()
      fireEvent.click(card('This week').getByRole('button', { name: 'Add something for Sunday' }))

      const band = within(card('This week').getByRole('region', { name: 'Add a dinner for Sunday' }))
      const suggestions = within(band.getByRole('list', { name: 'Suggestions for Sunday' }))
      expect(suggestions.getAllByRole('listitem')).toHaveLength(2)
      expect(suggestions.getByText('Lemon Chicken')).toBeInTheDocument()
      expect(suggestions.getByText('Home Chef · 30 min')).toBeInTheDocument()
      expect(suggestions.getByText('Roast Vegetables')).toBeInTheDocument()
      expect(suggestions.queryByText('Already on Monday')).not.toBeInTheDocument()
      expect(band.getByRole('link', { name: /Browse all recipes/ })).toHaveAttribute('href', '/recipes')
    })

    it('puts the chosen catalog card on that day, accepts it and closes the band', async () => {
      planMocks.createMutateAsync.mockResolvedValue({ id: 'new-entry' })
      planMocks.confirmMutateAsync.mockResolvedValue({ grocery_items_added: 0 })
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(card('This week').getByRole('button', { name: 'Add something for Sunday' }))
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Add Lemon Chicken' }))
      })

      expect(planMocks.createMutateAsync).toHaveBeenCalledWith({
        date: '2026-11-15',
        meal_type: 'dinner',
        catalog_card_id: 'card-1',
      })
      expect(planMocks.confirmMutateAsync).toHaveBeenCalledWith('new-entry')
      expect(card('This week').getByRole('status')).toHaveTextContent(
        'Added.'
      )
      expect(screen.queryByRole('region', { name: 'Add a dinner for Sunday' })).not.toBeInTheDocument()
    })

    it('adds a library recipe by its recipe id', async () => {
      planMocks.createMutateAsync.mockResolvedValue({ id: 'new-entry' })
      planMocks.confirmMutateAsync.mockResolvedValue({ grocery_items_added: 0 })
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(card('This week').getByRole('button', { name: 'Add something for Tuesday' }))
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Add Roast Vegetables' }))
      })

      expect(planMocks.createMutateAsync).toHaveBeenCalledWith({
        date: '2026-11-17',
        meal_type: 'dinner',
        recipe_id: 'recipe-1',
      })
    })

    it('keeps the band open and says why when the dinner cannot be added', async () => {
      planMocks.createMutateAsync.mockRejectedValue(new Error('Catalog card not found'))
      setup()

      renderWithProviders(<Plan />)
      fireEvent.click(card('This week').getByRole('button', { name: 'Add something for Sunday' }))
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Add Lemon Chicken' }))
      })

      const band = within(screen.getByRole('region', { name: 'Add a dinner for Sunday' }))
      expect(band.getByRole('alert')).toHaveTextContent('Catalog card not found')
      expect(planMocks.confirmMutateAsync).not.toHaveBeenCalled()
    })

    it('closes the band from its close button, or by pressing the day again', () => {
      setup()

      renderWithProviders(<Plan />)
      const addSunday = card('This week').getByRole('button', { name: 'Add something for Sunday' })
      fireEvent.click(addSunday)
      fireEvent.click(screen.getByRole('button', { name: 'Close' }))
      expect(screen.queryByRole('region', { name: 'Add a dinner for Sunday' })).not.toBeInTheDocument()

      fireEvent.click(addSunday)
      fireEvent.click(addSunday)
      expect(screen.queryByRole('region', { name: 'Add a dinner for Sunday' })).not.toBeInTheDocument()
    })
  })
})
