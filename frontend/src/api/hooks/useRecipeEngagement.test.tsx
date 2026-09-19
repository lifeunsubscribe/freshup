import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'

import {
  useMyRecipeRelation,
  useMyRecipeRelations,
  useToggleBookmark,
  useToggleLike,
  relationKeys,
} from './useRecipeEngagement'
import { apiClient, ApiException } from '../client'

vi.mock('../client', async () => {
  const actual = await vi.importActual<typeof import('../client')>('../client')
  return { ...actual, apiClient: vi.fn() }
})

const mockApiClient = vi.mocked(apiClient)

const RECIPE_ID = 'recipe-1'

function makeRelation(overrides: Record<string, unknown> = {}) {
  return {
    id: 'rel-1',
    user_id: 'user-1',
    recipe_id: RECIPE_ID,
    rating: null,
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
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
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

describe('useMyRecipeRelation', () => {
  it('returns the relation when one exists', async () => {
    mockApiClient.mockResolvedValueOnce(makeRelation({ is_liked: true }))

    const { result } = renderHook(() => useMyRecipeRelation(RECIPE_ID), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.is_liked).toBe(true)
  })

  it('normalizes a 404 into a neutral relation rather than an error', async () => {
    // The backend answers 404 when the user has never engaged with the recipe.
    // Callers should get a usable shape, not an error state.
    mockApiClient.mockRejectedValueOnce(new ApiException('Rating not found', 404))

    const { result } = renderHook(() => useMyRecipeRelation(RECIPE_ID), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toMatchObject({ is_bookmarked: false, is_liked: false })
  })

  it('still surfaces non-404 errors', async () => {
    mockApiClient.mockRejectedValueOnce(new ApiException('Server error', 500))

    const { result } = renderHook(
      () => useMyRecipeRelation(RECIPE_ID, { retry: false }),
      { wrapper }
    )

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe('useMyRecipeRelations', () => {
  it('indexes the relation list by recipe_id', async () => {
    mockApiClient.mockResolvedValueOnce([
      makeRelation({ recipe_id: 'a', is_bookmarked: true }),
      makeRelation({ recipe_id: 'b', is_liked: true }),
    ])

    const { result } = renderHook(() => useMyRecipeRelations(), { wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data?.get('a')?.is_bookmarked).toBe(true)
    expect(result.current.data?.get('b')?.is_liked).toBe(true)
    expect(result.current.data?.get('missing')).toBeUndefined()
  })

  it('fetches once for a whole grid of cards', async () => {
    mockApiClient.mockResolvedValue([])

    // Three cards mounting simultaneously subscribe to the same query.
    const { result } = renderHook(
      () => [useMyRecipeRelations(), useMyRecipeRelations(), useMyRecipeRelations()],
      { wrapper }
    )

    await waitFor(() => expect(result.current[0].isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledTimes(1)
  })
})

describe('useToggleBookmark', () => {
  it('POSTs when bookmarking and DELETEs when clearing', async () => {
    mockApiClient.mockResolvedValue(makeRelation({ is_bookmarked: true }))

    const { result } = renderHook(() => useToggleBookmark(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ recipeId: RECIPE_ID, next: true })
    })
    expect(mockApiClient).toHaveBeenLastCalledWith(
      `/recipes/${RECIPE_ID}/bookmark`,
      expect.objectContaining({ method: 'POST' })
    )

    await act(async () => {
      await result.current.mutateAsync({ recipeId: RECIPE_ID, next: false })
    })
    expect(mockApiClient).toHaveBeenLastCalledWith(
      `/recipes/${RECIPE_ID}/bookmark`,
      expect.objectContaining({ method: 'DELETE' })
    )
  })

  it('sends a menu assignment when one is given', async () => {
    mockApiClient.mockResolvedValue(makeRelation({ is_bookmarked: true }))

    const { result } = renderHook(() => useToggleBookmark(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({
        recipeId: RECIPE_ID,
        next: true,
        menuId: 'menu-9',
      })
    })

    expect(mockApiClient).toHaveBeenLastCalledWith(
      `/recipes/${RECIPE_ID}/bookmark`,
      expect.objectContaining({ body: JSON.stringify({ menu_id: 'menu-9' }) })
    )
  })

  it('updates the shared relation map optimistically', async () => {
    queryClient.setQueryData(relationKeys.mine, new Map())
    let resolveRequest: (v: unknown) => void = () => {}
    mockApiClient.mockImplementation(
      () => new Promise((resolve) => { resolveRequest = resolve })
    )

    const { result } = renderHook(() => useToggleBookmark(), { wrapper })

    act(() => {
      result.current.mutate({ recipeId: RECIPE_ID, next: true })
    })

    // Before the request resolves, the card should already read as bookmarked.
    await waitFor(() => {
      const map = queryClient.getQueryData<Map<string, { is_bookmarked: boolean }>>(
        relationKeys.mine
      )
      expect(map?.get(RECIPE_ID)?.is_bookmarked).toBe(true)
    })

    await act(async () => {
      resolveRequest(makeRelation({ is_bookmarked: true }))
    })
  })

  it('rolls the optimistic update back when the request fails', async () => {
    queryClient.setQueryData(
      relationKeys.mine,
      new Map([[RECIPE_ID, makeRelation({ is_bookmarked: false })]])
    )
    mockApiClient.mockRejectedValue(new ApiException('boom', 500))

    const { result } = renderHook(() => useToggleBookmark(), { wrapper })

    await act(async () => {
      await result.current
        .mutateAsync({ recipeId: RECIPE_ID, next: true })
        .catch(() => undefined)
    })

    const map = queryClient.getQueryData<Map<string, { is_bookmarked: boolean }>>(
      relationKeys.mine
    )
    expect(map?.get(RECIPE_ID)?.is_bookmarked).toBe(false)
  })
})

describe('useToggleLike', () => {
  it('hits the like endpoint, not rate', async () => {
    mockApiClient.mockResolvedValue(makeRelation({ is_liked: true }))

    const { result } = renderHook(() => useToggleLike(), { wrapper })

    await act(async () => {
      await result.current.mutateAsync({ recipeId: RECIPE_ID, next: true })
    })

    expect(mockApiClient).toHaveBeenLastCalledWith(
      `/recipes/${RECIPE_ID}/like`,
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('leaves the bookmark flag alone while toggling like', async () => {
    // The whole reason these hooks avoid POST /rate: that endpoint is a
    // whole-relation upsert and would clear is_bookmarked.
    queryClient.setQueryData(
      relationKeys.mine,
      new Map([[RECIPE_ID, makeRelation({ is_bookmarked: true, rating: 4 })]])
    )
    let resolveRequest: (v: unknown) => void = () => {}
    mockApiClient.mockImplementation(
      () => new Promise((resolve) => { resolveRequest = resolve })
    )

    const { result } = renderHook(() => useToggleLike(), { wrapper })

    act(() => {
      result.current.mutate({ recipeId: RECIPE_ID, next: true })
    })

    await waitFor(() => {
      const entry = queryClient
        .getQueryData<Map<string, ReturnType<typeof makeRelation>>>(relationKeys.mine)
        ?.get(RECIPE_ID)
      expect(entry?.is_liked).toBe(true)
      expect(entry?.is_bookmarked).toBe(true)
      expect(entry?.rating).toBe(4)
    })

    await act(async () => {
      resolveRequest(makeRelation({ is_liked: true, is_bookmarked: true, rating: 4 }))
    })
  })
})
