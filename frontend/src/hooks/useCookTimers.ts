import { useReducer, useEffect } from 'react'

export interface CookTimer {
  id: string
  name: string
  totalSeconds: number
  endsAt: number
  state: 'running' | 'done'
}

type TimerAction =
  | { type: 'ADD'; id: string; name: string; totalSeconds: number; endsAt: number }
  | { type: 'TICK'; now: number }
  | { type: 'DISMISS'; id: string }

function reducer(state: CookTimer[], action: TimerAction): CookTimer[] {
  switch (action.type) {
    case 'ADD':
      return [...state, {
        id: action.id,
        name: action.name,
        totalSeconds: action.totalSeconds,
        endsAt: action.endsAt,
        state: 'running',
      }]
    case 'TICK': {
      const hasExpired = state.some(t => t.state === 'running' && action.now >= t.endsAt)
      if (!hasExpired) return state
      return state.map(timer =>
        timer.state === 'running' && action.now >= timer.endsAt
          ? { ...timer, state: 'done' }
          : timer
      )
    }
    case 'DISMISS':
      return state.filter(t => t.id !== action.id)
    default:
      return state
  }
}

export function useCookTimers() {
  const [timers, dispatch] = useReducer(reducer, [])

  // Single shared interval; ticking every 500 ms keeps countdowns smooth
  // while staying far below any re-render budget.
  useEffect(() => {
    const id = setInterval(() => {
      dispatch({ type: 'TICK', now: Date.now() })
    }, 500)
    return () => clearInterval(id)
  }, [])

  function addTimer(name: string, totalSeconds: number): void {
    dispatch({
      type: 'ADD',
      id: `timer-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      name,
      totalSeconds,
      endsAt: Date.now() + totalSeconds * 1000,
    })
  }

  function dismissTimer(id: string): void {
    dispatch({ type: 'DISMISS', id })
  }

  return { timers, addTimer, dismissTimer }
}
