import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'
import type { ReactNode } from 'react'
import { apiClient } from '../client'
import { useSourceHealth, failingSources } from './useSourceHealth'
import type { SourceStatus } from '../types'

vi.mock('../client', async () => {
  const actual = await vi.importActual<typeof import('../client')>('../client')
  return { ...actual, apiClient: vi.fn() }
})

const mockApiClient = vi.mocked(apiClient)

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(QueryClientProvider, { client }, children)
  }
}

const threeStatuses: SourceStatus[] = [
  { source_type: 'hellofresh_web', status: 'healthy', checked_at: '2026-11-10T08:00:00Z', failing_since: null, detail: null, import_mode: 'link' },
  { source_type: 'kitchen_sanctuary', status: 'failing', checked_at: '2026-11-10T08:00:00Z', failing_since: '2026-11-09T08:00:00Z', detail: 'Connection timeout', import_mode: 'link' },
  { source_type: 'allrecipes', status: 'never_checked', checked_at: null, failing_since: null, detail: null, import_mode: null },
]

describe('useSourceHealth', () => {
  beforeEach(() => { mockApiClient.mockReset() })

  it('fetches from /sources/health', async () => {
    mockApiClient.mockResolvedValueOnce(threeStatuses)

    const { result } = renderHook(() => useSourceHealth(), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockApiClient).toHaveBeenCalledWith(
      '/sources/health',
      expect.objectContaining({ method: 'GET' })
    )
  })

  it('returns all three statuses from the mocked response', async () => {
    mockApiClient.mockResolvedValueOnce(threeStatuses)

    const { result } = renderHook(() => useSourceHealth(), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(threeStatuses)
  })

  it('surfaces the error when the API call fails', async () => {
    mockApiClient.mockRejectedValueOnce(new Error('network error'))

    const { result } = renderHook(() => useSourceHealth(), { wrapper: makeWrapper() })

    await waitFor(() => expect(result.current.isError).toBe(true))
  })
})

describe('failingSources', () => {
  it('filters to sources with status === failing', () => {
    expect(failingSources(threeStatuses)).toEqual([threeStatuses[1]])
  })

  it('returns an empty array when no sources are failing', () => {
    const healthy: SourceStatus[] = [
      { source_type: 'hellofresh_web', status: 'healthy', checked_at: null, failing_since: null, detail: null, import_mode: null },
    ]
    expect(failingSources(healthy)).toEqual([])
  })

  it('returns an empty array for an empty input', () => {
    expect(failingSources([])).toEqual([])
  })

  it('returns all sources when all are failing', () => {
    const allFailing: SourceStatus[] = [
      { source_type: 'a', status: 'failing', checked_at: null, failing_since: null, detail: null, import_mode: null },
      { source_type: 'b', status: 'failing', checked_at: null, failing_since: null, detail: null, import_mode: null },
    ]
    expect(failingSources(allFailing)).toEqual(allFailing)
  })
})
