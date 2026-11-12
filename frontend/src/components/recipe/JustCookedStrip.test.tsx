import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import JustCookedStrip from './JustCookedStrip'

function renderStrip(props: Partial<React.ComponentProps<typeof JustCookedStrip>> = {}) {
  return render(
    <JustCookedStrip
      cookCount={8}
      onRate={vi.fn().mockResolvedValue(undefined)}
      onDismiss={vi.fn()}
      {...props}
    />
  )
}

describe('JustCookedStrip', () => {
  it('shows the cook count', () => {
    renderStrip({ cookCount: 5 })
    expect(screen.getByText(/cooked 5 times now/i)).toBeInTheDocument()
  })

  it('renders five star buttons', () => {
    renderStrip()
    const group = screen.getByRole('radiogroup', { name: /rating, 1 to 5/i })
    expect(group.querySelectorAll('[role="radio"]')).toHaveLength(5)
  })

  it('renders "Not now" button', () => {
    renderStrip()
    expect(screen.getByRole('button', { name: /not now/i })).toBeInTheDocument()
  })

  it('"Not now" calls onDismiss without calling onRate', async () => {
    const onRate = vi.fn()
    const onDismiss = vi.fn()
    renderStrip({ onRate, onDismiss })

    await userEvent.click(screen.getByRole('button', { name: /not now/i }))
    expect(onDismiss).toHaveBeenCalledTimes(1)
    expect(onRate).not.toHaveBeenCalled()
  })

  describe('successful rating', () => {
    beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }) })
    afterEach(() => { vi.useRealTimers() })

    it('tapping a star calls onRate with the correct value', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime.bind(vi) })
      const onRate = vi.fn().mockResolvedValue(undefined)
      renderStrip({ onRate })

      await user.click(screen.getByRole('radio', { name: /4 stars/i }))
      await waitFor(() => expect(onRate).toHaveBeenCalledWith(4))
    })

    it('shows "Thanks. Rated N stars." after a successful rating', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime.bind(vi) })
      const onRate = vi.fn().mockResolvedValue(undefined)
      renderStrip({ onRate })

      await user.click(screen.getByRole('radio', { name: /3 stars/i }))
      await waitFor(() => expect(screen.getByText(/thanks\. rated 3 stars/i)).toBeInTheDocument())
    })

    it('calls onDismiss after 2 s following a successful rating', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime.bind(vi) })
      const onRate = vi.fn().mockResolvedValue(undefined)
      const onDismiss = vi.fn()
      renderStrip({ onRate, onDismiss })

      await user.click(screen.getByRole('radio', { name: /2 stars/i }))
      await waitFor(() => expect(screen.getByText(/thanks/i)).toBeInTheDocument())

      await act(async () => { vi.advanceTimersByTime(2001) })
      expect(onDismiss).toHaveBeenCalledTimes(1)
    })
  })

  describe('403 from /rate', () => {
    it('shows the gate sentence in mocha and does not call onDismiss', async () => {
      const gateError = Object.assign(new Error('Rate after cooking'), { status: 403 })
      const onRate = vi.fn().mockRejectedValue(gateError)
      const onDismiss = vi.fn()
      renderStrip({ onRate, onDismiss })

      await userEvent.click(screen.getByRole('radio', { name: /1 star/i }))
      await waitFor(() =>
        expect(
          screen.getByText(/ratings open up after the first cook/i)
        ).toBeInTheDocument()
      )
      expect(onDismiss).not.toHaveBeenCalled()
    })

    it('does not show the star buttons or "Not now" after a 403', async () => {
      const gateError = Object.assign(new Error('Rate after cooking'), { status: 403 })
      const onRate = vi.fn().mockRejectedValue(gateError)
      renderStrip({ onRate })

      await userEvent.click(screen.getByRole('radio', { name: /1 star/i }))
      await waitFor(() =>
        expect(screen.getByText(/ratings open up after the first cook/i)).toBeInTheDocument()
      )
      expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /not now/i })).not.toBeInTheDocument()
    })
  })
})
