import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../client'
import { groceryKeys } from './useGrocery'
import type {
  CreateEntryRequest,
  MealPlanEntry,
  WeekViewResponse,
  DraftGenerateResponse,
  ConfirmEntryResponse,
  SwapEntryResponse,
  RemixWeekResponse,
  RemoveEntryResponse,
} from '../types'

export const planKeys = {
  all: ['plan'] as const,
  entries: () => [...planKeys.all, 'entries'] as const,
  week: (weekStart: string) => [...planKeys.all, 'week', weekStart] as const,
}

export function useWeekPlan(weekStart: string) {
  return useQuery({
    queryKey: planKeys.week(weekStart),
    queryFn: () =>
      apiClient<WeekViewResponse>(`/plan/week?week_start=${encodeURIComponent(weekStart)}`, {
        method: 'GET',
      }),
  })
}

/** A week to suggest dinners for: all its free days, or only those from `fromDate` on. */
export type GenerateDraftRequest = string | { weekStart: string; fromDate: string }

/**
 * Suggest a dinner for each day of a week that has none. The week is named by
 * its first day (a Sunday).
 */
export function useGenerateDraft() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: GenerateDraftRequest) =>
      apiClient<DraftGenerateResponse>('/plan/draft/generate', {
        method: 'POST',
        body: JSON.stringify(
          typeof request === 'string'
            ? { week_start: request }
            : { week_start: request.weekStart, from_date: request.fromDate }
        ),
      }),
    onSuccess: (_, request) => {
      const weekStart = typeof request === 'string' ? request : request.weekStart
      queryClient.invalidateQueries({ queryKey: planKeys.week(weekStart) })
    },
  })
}

export function useConfirmEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (entryId: string) =>
      apiClient<ConfirmEntryResponse>(
        `/plan/entries/${encodeURIComponent(entryId)}/confirm`,
        { method: 'PUT' }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: planKeys.all })
      // Accepting a dinner puts its ingredients on the grocery list.
      queryClient.invalidateQueries({ queryKey: groceryKeys.all })
    },
  })
}

/**
 * Take a dinner off the plan, suggested or accepted. Its unpurchased grocery
 * items come off the list with it.
 */
export function useRemovePlanEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (entryId: string) =>
      apiClient<RemoveEntryResponse>(`/plan/entries/${encodeURIComponent(entryId)}`, {
        method: 'DELETE',
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: planKeys.all })
      queryClient.invalidateQueries({ queryKey: groceryKeys.all })
    },
  })
}

export function useSwapEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (entryId: string) =>
      apiClient<SwapEntryResponse>(
        `/plan/entries/${encodeURIComponent(entryId)}/swap`,
        { method: 'POST' }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: planKeys.all })
    },
  })
}

/**
 * Replace every suggested dinner of a week with a different suggestion.
 * Accepted dinners stay; with `fromDate`, so do suggestions on earlier days.
 */
export function useRemixWeek() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ weekStart, fromDate }: { weekStart: string; fromDate?: string }) =>
      apiClient<RemixWeekResponse>('/plan/week/remix', {
        method: 'POST',
        body: JSON.stringify({ week_start: weekStart, ...(fromDate ? { from_date: fromDate } : {}) }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: planKeys.all })
    },
  })
}

/**
 * Create a single meal plan entry.
 *
 * Posts to POST /plan/entries. The caller is responsible for surfacing
 * success/failure (success → page banner; failure → sheet error).
 * On success the plan entries cache is invalidated so the Plan page
 * reflects the new entry without a manual refresh.
 */
export function useCreatePlanEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (request: CreateEntryRequest) => {
      return apiClient<MealPlanEntry>('/plan/entries', {
        method: 'POST',
        body: JSON.stringify(request),
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: planKeys.entries() })
    },
  })
}
