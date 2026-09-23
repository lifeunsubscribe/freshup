import type { ReactElement, ReactNode } from 'react'
import { render, type RenderOptions, type RenderResult } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

/**
 * Render a component with the providers the app always has around it.
 *
 * Most components here reach for React Query somewhere — BottomNav reads the
 * grocery count for its badge, ReadyToEat lists prepared foods — and a test
 * that wraps only in a Router fails with "No QueryClient set" the moment that
 * happens. Since a component can gain a hook long after its test was written,
 * default to supplying both rather than adding providers one failure at a time.
 *
 * Tests that want to control the data still mock the api module; this only
 * guarantees the surrounding context exists.
 */

export interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  /** Initial history entry, for components that read the current route. */
  route?: string
  /** Supply your own client to seed cache state or assert on it. */
  queryClient?: QueryClient
}

/**
 * A QueryClient tuned for tests: no retries (a failing request should surface
 * immediately rather than after backoff) and no caching between tests.
 */
export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  })
}

export function renderWithProviders(
  ui: ReactElement,
  { route = '/', queryClient, ...renderOptions }: RenderWithProvidersOptions = {}
): RenderResult & { queryClient: QueryClient } {
  const client = queryClient ?? createTestQueryClient()

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
      </QueryClientProvider>
    )
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    queryClient: client,
  }
}
