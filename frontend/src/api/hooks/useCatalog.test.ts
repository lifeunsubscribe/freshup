import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import type { ReactNode } from 'react'
import { apiClient } from '../client'
import { useCollections, useCollection, useOpenCard, catalogKeys } from './useCatalog'

vi.mock('../client', async () => {
  const actual = await vi.importActual<typeof import('../client')>('../client')
  return { ...actual, apiClient: vi.fn() }
})

vi.mock('./useRecipes', async () => {
  const actual = await vi.importActual<typeof import('./useRecipes')>('./useRecipes')
  return {
    ...actual,
    recipeKeys: {
      all: ['recipes'] as const,
      details: () => ['recipes', 'detail'] as const,
      detail: (id: string) => ['recipes', 'detail', id] as const,
    },
  }
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

function makeWrapperWithClient() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return {
    wrapper: function Wrapper({ children }: { children: ReactNode }) {
      return createElement(QueryClientProvider, { client }, children)
    },
    client,
  }
}

const stubCollection = {
  slug: 'mains',
  name: 'Mains',
  source_type: 'hellofresh_web',
  last_fetched_at: null,
  children: [],
  cards: [],
  fetch_error: null,
}

const stubRecipe = {
  id: 'r1',
  name: 'Test Recipe',
  source_type: 'hellofresh_card',
  source_url: null,
  source_image: null,
  steps: [],
  created_by: null,
  notes: null,
  tags: [],
  cook_time_minutes: null,
  prep_time_minutes: null,
  base_servings: 2,
  times_cooked: 0,
  is_persisted: false,
  variation_groups: null,
  nutritional_info: null,
  ingredients: [],
}

describe('useCollections', () => {
  beforeEach(() => { mockApiClient.mockReset() })

  it('hits the endpoint once for two mounted consumers (dedupe + staleTime)', async () => {
    const data = [{ slug: 'mains', name: 'Mains', card_count: 10, last_fetched_at: null }]
    mockApiClient.mockResolvedValue(data)

    // Both hooks share the same QueryClient via the same wrapper closure.
    const wrapper = makeWrapper()
    renderHook(
      () => ({
        a: useCollections('hellofresh_web'),
        b: useCollections('hellofresh_web'),
      }),
      { wrapper }
    )

    await waitFor(() => expect(mockApiClient).toHaveBeenCalledTimes(1))
    expect(mockApiClient).toHaveBeenCalledWith(
      '/catalog/hellofresh_web/collections',
      expect.objectContaining({ method: 'GET' })
    )
  })

  it('returns the collection list data', async () => {
    const data = [{ slug: 'mains', name: 'Mains', card_count: 5, last_fetched_at: null }]
    mockApiClient.mockResolvedValueOnce(data)

    const { result } = renderHook(() => useCollections('hellofresh_web'), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(data)
  })
})

describe('useCollection', () => {
  beforeEach(() => { mockApiClient.mockReset() })

  it('makes no request when enabled is false', () => {
    renderHook(
      () => useCollection('hellofresh_web', 'mains', { enabled: false }),
      { wrapper: makeWrapper() }
    )
    expect(mockApiClient).not.toHaveBeenCalled()
  })

  it('appends ?fresh=true to the URL when opts.fresh is true', async () => {
    mockApiClient.mockResolvedValueOnce(stubCollection)

    const { result } = renderHook(
      () => useCollection('hellofresh_web', 'mains', { fresh: true }),
      { wrapper: makeWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith(
      '/catalog/hellofresh_web/collections/mains?fresh=true',
      expect.objectContaining({ method: 'GET' })
    )
  })

  it('appends ?fresh=false to the URL when opts.fresh is false', async () => {
    mockApiClient.mockResolvedValueOnce(stubCollection)

    const { result } = renderHook(
      () => useCollection('hellofresh_web', 'mains', { fresh: false }),
      { wrapper: makeWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith(
      '/catalog/hellofresh_web/collections/mains?fresh=false',
      expect.objectContaining({ method: 'GET' })
    )
  })

  it('omits the query string when opts.fresh is not set', async () => {
    mockApiClient.mockResolvedValueOnce(stubCollection)

    const { result } = renderHook(
      () => useCollection('hellofresh_web', 'mains'),
      { wrapper: makeWrapper() }
    )

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith(
      '/catalog/hellofresh_web/collections/mains',
      expect.objectContaining({ method: 'GET' })
    )
  })

  it('issues a new request when fresh toggles from false to true (cache miss on key change)', async () => {
    mockApiClient.mockResolvedValue(stubCollection)

    const { rerender } = renderHook(
      (props: { fresh?: boolean }) => useCollection('hellofresh_web', 'mains', props),
      { wrapper: makeWrapper(), initialProps: { fresh: false } }
    )

    await waitFor(() => expect(mockApiClient).toHaveBeenCalledTimes(1))
    rerender({ fresh: true })
    await waitFor(() => expect(mockApiClient).toHaveBeenCalledTimes(2))
  })
})

describe('useOpenCard', () => {
  beforeEach(() => { mockApiClient.mockReset() })

  it('POSTs to /catalog/cards/{cardId}/open', async () => {
    mockApiClient.mockResolvedValueOnce(stubRecipe)

    const { result } = renderHook(() => useOpenCard(), { wrapper: makeWrapper() })

    await act(async () => {
      result.current.mutate({ cardId: 'card-1', source: 'hellofresh_web', collectionSlug: 'mains' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith(
      '/catalog/cards/card-1/open',
      expect.objectContaining({ method: 'POST' })
    )
  })

  it('seeds the recipe detail cache on success', async () => {
    mockApiClient.mockResolvedValueOnce(stubRecipe)

    const { wrapper, client } = makeWrapperWithClient()
    const { result } = renderHook(() => useOpenCard(), { wrapper })

    await act(async () => {
      result.current.mutate({ cardId: 'card-1', source: 'hellofresh_web', collectionSlug: 'mains' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(client.getQueryData(['recipes', 'detail', 'r1'])).toEqual(stubRecipe)
  })

  it('invalidates catalogKeys.collection(source, slug) on success', async () => {
    mockApiClient.mockResolvedValueOnce(stubRecipe)

    const { wrapper, client } = makeWrapperWithClient()
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
    const { result } = renderHook(() => useOpenCard(), { wrapper })

    await act(async () => {
      result.current.mutate({ cardId: 'card-1', source: 'hellofresh_web', collectionSlug: 'mains' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: catalogKeys.collection('hellofresh_web', 'mains') })
    )
  })
})
