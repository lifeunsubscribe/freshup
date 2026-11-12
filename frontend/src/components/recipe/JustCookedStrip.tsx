import { useState, useEffect, useRef } from 'react'
import { ApiException } from '../../api/client'

interface JustCookedStripProps {
  cookCount: number
  onRate: (stars: number) => Promise<void>
  onNotNow: () => void
  /** Called ~2 s after a successful rating so the parent can restore ActionBar. */
  onDone: () => void
}

type StripState = 'idle' | 'submitting' | 'rated' | 'gated'

export default function JustCookedStrip({
  cookCount,
  onRate,
  onNotNow,
  onDone,
}: JustCookedStripProps) {
  const [state, setState] = useState<StripState>('idle')
  const [ratedStars, setRatedStars] = useState(0)
  const doneTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (doneTimerRef.current) clearTimeout(doneTimerRef.current)
    }
  }, [])

  const handleStarClick = async (n: number) => {
    if (state !== 'idle') return
    setState('submitting')
    try {
      await onRate(n)
      setRatedStars(n)
      setState('rated')
      doneTimerRef.current = setTimeout(() => {
        doneTimerRef.current = null
        onDone()
      }, 2000)
    } catch (err) {
      // 403 means the gate is still active (race or stale state) — show the gate sentence.
      // Any other error (network blip, 5xx) resets to idle so the user can retry.
      if (err instanceof ApiException && err.status === 403) {
        setState('gated')
      } else {
        setState('idle')
      }
    }
  }

  if (state === 'gated') {
    return (
      <div className="fixed bottom-0 left-0 right-0 bg-cream border-t border-warm-border shadow-lg z-10">
        <div className="max-w-2xl mx-auto px-4 py-4">
          <p className="text-[13px] text-mocha">Ratings open up after the first cook.</p>
        </div>
      </div>
    )
  }

  if (state === 'rated') {
    return (
      <div className="fixed bottom-0 left-0 right-0 bg-cream border-t border-warm-border shadow-lg z-10">
        <div className="max-w-2xl mx-auto px-4 py-4">
          <p className="text-[14px] font-medium">Thanks. Rated {ratedStars} stars.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-cream border-t border-warm-border shadow-lg z-10">
      <div className="max-w-2xl mx-auto px-4 pt-3 pb-2">
        <div className="flex items-center gap-2">
          <span className="w-5 h-5 rounded-full bg-olive text-cream-card flex items-center justify-center shrink-0">
            <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M5 12.5l4.5 4.5L19 7.5" />
            </svg>
          </span>
          <p className="flex-1 text-[14px] font-medium">Cooked {cookCount} times now.</p>
        </div>
        <p className="text-[13px] text-text-secondary mt-0.5">How was it?</p>
        <div className="mt-2 flex items-center justify-between">
          <div role="radiogroup" aria-label="Rating, 1 to 5" className="flex gap-1">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                role="radio"
                aria-checked={false}
                onClick={() => handleStarClick(n)}
                disabled={state === 'submitting'}
                aria-label={`Rate ${n} star${n === 1 ? '' : 's'}`}
                className="w-11 h-11 shrink-0 rounded-full text-[14px] bg-cream-card border border-warm-btn-border text-text-primary disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {n}
              </button>
            ))}
          </div>
          <button
            onClick={onNotNow}
            className="h-11 px-2 text-[13px] text-text-secondary"
          >
            Not now
          </button>
        </div>
      </div>
    </div>
  )
}
