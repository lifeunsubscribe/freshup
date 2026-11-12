import { useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../client'
import type { CreateEntryRequest, MealPlanEntry } from '../types'

export const planKeys = {
  all: ['plan'] as const,
  entries: () => [...planKeys.all, 'entries'] as const,
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
