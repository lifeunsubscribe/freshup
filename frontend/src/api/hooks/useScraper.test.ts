import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import type { ReactNode } from 'react'

// Mock apiClient and related helpers before importing the hooks.
// vi.mock is hoisted above every import, and the hooks import runs the
// factory, so anything the factory references must be hoisted with it or
// it is read before initialisation and the whole suite fails to load.
const { mockApiClient, mockGetAuthToken, mockGetApiBaseUrl, MockApiException } = vi.hoisted(() => {
  class MockApiException extends Error {
    status: number
    detail?: string
    constructor(message: string, status: number, detail?: string) {
      super(message)
      this.name = 'ApiException'
      this.status = status
      this.detail = detail
    }
  }
  return {
    mockApiClient: vi.fn(),
    mockGetAuthToken: vi.fn(() => 'test-token'),
    mockGetApiBaseUrl: vi.fn(() => 'http://localhost:8000'),
    MockApiException,
  }
})

vi.mock('../client', () => ({
  apiClient: mockApiClient,
  getAuthToken: mockGetAuthToken,
  getApiBaseUrl: mockGetApiBaseUrl,
  ApiException: MockApiException,
}))

vi.mock('./useRecipes', () => ({
  recipeKeys: {
    all: ['recipes'] as const,
    lists: () => ['recipes', 'list'] as const,
  },
}))

// Import after mocks are in place.
import { useImportUrl, useImportHtml } from './useScraper'

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client }, children)
  }
}

function makeWrapperWithSpy() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
  return {
    wrapper: function Wrapper({ children }: { children: ReactNode }) {
      return createElement(QueryClientProvider, { client }, children)
    },
    invalidateSpy,
  }
}

describe('useImportUrl', () => {
  beforeEach(() => {
    mockApiClient.mockReset()
  })

  it('POSTs to /scraper/import-url with the url in the JSON body', async () => {
    mockApiClient.mockResolvedValueOnce({ status: 'success', recipe_id: 'r1', warnings: [] })

    const { result } = renderHook(() => useImportUrl(), { wrapper: makeWrapper() })

    await act(async () => {
      result.current.mutate({ url: 'https://www.hellofresh.com/recipes/test-123' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApiClient).toHaveBeenCalledWith(
      '/scraper/import-url',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ url: 'https://www.hellofresh.com/recipes/test-123' }),
      })
    )
  })

  it('returns the ImportResult on success', async () => {
    const importResult = { status: 'success' as const, recipe_id: 'abc', warnings: ['Salt'] }
    mockApiClient.mockResolvedValueOnce(importResult)

    const { result } = renderHook(() => useImportUrl(), { wrapper: makeWrapper() })

    await act(async () => {
      result.current.mutate({ url: 'https://www.hellofresh.com/recipes/x' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(importResult)
  })

  it('surfaces the error on API failure', async () => {
    mockApiClient.mockRejectedValueOnce(new MockApiException('timeout', 504))

    const { result } = renderHook(() => useImportUrl(), { wrapper: makeWrapper() })

    await act(async () => {
      result.current.mutate({ url: 'https://www.hellofresh.com/recipes/x' })
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe('useImportHtml – paste path', () => {
  beforeEach(() => {
    mockApiClient.mockReset()
  })

  it('POSTs JSON with html and source_url for pasted text', async () => {
    mockApiClient.mockResolvedValueOnce({ status: 'success', recipe_id: 'r2', warnings: [] })

    const { result } = renderHook(() => useImportHtml(), { wrapper: makeWrapper() })

    await act(async () => {
      result.current.mutate({
        html: '<html><body>recipe</body></html>',
        source_url: 'https://www.kitchensanctuary.com/recipe',
      })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(mockApiClient).toHaveBeenCalledWith(
      '/scraper/import-html',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          html: '<html><body>recipe</body></html>',
          source_url: 'https://www.kitchensanctuary.com/recipe',
        }),
      })
    )
  })

  it('the paste body includes source_url', async () => {
    mockApiClient.mockResolvedValueOnce({ status: 'success', recipe_id: 'r3', warnings: [] })

    const { result } = renderHook(() => useImportHtml(), { wrapper: makeWrapper() })
    const sourceUrl = 'https://www.kitchensanctuary.com/crispy-sesame-chicken'

    await act(async () => {
      result.current.mutate({ html: '<p>content</p>', source_url: sourceUrl })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const bodyArg = JSON.parse(
      (mockApiClient.mock.calls[0][1] as { body: string }).body
    )
    expect(bodyArg.source_url).toBe(sourceUrl)
  })
})

describe('useImportHtml – file upload path', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    // Earlier blocks call apiClient; the "not called" assertion below needs a clean slate.
    mockApiClient.mockReset()
    // For the file path the hook bypasses apiClient and uses fetch directly.
    fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ status: 'success', recipe_id: 'r4', warnings: [] }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    )
  })

  afterEach(() => {
    fetchSpy.mockRestore()
  })

  it('POSTs multipart/form-data for a File upload', async () => {
    const file = new File(['<html>content</html>'], 'recipe.html', { type: 'text/html' })

    const { result } = renderHook(() => useImportHtml(), { wrapper: makeWrapper() })

    await act(async () => {
      result.current.mutate({
        file,
        source_url: 'https://www.kitchensanctuary.com/recipe',
      })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(fetchSpy).toHaveBeenCalledOnce()
    const [url, init] = fetchSpy.mock.calls[0]
    expect(url).toBe('http://localhost:8000/scraper/import-html')
    expect((init as RequestInit).method).toBe('POST')
    // Body must be FormData, not a JSON string.
    expect((init as RequestInit).body).toBeInstanceOf(FormData)
  })

  it('includes source_url in the FormData payload', async () => {
    const file = new File(['<html>content</html>'], 'recipe.html', { type: 'text/html' })
    const sourceUrl = 'https://www.kitchensanctuary.com/crispy-sesame'

    const { result } = renderHook(() => useImportHtml(), { wrapper: makeWrapper() })

    await act(async () => {
      result.current.mutate({ file, source_url: sourceUrl })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const fd = (fetchSpy.mock.calls[0][1] as RequestInit).body as FormData
    expect(fd.get('source_url')).toBe(sourceUrl)
    expect(fd.get('file')).toBe(file)
  })

  it('attaches the Bearer token to the request headers', async () => {
    const file = new File(['content'], 'recipe.html', { type: 'text/html' })

    const { result } = renderHook(() => useImportHtml(), { wrapper: makeWrapper() })

    await act(async () => {
      result.current.mutate({ file, source_url: 'https://www.kitchensanctuary.com/r' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    const headers = (fetchSpy.mock.calls[0][1] as RequestInit).headers as Record<string, string>
    expect(headers['Authorization']).toBe('Bearer test-token')
  })

  it('does NOT use apiClient for file uploads', async () => {
    const file = new File(['content'], 'recipe.html', { type: 'text/html' })

    const { result } = renderHook(() => useImportHtml(), { wrapper: makeWrapper() })

    await act(async () => {
      result.current.mutate({ file, source_url: 'https://www.kitchensanctuary.com/r' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    // apiClient must not have been called for the file path
    expect(mockApiClient).not.toHaveBeenCalled()
  })
})

describe('invalidation behaviour', () => {
  beforeEach(() => {
    mockApiClient.mockReset()
  })

  it('invalidates recipe lists on status:success', async () => {
    mockApiClient.mockResolvedValueOnce({ status: 'success', recipe_id: 'r1', warnings: [] })
    const { wrapper, invalidateSpy } = makeWrapperWithSpy()
    const { result } = renderHook(() => useImportUrl(), { wrapper })

    await act(async () => { result.current.mutate({ url: 'https://example.com/recipe' }) })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ['recipes', 'list'] }))
  })

  it('invalidates recipe lists on status:duplicate', async () => {
    mockApiClient.mockResolvedValueOnce({ status: 'duplicate', recipe_id: 'r2' })
    const { wrapper, invalidateSpy } = makeWrapperWithSpy()
    const { result } = renderHook(() => useImportUrl(), { wrapper })

    await act(async () => { result.current.mutate({ url: 'https://example.com/recipe' }) })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ['recipes', 'list'] }))
  })

  it('does not invalidate recipe lists on status:error (URL path)', async () => {
    mockApiClient.mockResolvedValueOnce({ status: 'error', message: 'The page timed out.' })
    const { wrapper, invalidateSpy } = makeWrapperWithSpy()
    const { result } = renderHook(() => useImportUrl(), { wrapper })

    await act(async () => { result.current.mutate({ url: 'https://example.com/recipe' }) })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).not.toHaveBeenCalled()
  })

  it('does not invalidate recipe lists on status:error (HTML paste path)', async () => {
    mockApiClient.mockResolvedValueOnce({ status: 'error', message: 'No recipe found.' })
    const { wrapper, invalidateSpy } = makeWrapperWithSpy()
    const { result } = renderHook(() => useImportHtml(), { wrapper })

    await act(async () => {
      result.current.mutate({ html: '<html>content</html>', source_url: 'https://www.kitchensanctuary.com/r' })
    })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))

    expect(invalidateSpy).not.toHaveBeenCalled()
  })
})
