import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { createElement } from 'react'
import { useCreatePlanEntry, planKeys } from './usePlan'

vi.mock('../client', () => ({
  apiClient: vi.fn().mockResolvedValue({
    id: 'entry-1',
    date: '2026-11-12',
    meal_type: 'dinner',
    recipe_id: 'recipe-1',
    planned_servings: 4,
  }),
}))

describe('useCreatePlanEntry', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
  })

  function wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }

  it('invalidates plan entries cache on success', async () => {
    const spy = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useCreatePlanEntry(), { wrapper })

    await result.current.mutateAsync({
      date: '2026-11-12',
      meal_type: 'dinner',
      recipe_id: 'recipe-1',
      planned_servings: 4,
    })

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ queryKey: planKeys.entries() })
    })
  })

  it('does not invalidate when mutation fails', async () => {
    const { apiClient } = await import('../client')
    vi.mocked(apiClient).mockRejectedValueOnce(new Error('network error'))

    const spy = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useCreatePlanEntry(), { wrapper })

    await expect(
      result.current.mutateAsync({
        date: '2026-11-12',
        meal_type: 'dinner',
        recipe_id: 'recipe-1',
        planned_servings: 4,
      })
    ).rejects.toThrow()

    expect(spy).not.toHaveBeenCalled()
  })
})
