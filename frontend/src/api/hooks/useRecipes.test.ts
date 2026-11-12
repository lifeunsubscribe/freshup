import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import type { ReactNode } from 'react'
import { apiClient } from '../client'
import { useRateRecipe } from './useRecipes'
import type { UserRecipeRelationResponse } from '../types'

vi.mock('../client', async () => {
  const actual = await vi.importActual<typeof import('../client')>('../client')
  return { ...actual, apiClient: vi.fn() }
})

const mockApiClient = vi.mocked(apiClient)

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client }, children)
  }
}

const baseRelation: UserRecipeRelationResponse = {
  id: 'rel-1',
  user_id: 'user-1',
  recipe_id: 'recipe-1',
  rating: null,
  is_bookmarked: true,
  is_liked: true,
  rating_photos: null,
  rating_comment: 'great',
  menu_id: 'menu-42',
}

describe('useRateRecipe — merged relation body', () => {
  beforeEach(() => { mockApiClient.mockReset() })

  it('sends the full relation body including is_bookmarked and is_liked', async () => {
    const response: UserRecipeRelationResponse = { ...baseRelation, rating: 4 }
    mockApiClient.mockResolvedValueOnce(response)

    const { result } = renderHook(() => useRateRecipe(), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.mutateAsync({
        recipeId: 'recipe-1',
        rating: 4,
        currentRelation: baseRelation,
      })
    })

    expect(mockApiClient).toHaveBeenCalledWith(
      '/recipes/recipe-1/rate',
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"is_bookmarked":true'),
      })
    )
    expect(mockApiClient).toHaveBeenCalledWith(
      '/recipes/recipe-1/rate',
      expect.objectContaining({
        body: expect.stringContaining('"is_liked":true'),
      })
    )
  })

  it('sends the new rating value in the body', async () => {
    mockApiClient.mockResolvedValueOnce({ ...baseRelation, rating: 3 })

    const { result } = renderHook(() => useRateRecipe(), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.mutateAsync({
        recipeId: 'recipe-1',
        rating: 3,
        currentRelation: baseRelation,
      })
    })

    const callBody = JSON.parse(
      (mockApiClient.mock.calls[0][1] as { body: string }).body
    )
    expect(callBody.rating).toBe(3)
  })

  it('preserves rating_comment and menu_id from the current relation', async () => {
    mockApiClient.mockResolvedValueOnce({ ...baseRelation, rating: 5 })

    const { result } = renderHook(() => useRateRecipe(), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.mutateAsync({
        recipeId: 'recipe-1',
        rating: 5,
        currentRelation: baseRelation,
      })
    })

    const callBody = JSON.parse(
      (mockApiClient.mock.calls[0][1] as { body: string }).body
    )
    expect(callBody.rating_comment).toBe('great')
    expect(callBody.menu_id).toBe('menu-42')
  })

  it('works when currentRelation has falsy engagement (EMPTY_RELATION-like)', async () => {
    const emptyRelation = {
      is_bookmarked: false,
      is_liked: false,
      rating_photos: null,
      rating_comment: null,
      menu_id: null,
    }
    mockApiClient.mockResolvedValueOnce({ ...baseRelation, rating: 2, ...emptyRelation })

    const { result } = renderHook(() => useRateRecipe(), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.mutateAsync({
        recipeId: 'recipe-1',
        rating: 2,
        currentRelation: emptyRelation,
      })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const callBody = JSON.parse(
      (mockApiClient.mock.calls[0][1] as { body: string }).body
    )
    expect(callBody.rating).toBe(2)
    expect(callBody.is_bookmarked).toBe(false)
    expect(callBody.is_liked).toBe(false)
  })
})
