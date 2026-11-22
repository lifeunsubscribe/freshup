import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight, Plus, X } from 'lucide-react'
import { useRecommendations } from '../../api/hooks/useRecipes'
import type { RecommendedItem } from '../../api/types'
import { ownOrSourceName } from '../../utils/sourceNames'
import { weekdayName } from '../../utils/week'

/** What the user chose for the day: a recipe in the library, or a catalog card. */
export type DinnerPick = { recipeId: string } | { cardId: string }

interface AddDinnerBandProps {
  /** The day being filled, YYYY-MM-DD. */
  date: string
  /** Recipes and cards already on the week; they are not offered again. */
  taken: { recipeIds: Set<string>; cardIds: Set<string> }
  /** True while the chosen dinner is being added. */
  adding: boolean
  error: string | null
  onAdd: (pick: DinnerPick) => void
  onClose: () => void
}

/** How many suggestions to ask for; some are filtered out as already planned. */
const SUGGESTION_COUNT = 24

/**
 * The band that opens under a week when a day has nothing: a carousel of
 * dinners to put on that day, and a way out to the full recipe pages for
 * anything the suggestions do not cover.
 */
export default function AddDinnerBand({ date, taken, adding, error, onAdd, onClose }: AddDinnerBandProps) {
  const day = weekdayName(date)
  const { data, isLoading, isError } = useRecommendations(SUGGESTION_COUNT, 'dinner')
  const options = (data ?? []).filter((item) =>
    item.kind === 'card'
      ? !taken.cardIds.has(item.card.id) &&
        !(item.card.recipe_id && taken.recipeIds.has(item.card.recipe_id))
      : !taken.recipeIds.has(item.recipe.id)
  )

  return (
    <section
      aria-label={`Add a dinner for ${day}`}
      className="rounded-card border border-warm-border bg-cream-surface"
    >
      <div className="flex items-center justify-between gap-3 px-3 pt-3">
        <h3 className="text-[14px] font-medium text-text-primary">
          Add a dinner for {day}
          <span className="text-olive">.</span>
        </h3>
        <button
          onClick={onClose}
          aria-label="Close"
          className="flex items-center justify-center w-9 h-9 -mr-1 rounded-full text-text-secondary"
        >
          <X size={16} />
        </button>
      </div>

      {isLoading && <p className="px-3 pb-3 text-sm text-text-secondary">Finding suggestions...</p>}
      {isError && <p className="px-3 pb-3 text-sm text-text-secondary">Could not load suggestions.</p>}
      {!isLoading && !isError && options.length === 0 && (
        <p className="px-3 pb-3 text-sm text-text-secondary">Nothing to suggest right now.</p>
      )}

      {options.length > 0 && (
        <ul
          aria-label={`Suggestions for ${day}`}
          className="flex gap-3 overflow-x-auto px-3 pt-2 pb-3 scrollbar-hide"
        >
          {options.map((item) => (
            <Suggestion
              key={item.kind === 'card' ? `card-${item.card.id}` : `recipe-${item.recipe.id}`}
              item={item}
              disabled={adding}
              onAdd={onAdd}
            />
          ))}
        </ul>
      )}

      {error && (
        <p role="alert" className="px-3 pb-3 text-[12px] text-terra-dark">
          {error}
        </p>
      )}

      <Link
        to="/recipes"
        className="flex items-center justify-between gap-2 px-3 py-3 border-t border-warm-border text-[13px] text-olive"
      >
        <span>
          Browse all recipes
          <span className="block text-[12px] text-text-secondary">
            Search and filters; use Add to plan on the one you want.
          </span>
        </span>
        <ChevronRight size={16} />
      </Link>
    </section>
  )
}

function Suggestion({
  item,
  disabled,
  onAdd,
}: {
  item: RecommendedItem
  disabled: boolean
  onAdd: (pick: DinnerPick) => void
}) {
  const [imageError, setImageError] = useState(false)
  const view =
    item.kind === 'card'
      ? {
          name: item.card.name,
          image: item.card.image_url,
          source: item.card.source_type,
          minutes: item.card.prep_time_minutes,
          pick: { cardId: item.card.id } as DinnerPick,
        }
      : {
          name: item.recipe.name,
          image: item.recipe.source_image ?? null,
          source: item.recipe.source_type,
          minutes: item.recipe.cook_time_minutes ?? item.recipe.prep_time_minutes,
          pick: { recipeId: item.recipe.id } as DinnerPick,
        }
  const details = [ownOrSourceName(view.source), view.minutes ? `${view.minutes} min` : null]
    .filter(Boolean)
    .join(' · ')

  return (
    <li className="flex-shrink-0 w-[150px] flex flex-col rounded-card border border-warm-border bg-white overflow-hidden">
      <div className="w-full aspect-[4/3] bg-warm-gray">
        {view.image && !imageError ? (
          <img
            src={view.image}
            alt=""
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <span className="w-full h-full flex items-center justify-center text-text-tertiary text-xs">
            No image
          </span>
        )}
      </div>
      <div className="flex-1 flex flex-col gap-2 p-2.5">
        <div>
          <p className="text-[13px] font-medium text-text-primary leading-tight line-clamp-2">
            {view.name}
          </p>
          <p className="mt-0.5 text-[11px] text-text-secondary">{details}</p>
        </div>
        <button
          onClick={() => onAdd(view.pick)}
          disabled={disabled}
          aria-label={`Add ${view.name}`}
          className="mt-auto flex items-center justify-center gap-1 h-9 rounded-button-sm bg-olive text-white text-[13px] font-medium disabled:opacity-50"
        >
          <Plus size={14} />
          Add
        </button>
      </div>
    </li>
  )
}
