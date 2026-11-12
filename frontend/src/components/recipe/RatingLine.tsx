import { useState, useEffect } from 'react'

interface RatingLineProps {
  hasCooked: boolean
  rating: number | null
  onRate: (stars: number) => Promise<void>
}

function StarDisplay({ rating }: { rating: number }) {
  return (
    <span aria-label={`${rating} of 5 stars`}>
      {'★'.repeat(rating)}{'☆'.repeat(5 - rating)}
    </span>
  )
}

export default function RatingLine({ hasCooked, rating, onRate }: RatingLineProps) {
  const [displayRating, setDisplayRating] = useState(rating)
  const [editing, setEditing] = useState(false)

  // Sync display when parent's rating prop updates (e.g. after query refetches).
  useEffect(() => {
    setDisplayRating(rating)
    setEditing(false)
  }, [rating])

  const handleStarClick = async (n: number) => {
    const prevRating = displayRating
    const prevEditing = editing
    setDisplayRating(n)
    setEditing(false)
    try {
      await onRate(n)
    } catch {
      setDisplayRating(prevRating)
      setEditing(prevEditing)
    }
  }

  if (displayRating !== null && !editing) {
    return (
      <p className="mt-3 text-[12px] leading-[1.4] text-text-secondary">
        Your rating: <StarDisplay rating={displayRating} />{' '}·{' '}
        <button
          onClick={() => setEditing(true)}
          className="text-olive text-[12px]"
        >
          change
        </button>
      </p>
    )
  }

  if (hasCooked || editing) {
    return (
      <div className="mt-3">
        <p className="text-[12px] leading-[1.4] text-text-secondary">
          {editing ? 'Pick a new rating:' : "You've cooked this. Rate it?"}
        </p>
        <div role="radiogroup" aria-label="Rating, 1 to 5" className="flex gap-1 mt-1.5">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              role="radio"
              aria-checked={n === displayRating}
              onClick={() => handleStarClick(n)}
              aria-label={`Rate ${n} star${n === 1 ? '' : 's'}`}
              className="w-11 h-11 shrink-0 rounded-full text-[14px] bg-cream-card border border-warm-btn-border text-text-primary"
            >
              {n}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <p className="mt-3 text-[12px] leading-[1.4] text-text-tertiary">
      Ratings open up after the first cook.
    </p>
  )
}
