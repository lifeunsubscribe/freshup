import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import JustCookedStrip from './JustCookedStrip'
import { ApiException } from '../../api/client'

describe('JustCookedStrip', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  it('shows the cook count and five star buttons', () => {
    render(
      <JustCookedStrip
        cookCount={8}
        onRate={vi.fn()}
        onNotNow={vi.fn()}
        onDone={vi.fn()}
      />
    )
    expect(screen.getByText(/cooked 8 times now/i)).toBeInTheDocument()
    const buttons = screen.getByRole('radiogroup').querySelectorAll('button')
    expect(buttons).toHaveLength(5)
  })

  it('"Not now" calls onNotNow without posting a rating', async () => {
    const onRate = vi.fn()
    const onNotNow = vi.fn()
    render(
      <JustCookedStrip
        cookCount={1}
        onRate={onRate}
        onNotNow={onNotNow}
        onDone={vi.fn()}
      />
    )
    await userEvent.click(screen.getByRole('button', { name: /not now/i }))
    expect(onNotNow).toHaveBeenCalledTimes(1)
    expect(onRate).not.toHaveBeenCalled()
  })

  it('shows "Thanks. Rated N stars." after a successful rating', async () => {
    const onRate = vi.fn().mockResolvedValue(undefined)
    render(
      <JustCookedStrip
        cookCount={1}
        onRate={onRate}
        onNotNow={vi.fn()}
        onDone={vi.fn()}
      />
    )
    const buttons = screen.getByRole('radiogroup').querySelectorAll('button')
    await userEvent.click(buttons[3]) // star 4
    await waitFor(() =>
      expect(screen.getByText(/thanks\. rated 4 stars/i)).toBeInTheDocument()
    )
  })

  it('calls onDone ~2 s after a successful rating', async () => {
    const onRate = vi.fn().mockResolvedValue(undefined)
    const onDone = vi.fn()
    render(
      <JustCookedStrip
        cookCount={1}
        onRate={onRate}
        onNotNow={vi.fn()}
        onDone={onDone}
      />
    )
    const buttons = screen.getByRole('radiogroup').querySelectorAll('button')
    await userEvent.click(buttons[0]) // star 1

    await waitFor(() =>
      expect(screen.getByText(/thanks\. rated 1 star/i)).toBeInTheDocument()
    )

    expect(onDone).not.toHaveBeenCalled()
    vi.advanceTimersByTime(2000)
    expect(onDone).toHaveBeenCalledTimes(1)
  })

  it('shows the gate sentence and no retry when onRate throws a 403', async () => {
    const err = new ApiException('Forbidden', 403)
    const onRate = vi.fn().mockRejectedValue(err)
    const onDone = vi.fn()
    render(
      <JustCookedStrip
        cookCount={1}
        onRate={onRate}
        onNotNow={vi.fn()}
        onDone={onDone}
      />
    )
    const buttons = screen.getByRole('radiogroup').querySelectorAll('button')
    await userEvent.click(buttons[0])

    await waitFor(() =>
      expect(
        screen.getByText(/ratings open up after the first cook/i)
      ).toBeInTheDocument()
    )
    // No retry offer: radiogroup is gone
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
    // onDone is never called after a 403
    vi.advanceTimersByTime(3000)
    expect(onDone).not.toHaveBeenCalled()
  })

  it('calls onRate with the clicked star index', async () => {
    const onRate = vi.fn().mockResolvedValue(undefined)
    render(
      <JustCookedStrip
        cookCount={5}
        onRate={onRate}
        onNotNow={vi.fn()}
        onDone={vi.fn()}
      />
    )
    const buttons = screen.getByRole('radiogroup').querySelectorAll('button')
    await userEvent.click(buttons[4]) // star 5
    expect(onRate).toHaveBeenCalledWith(5)
  })
})
