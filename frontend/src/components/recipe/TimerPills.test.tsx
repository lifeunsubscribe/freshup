import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TimerPills from './TimerPills'
import type { CookTimer } from '../../hooks/useCookTimers'

const NOW = Date.now()

function makeTimer(overrides: Partial<CookTimer> = {}): CookTimer {
  return {
    id: 'timer-1',
    name: 'Step 1',
    totalSeconds: 300,
    endsAt: NOW + 300_000,
    state: 'running',
    ...overrides,
  }
}

describe('TimerPills', () => {
  it('renders nothing when there are no timers', () => {
    const { container } = render(<TimerPills timers={[]} onDismiss={vi.fn()} />)
    expect(container.firstChild).toBeNull()
  })

  describe('running timers', () => {
    it('shows the timer name', () => {
      render(<TimerPills timers={[makeTimer()]} onDismiss={vi.fn()} />)
      expect(screen.getByText(/Step 1/)).toBeInTheDocument()
    })

    it('shows a countdown in m:ss format', () => {
      render(<TimerPills timers={[makeTimer({ endsAt: NOW + 150_000 })]} onDismiss={vi.fn()} />)
      // 150 s = 2:30
      expect(screen.getByText(/2:30/)).toBeInTheDocument()
    })

    it('countdown advances when time advances', () => {
      vi.useFakeTimers()
      vi.setSystemTime(NOW)
      const timer = makeTimer({ endsAt: NOW + 300_000 }) // 5:00
      const { rerender } = render(<TimerPills timers={[timer]} onDismiss={vi.fn()} />)
      expect(screen.getByText(/5:00/)).toBeInTheDocument()

      vi.advanceTimersByTime(60_000)
      rerender(<TimerPills timers={[timer]} onDismiss={vi.fn()} />)
      expect(screen.getByText(/4:00/)).toBeInTheDocument()
      vi.useRealTimers()
    })

    it('running pill is not a button (non-interactive)', () => {
      render(<TimerPills timers={[makeTimer()]} onDismiss={vi.fn()} />)
      // The running timer div does not have role="button"
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })
  })

  describe('done timers', () => {
    it('shows "{name} · done" text', () => {
      render(
        <TimerPills
          timers={[makeTimer({ state: 'done' })]}
          onDismiss={vi.fn()}
        />
      )
      expect(screen.getByText(/Step 1 · done/)).toBeInTheDocument()
    })

    it('done pill is a button', () => {
      render(
        <TimerPills
          timers={[makeTimer({ state: 'done' })]}
          onDismiss={vi.fn()}
        />
      )
      expect(screen.getByRole('button')).toBeInTheDocument()
    })

    it('calls onDismiss with the timer id when tapped', async () => {
      const onDismiss = vi.fn()
      render(
        <TimerPills
          timers={[makeTimer({ id: 'my-id', state: 'done' })]}
          onDismiss={onDismiss}
        />
      )
      await userEvent.click(screen.getByRole('button'))
      expect(onDismiss).toHaveBeenCalledWith('my-id')
    })
  })

  describe('ordering', () => {
    it('shows running timers before done timers', () => {
      const timers: CookTimer[] = [
        makeTimer({ id: 't1', name: 'Done one', state: 'done' }),
        makeTimer({ id: 't2', name: 'Running two', state: 'running', endsAt: NOW + 60_000 }),
      ]
      render(<TimerPills timers={timers} onDismiss={vi.fn()} />)
      const allText = screen.getByLabelText('Active timers').textContent ?? ''
      expect(allText.indexOf('Running two')).toBeLessThan(allText.indexOf('Done one'))
    })

    it('orders running timers by soonest endsAt first', () => {
      const timers: CookTimer[] = [
        makeTimer({ id: 't1', name: 'Later', state: 'running', endsAt: NOW + 120_000 }),
        makeTimer({ id: 't2', name: 'Sooner', state: 'running', endsAt: NOW + 30_000 }),
      ]
      render(<TimerPills timers={timers} onDismiss={vi.fn()} />)
      const allText = screen.getByLabelText('Active timers').textContent ?? ''
      expect(allText.indexOf('Sooner')).toBeLessThan(allText.indexOf('Later'))
    })
  })
})
