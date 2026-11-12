import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { createElement } from 'react'
import { useRateRecipe, recipeKeys } from './useRecipes'
import { useCookRecipe } from './useRecipeEngagement'
import { apiClient } from '../client'

vi.mock('../client', async () => {
  const actual = await vi.importActual<typeof import('../client')>('../client')
  return { ...actual, apiClient: vi.fn() }
})

const mockApiClient = vi.mocked(apiClient)

const RECIPE_ID = 'recipe-1'

function makeRelationResponse(overrides: Record<string, unknown> = {}) {
  return {
    id: 'rel-1',
    user_id: 'user-1',
    recipe_id: RECIPE_ID,
    rating: 4,
    is_bookmarked: false,
    is_liked: false,
    rating_photos: null,
    rating_comment: null,
    menu_id: null,
    ...overrides,
  }
}

let queryClient: QueryClient

function wrapper({ children }: { children: ReactNode }) {
  return createElement(QueryClientProvider, { client: queryClient }, children)
}

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  mockApiClient.mockReset()
})

afterEach(() => {
  queryClient.clear()
})

describe('useRateRecipe', () => {
  it('sends the new rating merged with the current relation fields', async () => {
    mockApiClient.mockResolvedValueOnce(makeRelationResponse({ rating: 3 }))

    const { result } = renderHook(() => useRateRecipe(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        recipeId: RECIPE_ID,
        rating: 3,
        currentRelation: {
          is_bookmarked: true,
          is_liked: false,
          rating_photos: ['photo.jpg'],
          rating_comment: 'Great!',
          menu_id: 'menu-1',
        },
      })
    })

    expect(mockApiClient).toHaveBeenCalledWith(
      `/recipes/${RECIPE_ID}/rate`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          rating: 3,
          is_bookmarked: true,
          is_liked: false,
          rating_photos: ['photo.jpg'],
          rating_comment: 'Great!',
          menu_id: 'menu-1',
        }),
      })
    )
  })

  it('preserves is_bookmarked=true so a bookmarked recipe stays bookmarked', async () => {
    mockApiClient.mockResolvedValueOnce(makeRelationResponse({ is_bookmarked: true }))

    const { result } = renderHook(() => useRateRecipe(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        recipeId: RECIPE_ID,
        rating: 5,
        currentRelation: {
          is_bookmarked: true,
          is_liked: true,
          rating_photos: null,
          rating_comment: null,
          menu_id: null,
        },
      })
    })

    const sentBody = JSON.parse(
      (mockApiClient.mock.calls[0][1] as { body: string }).body
    )
    expect(sentBody.is_bookmarked).toBe(true)
    expect(sentBody.is_liked).toBe(true)
    expect(sentBody.rating).toBe(5)
  })

  it('sends null rating_photos when the current relation has none', async () => {
    mockApiClient.mockResolvedValueOnce(makeRelationResponse())

    const { result } = renderHook(() => useRateRecipe(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        recipeId: RECIPE_ID,
        rating: 2,
        currentRelation: {
          is_bookmarked: false,
          is_liked: false,
          rating_photos: null,
          rating_comment: null,
          menu_id: null,
        },
      })
    })

    const sentBody = JSON.parse(
      (mockApiClient.mock.calls[0][1] as { body: string }).body
    )
    expect(sentBody.rating_photos).toBeNull()
    expect(sentBody.rating_comment).toBeNull()
  })

  it('invalidates myRating and ratings cache keys on success', async () => {
    mockApiClient.mockResolvedValueOnce(makeRelationResponse())
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useRateRecipe(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        recipeId: RECIPE_ID,
        rating: 4,
        currentRelation: {
          is_bookmarked: false,
          is_liked: false,
          rating_photos: null,
          rating_comment: null,
          menu_id: null,
        },
      })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const invalidatedKeys = invalidateSpy.mock.calls.map(
      (call) => (call[0] as { queryKey: unknown[] }).queryKey
    )
    expect(
      invalidatedKeys.some((k) => JSON.stringify(k).includes('my-rating'))
    ).toBe(true)
    expect(
      invalidatedKeys.some((k) => JSON.stringify(k).includes('ratings'))
    ).toBe(true)
  })

  it('invalidates outcomes cache key on success', async () => {
    mockApiClient.mockResolvedValueOnce(makeRelationResponse())
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useRateRecipe(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        recipeId: RECIPE_ID,
        rating: 3,
        currentRelation: {
          is_bookmarked: false,
          is_liked: false,
          rating_photos: null,
          rating_comment: null,
          menu_id: null,
        },
      })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const invalidatedKeys = invalidateSpy.mock.calls.map(
      (call) => (call[0] as { queryKey: unknown[] }).queryKey
    )
    expect(
      invalidatedKeys.some(
        (k) => JSON.stringify(k) === JSON.stringify(recipeKeys.outcomes(RECIPE_ID))
      )
    ).toBe(true)
  })
})

describe('useCookRecipe outcomes invalidation', () => {
  it('invalidates outcomes cache key after a successful cook', async () => {
    mockApiClient.mockResolvedValueOnce({
      id: 'ev-1',
      user_id: 'user-1',
      recipe_id: RECIPE_ID,
      cooked_at: new Date().toISOString(),
      meal_plan_entry_id: null,
      notes: null,
    })
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries')

    const { result } = renderHook(() => useCookRecipe(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ recipeId: RECIPE_ID })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const invalidatedKeys = invalidateSpy.mock.calls.map(
      (call) => (call[0] as { queryKey: unknown[] }).queryKey
    )
    expect(
      invalidatedKeys.some(
        (k) => JSON.stringify(k) === JSON.stringify(recipeKeys.outcomes(RECIPE_ID))
      )
    ).toBe(true)
  })
})
