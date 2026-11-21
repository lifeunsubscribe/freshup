import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, fireEvent, within, act } from '@testing-library/react'
import Plan from './Plan'
import { renderWithProviders } from '../test/renderWithProviders'
import { planEntry as entry, planMocks, resetPlanMocks, setupPlanMocks as setup } from '../test/planWeekMocks'
import { useWeekPlan } from '../api'

vi.mock('../api', () => ({
  useWeekPlan: vi.fn(),
  useGenerateDraft: vi.fn(),
  useConfirmEntry: vi.fn(),
  useSwapEntry: vi.fn(),
  useOpenCard: vi.fn(),
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

  it('accepts a whole week from its card', async () => {
    planMocks.weeks[THIS_WEEK] = { draft_entries: [entry('2026-11-16'), entry('2026-11-17')] }
    planMocks.confirmMutateAsync.mockResolvedValue({ grocery_items_added: 4 })
    setup()

    renderWithProviders(<Plan />)
    await act(async () => {
      fireEvent.click(card('This week').getByRole('button', { name: 'Accept all 2' }))
    })

    expect(planMocks.confirmMutateAsync).toHaveBeenCalledTimes(2)
    expect(card('This week').getByRole('status')).toHaveTextContent(
      'Accepted 2 dinners. Added 8 items to your grocery list.'
    )
  })
})
