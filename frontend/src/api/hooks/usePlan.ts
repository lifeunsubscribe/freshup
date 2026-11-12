import { useMutation } from '@tanstack/react-query'
import { apiClient } from '../client'
import type { CreateEntryRequest, MealPlanEntry } from '../types'

/**
 * Create a single meal plan entry.
 *
 * Posts to POST /plan/entries. The caller is responsible for surfacing
 * success/failure (success → page banner; failure → sheet error).
 */
export function useCreatePlanEntry() {
  return useMutation({
    mutationFn: async (request: CreateEntryRequest) => {
      return apiClient<MealPlanEntry>('/plan/entries', {
        method: 'POST',
        body: JSON.stringify(request),
      })
    },
  })
}
