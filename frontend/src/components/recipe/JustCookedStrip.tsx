import { useState, useRef, useEffect } from 'react'

interface JustCookedStripProps {
  cookCount: number
  onRate: (stars: number) => Promise<void>
  onDismiss: () => void
}

type StripState = 'idle' | 'submitting' | 'thanks' | 'gate'

export default function JustCookedStrip({
  cookCount,
  onRate,
  onDismiss,
}: JustCookedStripProps) {
  const [state, setState] = useState<StripState>('idle')
  const [thankedStars, setThankedStars] = useState(0)
  const thanksTimerRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    return () => {
      if (thanksTimerRef.current) clearTimeout(thanksTimerRef.current)
    }
  }, [])

  const handleStarTap = async (stars: number) => {
    if (state !== 'idle') return
    setState('submitting')
    try {
      await onRate(stars)
      setThankedStars(stars)
      setState('thanks')
      thanksTimerRef.current = setTimeout(() => {
        thanksTimerRef.current = null
        onDismiss()
      }, 2000)
    } catch (err: unknown) {
      // 403 means the gate wasn't satisfied — show the gate sentence, no retry.
      const status = (err as { status?: number })?.status
      if (status === 403) {
        setState('gate')
      } else {
        setState('idle')
      }
    }
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-cream-card border-t border-warm-border shadow-lg z-10">
      <div className="max-w-2xl mx-auto px-4 pt-3 pb-2">
        {state === 'gate' ? (
          <p className="py-3 text-[13px] leading-[1.4] text-mocha">
            Ratings open up after the first cook.
          </p>
        ) : state === 'thanks' ? (
          <p className="py-3 text-[14px] font-medium text-text-primary">
            Thanks. Rated {thankedStars} stars<span className="text-olive">.</span>
          </p>
        ) : (
          <>
            <div className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-olive text-cream-card flex items-center justify-center shrink-0">
                <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" aria-hidden="true">
                  <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
              <p className="flex-1 text-[14px] font-medium text-text-primary">
                Cooked {cookCount} times now<span className="text-olive">.</span>
              </p>
            </div>

            <div className="mt-2 flex items-center justify-between">
              <div
                role="radiogroup"
                aria-label="Rating, 1 to 5"
                className="flex gap-1"
              >
                {[1, 2, 3, 4, 5].map((n) => (
                  <button
                    key={n}
                    role="radio"
                    aria-checked={false}
                    aria-label={`${n} star${n !== 1 ? 's' : ''}`}
                    disabled={state === 'submitting'}
                    onClick={() => handleStarTap(n)}
                    className="w-11 h-11 shrink-0 rounded-full text-[14px] font-medium bg-cream-card border border-warm-btn-border text-text-primary disabled:opacity-40 disabled:cursor-not-allowed transition-colors hover:bg-cream-dark"
                  >
                    {n}
                  </button>
                ))}
              </div>

              <button
                onClick={onDismiss}
                className="h-11 px-2 text-[13px] text-text-secondary"
              >
                Not now
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
