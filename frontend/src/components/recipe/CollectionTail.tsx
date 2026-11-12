export type TailState =
  | 'bringing-in-more'
  | 'more-arrived'
  | 'caught-up'
  | 'could-not-bring-in-more'

interface CollectionTailProps {
  state: TailState
  newCount?: number
}

export default function CollectionTail({ state, newCount = 0 }: CollectionTailProps) {
  if (state === 'bringing-in-more') {
    return (
      <div className="mt-6 space-y-3">
        {/* Skeleton row */}
        <div className="grid grid-cols-2 gap-3">
          <div className="h-40 rounded-[10px] bg-warm-gray/40 animate-pulse" aria-hidden="true" />
          <div className="h-40 rounded-[10px] bg-warm-gray/40 animate-pulse" aria-hidden="true" />
        </div>
        <p className="text-sm text-text-secondary text-center">Bringing in more…</p>
      </div>
    )
  }

  if (state === 'more-arrived') {
    return (
      <p className="mt-6 text-sm text-text-secondary text-center" aria-live="polite">
        {newCount > 0 ? `${newCount} more arrived` : 'More arrived'}
      </p>
    )
  }

  if (state === 'caught-up') {
    return (
      <p className="mt-6 text-sm text-text-tertiary text-center">
        That&rsquo;s everything in this collection.
      </p>
    )
  }

  // could-not-bring-in-more
  return (
    <p className="mt-6 text-sm text-mocha text-center">
      Could not bring in more right now. What is already here still works.
    </p>
  )
}
