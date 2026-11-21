import { vi } from 'vitest'
import {
  useWeekPlan,
  useGenerateDraft,
  useConfirmEntry,
  useSwapEntry,
  useOpenCard,
} from '../api'
import type { MealPlanEntryDisplay, WeekViewResponse } from '../api/types'

/**
 * Shared stand-ins for the plan hooks, for tests of the Plan page and the week
 * editor. The test file must itself call vi.mock('../api', ...) for the five
 * hooks; this module only fills those mocks in.
 */

export function planEntry(
  date: string,
  overrides: Partial<MealPlanEntryDisplay> = {}
): MealPlanEntryDisplay {
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

export const planMocks = {
  generateMutate: vi.fn(),
  generateReset: vi.fn(),
  confirmMutate: vi.fn(),
  confirmMutateAsync: vi.fn(),
  swapMutate: vi.fn(),
  openCardMutate: vi.fn(),
  /** Weeks the mocked GET /plan/week knows about; any other week is empty. */
  weeks: {} as Record<string, Partial<WeekViewResponse>>,
}

export function resetPlanMocks() {
  planMocks.weeks = {}
}

export function setupPlanMocks({
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
        : {
            week_start: weekStart,
            confirmed_entries: [],
            draft_entries: [],
            ...planMocks.weeks[weekStart],
          },
    isLoading: weekQuery.isLoading ?? false,
    isError: weekQuery.isError ?? false,
    refetch: vi.fn(),
  })) as unknown as typeof useWeekPlan)

  vi.mocked(useGenerateDraft).mockReturnValue({
    mutate: planMocks.generateMutate,
    reset: planMocks.generateReset,
    isPending: generate.isPending ?? false,
    isError: generate.isError ?? false,
  } as unknown as ReturnType<typeof useGenerateDraft>)
  vi.mocked(useConfirmEntry).mockReturnValue({
    mutate: planMocks.confirmMutate,
    mutateAsync: planMocks.confirmMutateAsync,
    isPending: false,
  } as unknown as ReturnType<typeof useConfirmEntry>)
  vi.mocked(useSwapEntry).mockReturnValue({
    mutate: planMocks.swapMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useSwapEntry>)
  vi.mocked(useOpenCard).mockReturnValue({
    mutate: planMocks.openCardMutate,
  } as unknown as ReturnType<typeof useOpenCard>)
}
