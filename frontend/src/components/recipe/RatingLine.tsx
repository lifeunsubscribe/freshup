import { useState } from 'react'

interface RatingLineProps {
  /** Number of cook events this user has for the recipe. 0 = never cooked. */
  cookCount: number
  rating: number | null
  onRate: (stars: number) => Promise<void>
}

export default function RatingLine({ cookCount, rating, onRate }: RatingLineProps) {
  const [editing, setEditing] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  if (cookCount === 0 && rating === null) {
    return (
      <p className="mt-3 text-[12px] leading-[1.4] text-text-tertiary">
        Ratings open up after the first cook.
      </p>
    )
  }

  if (rating !== null && !editing) {
    return (
      <p className="mt-3 text-[12px] leading-[1.4] text-text-secondary">
        Your rating: {rating}/5{' '}
        <button
          onClick={() => setEditing(true)}
          className="text-olive underline-offset-2"
        >
          change
        </button>
      </p>
    )
  }

  const handleStarTap = async (stars: number) => {
    if (submitting) return
    setSubmitting(true)
    try {
      await onRate(stars)
      setEditing(false)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mt-3">
      <p className="text-[12px] leading-[1.4] text-text-secondary mb-2">
        {rating === null ? "You've cooked this. Rate it?" : 'Change your rating:'}
      </p>
      <div
        role="radiogroup"
        aria-label="Rating, 1 to 5"
        className="flex gap-1"
      >
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            role="radio"
            aria-checked={n === rating}
            aria-label={`${n} star${n !== 1 ? 's' : ''}`}
            disabled={submitting}
            onClick={() => handleStarTap(n)}
            className={`w-11 h-11 shrink-0 rounded-full text-[14px] font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
              n <= (rating ?? 0)
                ? 'bg-olive text-cream-card'
                : 'bg-cream-card border border-warm-btn-border text-text-primary hover:bg-cream-dark'
            }`}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  )
}
