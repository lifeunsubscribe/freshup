import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { createElement } from 'react'
import {
  useConfirmEntry,
  useCreatePlanEntry,
  useGenerateDraft,
  useRemixWeek,
  useRemovePlanEntry,
  planKeys,
} from './usePlan'
import { groceryKeys } from './useGrocery'

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

describe('useGenerateDraft', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
  })

  function wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children)
  }

  it('asks for a whole week by its first day', async () => {
    const { apiClient } = await import('../client')
    const { result } = renderHook(() => useGenerateDraft(), { wrapper })

    await result.current.mutateAsync('2026-11-15')

    expect(vi.mocked(apiClient)).toHaveBeenLastCalledWith('/plan/draft/generate', {
      method: 'POST',
      body: JSON.stringify({ week_start: '2026-11-15' }),
    })
  })

  it('asks only for days from a date on, and refreshes that week', async () => {
    const { apiClient } = await import('../client')
    const spy = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useGenerateDraft(), { wrapper })

    await result.current.mutateAsync({ weekStart: '2026-11-15', fromDate: '2026-11-18' })

    expect(vi.mocked(apiClient)).toHaveBeenLastCalledWith('/plan/draft/generate', {
      method: 'POST',
      body: JSON.stringify({ week_start: '2026-11-15', from_date: '2026-11-18' }),
    })
    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ queryKey: planKeys.week('2026-11-15') })
    })
  })
})

describe('useRemixWeek', () => {
  it('asks for a week to be remixed from a date on, and refreshes every week', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children)
    const { apiClient } = await import('../client')
    const spy = vi.spyOn(queryClient, 'invalidateQueries')
    const { result } = renderHook(() => useRemixWeek(), { wrapper })

    await result.current.mutateAsync({ weekStart: '2026-11-15', fromDate: '2026-11-18' })

    expect(vi.mocked(apiClient)).toHaveBeenLastCalledWith('/plan/week/remix', {
      method: 'POST',
      body: JSON.stringify({ week_start: '2026-11-15', from_date: '2026-11-18' }),
    })
    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ queryKey: planKeys.all })
    })
  })
})

describe('the grocery list follows the plan', () => {
  function setupClient() {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })
    const wrapper = ({ children }: { children: ReactNode }) =>
      createElement(QueryClientProvider, { client: queryClient }, children)
    return { wrapper, spy: vi.spyOn(queryClient, 'invalidateQueries') }
  }

  it('refreshes the grocery list when a dinner is accepted', async () => {
    const { wrapper, spy } = setupClient()
    const { result } = renderHook(() => useConfirmEntry(), { wrapper })

    await result.current.mutateAsync('entry-1')

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ queryKey: groceryKeys.all })
      expect(spy).toHaveBeenCalledWith({ queryKey: planKeys.all })
    })
  })

  it('removes a dinner and refreshes both the plan and the grocery list', async () => {
    const { apiClient } = await import('../client')
    const { wrapper, spy } = setupClient()
    const { result } = renderHook(() => useRemovePlanEntry(), { wrapper })

    await result.current.mutateAsync('entry-1')

    expect(vi.mocked(apiClient)).toHaveBeenLastCalledWith('/plan/entries/entry-1', { method: 'DELETE' })
    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({ queryKey: groceryKeys.all })
      expect(spy).toHaveBeenCalledWith({ queryKey: planKeys.all })
    })
  })
})
