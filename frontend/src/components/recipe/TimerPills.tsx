import type { CookTimer } from '../../hooks/useCookTimers'

function formatCountdown(endsAt: number): string {
  const remaining = Math.max(0, endsAt - Date.now())
  const totalSecs = Math.ceil(remaining / 1000)
  const mins = Math.floor(totalSecs / 60)
  const secs = totalSecs % 60
  return `${mins}:${String(secs).padStart(2, '0')}`
}

interface TimerPillsProps {
  timers: CookTimer[]
  onDismiss: (id: string) => void
}

/**
 * Shows cook timer pills in the top bar.
 * Running timers display a live "m:ss" countdown; finished timers turn mocha
 * and can be tapped to dismiss.
 * Pills are ordered: running timers (soonest-first) then done timers.
 */
export default function TimerPills({ timers, onDismiss }: TimerPillsProps) {
  if (timers.length === 0) return null

  const sorted = [...timers].sort((a, b) => {
    if (a.state === 'running' && b.state === 'done') return -1
    if (a.state === 'done' && b.state === 'running') return 1
    if (a.state === 'running' && b.state === 'running') return a.endsAt - b.endsAt
    return 0
  })

  return (
    <div className="flex gap-1.5 flex-wrap" aria-label="Active timers">
      {sorted.map(timer =>
        timer.state === 'done' ? (
          <button
            key={timer.id}
            onClick={() => onDismiss(timer.id)}
            className="inline-flex items-center px-2.5 py-1 rounded-full bg-mocha text-cream text-xs font-medium"
            aria-label={`${timer.name} done, tap to dismiss`}
          >
            {timer.name} · done
          </button>
        ) : (
          <div
            key={timer.id}
            className="inline-flex items-center px-2.5 py-1 rounded-full bg-cream-dark text-text-primary text-xs font-medium"
            aria-label={`${timer.name}: ${formatCountdown(timer.endsAt)} remaining`}
          >
            {timer.name} · {formatCountdown(timer.endsAt)}
          </div>
        )
      )}
    </div>
  )
}
