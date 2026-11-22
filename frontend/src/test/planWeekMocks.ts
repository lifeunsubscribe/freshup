import { vi } from 'vitest'
import {
  useWeekPlan,
  useGenerateDraft,
  useConfirmEntry,
  useSwapEntry,
  useOpenCard,
  useCreatePlanEntry,
  useRemixWeek,
  useRemovePlanEntry,
} from '../api'
import { useRecommendations } from '../api/hooks/useRecipes'
import type { MealPlanEntryDisplay, RecommendedItem, WeekViewResponse } from '../api/types'

/**
 * Shared stand-ins for the plan hooks, for tests of the Plan page and the week
 * editor. The test file must itself call vi.mock('../api', ...) for the eight
 * plan hooks and vi.mock('../api/hooks/useRecipes', ...) for useRecommendations;
 * this module only fills those mocks in.
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
  createMutateAsync: vi.fn(),
  remixMutate: vi.fn(),
  removeMutate: vi.fn(),
  /** What GET /recommendations returns for the add band. */
  recommendations: [] as RecommendedItem[],
  /** Weeks the mocked GET /plan/week knows about; any other week is empty. */
  weeks: {} as Record<string, Partial<WeekViewResponse>>,
}

export function resetPlanMocks() {
  planMocks.weeks = {}
  planMocks.recommendations = []
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
  vi.mocked(useCreatePlanEntry).mockReturnValue({
    mutateAsync: planMocks.createMutateAsync,
  } as unknown as ReturnType<typeof useCreatePlanEntry>)
  vi.mocked(useRemixWeek).mockReturnValue({
    mutate: planMocks.remixMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useRemixWeek>)
  vi.mocked(useRemovePlanEntry).mockReturnValue({
    mutate: planMocks.removeMutate,
    isPending: false,
  } as unknown as ReturnType<typeof useRemovePlanEntry>)
  vi.mocked(useRecommendations).mockReturnValue({
    data: planMocks.recommendations,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof useRecommendations>)
}

/** A catalog card as GET /recommendations returns it. */
export function suggestedCard(id: string, name: string): RecommendedItem {
  return {
    kind: 'card',
    card: {
      id,
      name,
      source_type: 'homechef_web',
      headline: null,
      image_url: null,
      prep_time_minutes: 30,
      rating: null,
      rating_count: null,
      recipe_url: `https://example.test/${id}`,
      recipe_id: null,
      is_persisted: false,
      tags: [],
    },
  }
}

/** A library recipe as GET /recommendations returns it. */
export function suggestedRecipe(id: string, name: string): RecommendedItem {
  return {
    kind: 'recipe',
    recipe: {
      id,
      name,
      source_type: 'manual',
      created_at: '2026-11-01T00:00:00',
      tags: [],
      cook_time_minutes: 20,
      prep_time_minutes: 10,
      base_servings: 2,
    },
  }
}
