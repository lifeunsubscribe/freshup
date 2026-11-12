import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useCookTimers } from './useCookTimers'

describe('useCookTimers', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts with no timers', () => {
    const { result } = renderHook(() => useCookTimers())
    expect(result.current.timers).toHaveLength(0)
  })

  it('addTimer adds a running timer', () => {
    const { result } = renderHook(() => useCookTimers())
    act(() => {
      result.current.addTimer('Step 1', 300)
    })
    expect(result.current.timers).toHaveLength(1)
    expect(result.current.timers[0].name).toBe('Step 1')
    expect(result.current.timers[0].totalSeconds).toBe(300)
    expect(result.current.timers[0].state).toBe('running')
  })

  it('addTimer sets endsAt approximately now + totalSeconds * 1000', () => {
    const now = Date.now()
    const { result } = renderHook(() => useCookTimers())
    act(() => {
      result.current.addTimer('Test', 60)
    })
    const timer = result.current.timers[0]
    expect(timer.endsAt).toBeGreaterThanOrEqual(now + 60_000 - 50)
    expect(timer.endsAt).toBeLessThanOrEqual(now + 60_000 + 50)
  })

  it('transitions a timer to done when endsAt passes', () => {
    const { result } = renderHook(() => useCookTimers())
    act(() => {
      result.current.addTimer('Quick', 1)
    })
    expect(result.current.timers[0].state).toBe('running')

    // Advance fake time past the timer's end
    act(() => {
      vi.advanceTimersByTime(1500)
    })
    expect(result.current.timers[0].state).toBe('done')
  })

  it('dismissTimer removes the timer by id', () => {
    const { result } = renderHook(() => useCookTimers())
    act(() => {
      result.current.addTimer('Step 1', 300)
    })
    const id = result.current.timers[0].id
    act(() => {
      result.current.dismissTimer(id)
    })
    expect(result.current.timers).toHaveLength(0)
  })

  it('supports multiple concurrent timers', () => {
    const { result } = renderHook(() => useCookTimers())
    act(() => {
      result.current.addTimer('Step 1', 60)
      result.current.addTimer('Step 2', 120)
    })
    expect(result.current.timers).toHaveLength(2)
    const names = result.current.timers.map(t => t.name)
    expect(names).toContain('Step 1')
    expect(names).toContain('Step 2')
  })

  it('only transitions timers that have elapsed', () => {
    const { result } = renderHook(() => useCookTimers())
    act(() => {
      result.current.addTimer('Short', 1)
      result.current.addTimer('Long', 300)
    })

    act(() => {
      vi.advanceTimersByTime(1500)
    })

    const short = result.current.timers.find(t => t.name === 'Short')!
    const long = result.current.timers.find(t => t.name === 'Long')!
    expect(short.state).toBe('done')
    expect(long.state).toBe('running')
  })

  it('assigns unique ids to each timer', () => {
    const { result } = renderHook(() => useCookTimers())
    act(() => {
      result.current.addTimer('A', 60)
      result.current.addTimer('B', 60)
    })
    const ids = result.current.timers.map(t => t.id)
    expect(new Set(ids).size).toBe(2)
  })

  it('clears the interval on unmount', () => {
    const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval')
    const { unmount } = renderHook(() => useCookTimers())
    unmount()
    expect(clearIntervalSpy).toHaveBeenCalled()
    clearIntervalSpy.mockRestore()
  })
})
