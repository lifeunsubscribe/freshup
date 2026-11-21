import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import ThisWeek from '../ThisWeek'
import { renderWithProviders } from '../../../test/renderWithProviders'
import {
  useWeekPlan,
  useGenerateDraft,
  useConfirmEntry,
  useSwapEntry,
  useOpenCard,
} from '../../../api'

vi.mock('../../../api', () => ({
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

// Pin to a known Monday so getCurrentMondayStr() is deterministic.
// 2026-11-17 is a Tuesday; the Monday of that week is 2026-11-16.
const TEST_DATE = new Date('2026-11-16T10:00:00')
const WEEK_START = '2026-11-16'
const DATES = [
  '2026-11-16', '2026-11-17', '2026-11-18', '2026-11-19',
  '2026-11-20', '2026-11-21', '2026-11-22',
]

function makeDraftEntry(i: number) {
  return {
    id: `entry-${i}`,
    date: DATES[i],
    meal_type: 'dinner',
    recipe_id: null,
    catalog_card_id: `card-${i}`,
    prepared_food_id: null,
    planned_servings: 2,
    status: 'draft',
    notes: null,
    display: {
      name: `Recipe ${i}`,
      image_url: null as string | null,
      prep_time_minutes: 30,
      source_type: 'hellofresh_web',
    },
  }
}

function makeConfirmedEntry(i: number) {
  return {
    ...makeDraftEntry(i),
    id: `entry-${i}-confirmed`,
    status: 'approved',
    recipe_id: `recipe-${i}`,
    catalog_card_id: null,
  }
}

const mockGenerateMutate = vi.fn()
const mockConfirmMutate = vi.fn()
const mockSwapMutate = vi.fn()
const mockOpenCardMutate = vi.fn()
const mockGenerateReset = vi.fn()

function setupMocks({
  draftEntries = [] as ReturnType<typeof makeDraftEntry>[],
  confirmedEntries = [] as ReturnType<typeof makeConfirmedEntry>[],
  generateIsError = false,
  isLoading = false,
} = {}) {
  vi.mocked(useWeekPlan).mockReturnValue({
    data: {
      week_start: WEEK_START,
      confirmed_entries: confirmedEntries,
      draft_entries: draftEntries,
    },
    isLoading,
    isError: false,
  } as unknown as ReturnType<typeof useWeekPlan>)

  vi.mocked(useGenerateDraft).mockReturnValue({
    mutate: mockGenerateMutate,
    isError: generateIsError,
    reset: mockGenerateReset,
  } as unknown as ReturnType<typeof useGenerateDraft>)

  vi.mocked(useConfirmEntry).mockReturnValue({
    mutate: mockConfirmMutate,
  } as unknown as ReturnType<typeof useConfirmEntry>)

  vi.mocked(useSwapEntry).mockReturnValue({
    mutate: mockSwapMutate,
  } as unknown as ReturnType<typeof useSwapEntry>)

  vi.mocked(useOpenCard).mockReturnValue({
    mutate: mockOpenCardMutate,
  } as unknown as ReturnType<typeof useOpenCard>)
}

describe('ThisWeek', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
    vi.setSystemTime(TEST_DATE)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('rendering seven tiles with drafts', () => {
    it('renders all seven day labels', () => {
      setupMocks({ draftEntries: DATES.map((_, i) => makeDraftEntry(i)) })

      renderWithProviders(<ThisWeek />)

      for (const label of ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']) {
        expect(screen.getByText(label)).toBeInTheDocument()
      }
    })

    it('puts no "Suggested" label on draft tiles', () => {
      setupMocks({ draftEntries: DATES.map((_, i) => makeDraftEntry(i)) })

      renderWithProviders(<ThisWeek />)

      expect(screen.queryByText('Suggested')).not.toBeInTheDocument()
    })

    it('shows the picture the entry carries, before and after it is accepted', () => {
      const suggested = makeDraftEntry(0)
      suggested.display.image_url = 'https://img.test/suggested.jpg'
      const accepted = makeConfirmedEntry(1)
      accepted.display.image_url = 'https://img.test/accepted.jpg'
      setupMocks({ draftEntries: [suggested], confirmedEntries: [accepted] })

      renderWithProviders(<ThisWeek />)

      expect(screen.getByAltText('Recipe 0')).toHaveAttribute('src', 'https://img.test/suggested.jpg')
      expect(screen.getByAltText('Recipe 1')).toHaveAttribute('src', 'https://img.test/accepted.jpg')
    })

    it('names the source, not its internal type', () => {
      const own = makeDraftEntry(1)
      own.display.source_type = 'manual'
      const homeChef = makeDraftEntry(2)
      homeChef.display.source_type = 'homechef_web'
      setupMocks({ draftEntries: [makeDraftEntry(0), own, homeChef] })

      renderWithProviders(<ThisWeek />)

      expect(screen.getByText('HelloFresh')).toBeInTheDocument()
      expect(screen.getByText('Your recipes')).toBeInTheDocument()
      expect(screen.getByText('Home Chef')).toBeInTheDocument()
    })

    it('shows source byline on each draft tile', () => {
      setupMocks({ draftEntries: DATES.map((_, i) => makeDraftEntry(i)) })

      renderWithProviders(<ThisWeek />)

      expect(screen.getAllByText('HelloFresh')).toHaveLength(7)
    })

    it('shows no "Suggested" pill on confirmed tiles', () => {
      setupMocks({ confirmedEntries: DATES.map((_, i) => makeConfirmedEntry(i)) })

      renderWithProviders(<ThisWeek />)

      expect(screen.queryByText('Suggested')).not.toBeInTheDocument()
    })

    it('renders the section header', () => {
      setupMocks({ draftEntries: DATES.map((_, i) => makeDraftEntry(i)) })

      renderWithProviders(<ThisWeek />)

      expect(screen.getByText('This week')).toBeInTheDocument()
    })
  })

  describe('accept and swap actions', () => {
    it('calls confirm endpoint when accept button is clicked', () => {
      setupMocks({ draftEntries: DATES.map((_, i) => makeDraftEntry(i)) })

      renderWithProviders(<ThisWeek />)

      const acceptButtons = screen.getAllByRole('button', { name: 'Accept suggestion' })
      fireEvent.click(acceptButtons[0])

      expect(mockConfirmMutate).toHaveBeenCalledWith('entry-0')
    })

    it('calls swap endpoint when swap button is clicked', () => {
      setupMocks({ draftEntries: DATES.map((_, i) => makeDraftEntry(i)) })

      renderWithProviders(<ThisWeek />)

      const swapButtons = screen.getAllByRole('button', { name: 'Swap suggestion' })
      fireEvent.click(swapButtons[0])

      expect(mockSwapMutate).toHaveBeenCalledWith('entry-0')
    })

    it('does not show accept/swap on confirmed tiles', () => {
      setupMocks({ confirmedEntries: DATES.map((_, i) => makeConfirmedEntry(i)) })

      renderWithProviders(<ThisWeek />)

      expect(screen.queryByRole('button', { name: 'Accept suggestion' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Swap suggestion' })).not.toBeInTheDocument()
    })
  })

  describe('empty week triggers auto-generate', () => {
    it('calls generate exactly once when week is empty on mount', () => {
      setupMocks({ draftEntries: [], confirmedEntries: [] })

      renderWithProviders(<ThisWeek />)

      expect(mockGenerateMutate).toHaveBeenCalledTimes(1)
      expect(mockGenerateMutate).toHaveBeenCalledWith(WEEK_START)
    })

    it('does not call generate when week has draft entries', () => {
      setupMocks({ draftEntries: DATES.map((_, i) => makeDraftEntry(i)) })

      renderWithProviders(<ThisWeek />)

      expect(mockGenerateMutate).not.toHaveBeenCalled()
    })

    it('does not call generate when week has confirmed entries', () => {
      setupMocks({ confirmedEntries: DATES.map((_, i) => makeConfirmedEntry(i)) })

      renderWithProviders(<ThisWeek />)

      expect(mockGenerateMutate).not.toHaveBeenCalled()
    })
  })

  describe('failed generate shows retry line', () => {
    it('shows error message when generate fails', () => {
      setupMocks({ generateIsError: true })

      renderWithProviders(<ThisWeek />)

      expect(screen.getByText(/Could not suggest a week yet\./)).toBeInTheDocument()
    })

    it('shows Try again button when generate fails', () => {
      setupMocks({ generateIsError: true })

      renderWithProviders(<ThisWeek />)

      expect(screen.getByRole('button', { name: /Try again/ })).toBeInTheDocument()
    })

    it('calls reset and re-generates when Try again is clicked', () => {
      setupMocks({ generateIsError: true })

      renderWithProviders(<ThisWeek />)
      vi.clearAllMocks()

      fireEvent.click(screen.getByRole('button', { name: /Try again/ }))

      expect(mockGenerateReset).toHaveBeenCalled()
      expect(mockGenerateMutate).toHaveBeenCalledWith(WEEK_START)
    })
  })
})
