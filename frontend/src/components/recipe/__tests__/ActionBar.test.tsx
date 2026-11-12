import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import ActionBar from '../ActionBar'

vi.mock('../../../api/hooks/useGrocery', () => ({
  useCreateGroceryItem: () => ({ mutateAsync: vi.fn() }),
  useGroceryList: () => ({ data: [], refetch: vi.fn().mockResolvedValue({ data: [] }) }),
}))

let queryClient: QueryClient

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
}

function renderBar(props: Partial<React.ComponentProps<typeof ActionBar>> = {}) {
  return render(
    <ActionBar
      onCookThis={vi.fn().mockResolvedValue(undefined)}
      onAddToPlan={vi.fn()}
      {...props}
    />,
    { wrapper }
  )
}

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
})

describe('ActionBar', () => {
  it('renders "I cooked this" button', () => {
    renderBar()
    expect(screen.getByRole('button', { name: /i cooked this/i })).toBeInTheDocument()
  })

  it('renders "Add to plan" button', () => {
    renderBar()
    expect(screen.getByRole('button', { name: /add to plan/i })).toBeInTheDocument()
  })

  it('does not render heart or bookmark buttons', () => {
    renderBar()
    expect(screen.queryByRole('button', { name: /bookmark/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /like/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /heart/i })).not.toBeInTheDocument()
  })

  it('calls onCookThis when "I cooked this" is clicked', async () => {
    const onCookThis = vi.fn().mockResolvedValue(undefined)
    renderBar({ onCookThis })
    await userEvent.click(screen.getByRole('button', { name: /i cooked this/i }))
    await waitFor(() => expect(onCookThis).toHaveBeenCalledTimes(1))
  })

  describe('cook success state', () => {
    // shouldAdvanceTime keeps React Query's internal timers moving; a fully frozen
    // clock stalled the click and the test hit vitest's 5 s limit.
    beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }) })
    afterEach(() => { vi.useRealTimers() })

    it('shows "Cooked!" for 2s after a successful cook', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime.bind(vi) })
      const onCookThis = vi.fn().mockResolvedValue(undefined)
      renderBar({ onCookThis })

      await user.click(screen.getByRole('button', { name: /i cooked this/i }))
      expect(screen.getByText('Cooked!')).toBeInTheDocument()

      // waitFor polls with the (faked) timers and never advances; step the clock
      // inside act and assert synchronously instead.
      await act(async () => {
        vi.advanceTimersByTime(2001)
      })
      expect(screen.getByRole('button', { name: /i cooked this/i })).toBeInTheDocument()
    })
  })

  it('calls onAddToPlan when "Add to plan" is clicked', async () => {
    const onAddToPlan = vi.fn()
    renderBar({ onAddToPlan })
    await userEvent.click(screen.getByRole('button', { name: /add to plan/i }))
    expect(onAddToPlan).toHaveBeenCalledTimes(1)
  })

  it('renders shopping cart glyph button', () => {
    renderBar()
    expect(screen.getByRole('button', { name: /all ingredients in stock/i })).toBeInTheDocument()
  })
})
