import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bookmark } from 'lucide-react'
import Pill from '../ui/Pill'
import { useOpenCard } from '../../api/hooks/useCatalog'
import type { CardResponse } from '../../api/types'

export interface CatalogCardProps {
  card: CardResponse
  collectionSlug: string
  isNew?: boolean
}

export default function CatalogCard({ card, collectionSlug, isNew = false }: CatalogCardProps) {
  const navigate = useNavigate()
  const [imageError, setImageError] = useState(false)
  const { mutate: openCard, isPending, isError, error, reset } = useOpenCard()

  function handleOpen() {
    openCard(
      { cardId: card.id, source: 'hellofresh_web', collectionSlug },
      {
        onSuccess: (recipe) => navigate(`/recipes/${recipe.id}`),
      }
    )
  }

  function handleTap() {
    if (isPending) return
    if (card.recipe_id) {
      navigate(`/recipes/${card.recipe_id}`)
      return
    }
    handleOpen()
  }

  function handleRetry(e: React.MouseEvent) {
    e.stopPropagation()
    reset()
    handleOpen()
  }

  const ratingDisplay =
    card.rating != null && card.rating_count != null
      ? `${card.rating.toFixed(1)} (${card.rating_count})`
      : null

  return (
    <div
      role="button"
      tabIndex={isPending ? -1 : 0}
      aria-label={card.name}
      aria-disabled={isPending}
      onClick={handleTap}
      onKeyDown={(e) => {
        if (e.target !== e.currentTarget) return
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          handleTap()
        }
      }}
      className="block w-full text-left bg-white rounded-[10px] overflow-hidden shadow-sm hover:shadow-md transition-shadow cursor-pointer min-h-[44px]"
    >
      {/* Image with 4:3 aspect ratio — same sizing as RecipeCard so both sit in one row without a seam */}
      <div className="relative w-full" style={{ paddingBottom: '75%' }}>
        <div className="absolute inset-0 bg-warm-gray">
          {card.image_url && !imageError ? (
            <img
              src={card.image_url}
              alt={card.name}
              className="w-full h-full object-cover"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-text-tertiary">
              No image
            </div>
          )}
        </div>

        {card.is_persisted && (
          <div className="absolute top-2 left-2">
            <Pill variant="success">Saved</Pill>
          </div>
        )}

        {isPending && (
          <div className="absolute inset-0 bg-white/60 flex items-center justify-center">
            <span className="text-sm text-text-secondary">Opening…</span>
          </div>
        )}
      </div>

      <div className="p-3">
        <h3 className="text-[13px] font-medium text-text-primary line-clamp-2 mb-1">
          {card.name}
        </h3>

        {card.headline && (
          <p className="text-xs text-text-secondary line-clamp-1 mb-1">{card.headline}</p>
        )}

        <div className="text-xs text-text-secondary mb-1.5">
          {card.prep_time_minutes != null && <span>{card.prep_time_minutes} min</span>}
          {card.prep_time_minutes != null && ratingDisplay && <span> · </span>}
          {ratingDisplay && <span>{ratingDisplay}</span>}
        </div>

        <div className="flex items-center gap-1 text-xs">
          <Bookmark
            size={14}
            className={card.is_persisted ? 'fill-olive stroke-olive' : 'stroke-mocha'}
            strokeWidth={2}
          />
          {card.is_persisted ? (
            <span className="text-olive font-medium">Saved</span>
          ) : (
            <span className="text-mocha">Not saved yet</span>
          )}
          {isNew && (
            <span className="text-mocha font-medium ml-1">New</span>
          )}
        </div>

        {isError && (
          <div className="mt-2 text-xs text-mocha">
            {(error as Error)?.message || 'Could not open recipe.'}{' '}
            <button onClick={handleRetry} className="underline">
              Try again
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
