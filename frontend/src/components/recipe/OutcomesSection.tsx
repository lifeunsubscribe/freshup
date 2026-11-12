import { useRecipeOutcomes } from '../../api/hooks/useRecipes'
import { useAuth } from '../../contexts/AuthContext'
import { relativeTime } from '../../utils/relativeTime'
import { StarDisplay } from './RatingLine'
import type { RecipeOutcome } from '../../api/types'

interface OutcomesSectionProps {
  recipeId: string
}

function SkeletonRow() {
  return (
    <li className="p-3 bg-cream-card border border-warm-border rounded-card space-y-2">
      <div className="sk h-3 w-24 rounded-pill bg-cream-icon" />
      <div className="sk h-3 w-40 rounded-pill bg-cream-icon" />
    </li>
  )
}

interface OutcomeRowProps {
  outcome: RecipeOutcome
  isViewer: boolean
}

function OutcomeRow({ outcome, isViewer }: OutcomeRowProps) {
  const displayName = isViewer ? 'You' : outcome.user_name

  return (
    <li className="p-3 bg-cream-card border border-warm-border rounded-card space-y-1.5">
      <p className="text-[13px] font-medium text-text-primary">{displayName}</p>

      {outcome.rating !== null && <StarDisplay rating={outcome.rating} />}

      {outcome.times_cooked > 0 && outcome.last_cooked_at && (
        <p className="text-[12px] text-text-secondary">
          Cooked {outcome.times_cooked} {outcome.times_cooked === 1 ? 'time' : 'times'}, last{' '}
          {relativeTime(outcome.last_cooked_at)}
        </p>
      )}

      {outcome.rating_comment && (
        <p className="text-[13px] leading-normal text-text-primary">
          &ldquo;{outcome.rating_comment}&rdquo;
        </p>
      )}

      {outcome.latest_cook_notes && (
        <p className="text-[12px] text-text-secondary">
          Last time: {outcome.latest_cook_notes}
        </p>
      )}

      {outcome.rating_photos && outcome.rating_photos.length > 0 && (
        <div className="flex gap-2 overflow-x-auto">
          {outcome.rating_photos.map((url, i) => (
            <a
              key={i}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0"
            >
              <img
                src={url}
                alt=""
                className="w-16 h-16 rounded-image-card object-cover"
              />
            </a>
          ))}
        </div>
      )}
    </li>
  )
}

export default function OutcomesSection({ recipeId }: OutcomesSectionProps) {
  const { currentUser } = useAuth()
  const { data: outcomes, isLoading, isError } = useRecipeOutcomes(recipeId)

  return (
    <section className="mx-4 mt-5">
      <h2 className="text-[15px] font-medium leading-[1.3]">
        How it turned out<span className="text-olive">.</span>
      </h2>

      {isLoading && (
        <ul className="mt-3 space-y-2">
          <SkeletonRow />
          <SkeletonRow />
        </ul>
      )}

      {isError && (
        <p className="mt-3 text-[13px] text-mocha">
          Could not load how it turned out.
        </p>
      )}

      {!isLoading && !isError && outcomes && outcomes.length === 0 && (
        <p className="mt-3 text-[13px] text-text-secondary">
          Nobody here has cooked this yet.
        </p>
      )}

      {!isLoading && !isError && outcomes && outcomes.length > 0 && (
        <ul className="mt-3 space-y-2">
          {[...outcomes]
            .sort((a, b) => {
              if (a.user_id === currentUser?.id) return -1
              if (b.user_id === currentUser?.id) return 1
              return 0
            })
            .map((outcome) => (
              <OutcomeRow
                key={outcome.user_id}
                outcome={outcome}
                isViewer={outcome.user_id === currentUser?.id}
              />
            ))}
        </ul>
      )}
    </section>
  )
}
