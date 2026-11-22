import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bookmark } from 'lucide-react'
import Pill from '../ui/Pill'
import { useOpenCard } from '../../api/hooks/useCatalog'
import { useToggleBookmark } from '../../api/hooks/useRecipeEngagement'
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
  // Saving from the card: its own request, so it never shows "Opening…" or navigates.
  const { mutate: openForSave, isPending: isImportingForSave } = useOpenCard()
  const toggleBookmark = useToggleBookmark()
  const [justSaved, setJustSaved] = useState(false)
  const [saveFailed, setSaveFailed] = useState(false)
  const isSaved = card.is_persisted || justSaved
  const isSaving = isImportingForSave || toggleBookmark.isPending

  /**
   * The bookmark saves the recipe where it stands: the card stays on the page
   * and its bookmark fills in. Looking at a recipe never saves it; this does.
   */
  function handleSave(e: React.MouseEvent) {
    e.stopPropagation()
    if (isSaved || isSaving) return
    setSaveFailed(false)
    const bookmark = (recipeId: string) =>
      toggleBookmark.mutate(
        { recipeId, next: true },
        { onSuccess: () => setJustSaved(true), onError: () => setSaveFailed(true) }
      )
    if (card.recipe_id) {
      bookmark(card.recipe_id)
      return
    }
    // Not fetched yet: bring the recipe in first, then save it.
    openForSave(
      { cardId: card.id, source: card.source_type, collectionSlug },
      { onSuccess: (recipe) => bookmark(recipe.id), onError: () => setSaveFailed(true) }
    )
  }

  function handleOpen() {
    openCard(
      { cardId: card.id, source: card.source_type, collectionSlug },
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
      className="flex flex-col h-full w-full text-left bg-white rounded-[10px] overflow-hidden shadow-sm hover:shadow-md transition-shadow cursor-pointer min-h-[44px]"
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

        {isSaved && (
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

      {/* Grows to fill the card so the saved line sits at the bottom, matching RecipeCard */}
      <div className="p-3 flex-1 flex flex-col">
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

        <div className="mt-auto flex items-center gap-1 text-xs">
          {isSaved ? (
            <span className="flex items-center gap-1">
              <Bookmark size={14} className="fill-olive stroke-olive" strokeWidth={2} />
              <span className="text-olive font-medium">Saved</span>
            </span>
          ) : (
            <button
              type="button"
              onClick={handleSave}
              disabled={isSaving}
              aria-label={`Save ${card.name}`}
              className="flex items-center gap-1 -my-2 py-2 pr-2 disabled:opacity-60"
            >
              <Bookmark size={14} className="stroke-mocha" strokeWidth={2} />
              <span className="text-mocha">{isSaving ? 'Saving…' : 'Not saved yet'}</span>
            </button>
          )}
          {isNew && (
            <span className="text-mocha font-medium ml-1">New</span>
          )}
        </div>

        {saveFailed && (
          <p role="alert" className="mt-1 text-xs text-mocha">
            Could not save this one. Try again.
          </p>
        )}

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
