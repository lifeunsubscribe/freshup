import { Link } from 'react-router-dom'
import { Heart } from 'lucide-react'
import { useState } from 'react'
import Pill from '../ui/Pill'

export interface RecipeCardProps {
  recipe: {
    id: string
    name: string
    source_type: string
    cook_time_minutes: number | null
    prep_time_minutes: number | null
    tags: string[]
  }
  variant?: 'grid' | 'carousel'
  isLastVisible?: boolean
  isFavorited?: boolean
  onFavoriteToggle?: () => void
  householdContext?: {
    timesCooked: number
  }
  imageUrl?: string
  servings?: number
}

/**
 * RecipeCard component displays recipe information in grid or carousel layouts
 *
 * Features:
 * - 4:3 aspect ratio image with rounded top corners (10px)
 * - Favorite heart overlay (top-right): filled when favorited, outline when not
 * - Source badge (top-left): conditional based on source_type
 * - Recipe name: truncates at 2 lines, 13px/500 weight
 * - Metadata: cook time, servings, cuisine tag with " · " separator
 * - Household context: "✓ Cooked Nx" (olive) or "Never cooked" (mocha)
 * - Grid variant: fills container width (use in 2-column grid)
 * - Carousel variant: min-width 150px with flex-shrink-0
 * - Last-visible variant: opacity 0.7 for carousel fade effect
 * - Clickable: navigates to /recipes/:id
 */
export default function RecipeCard({
  recipe,
  variant = 'grid',
  isLastVisible = false,
  isFavorited = false,
  onFavoriteToggle,
  householdContext,
  imageUrl,
  servings,
}: RecipeCardProps) {
  const { id, name, source_type, cook_time_minutes, tags } = recipe

  // Track image loading errors
  const [imageError, setImageError] = useState(false)

  // Calculate total time (prep + cook) or use cook_time if prep is not available
  const totalTime = cook_time_minutes || 0

  // Extract cuisine tag (first tag if available)
  const cuisineTag = tags.length > 0 ? tags[0] : null

  // Map source_type to badge label
  const getSourceBadge = (): string | null => {
    if (source_type === 'hellofresh_card') return 'HelloFresh'
    if (source_type === 'manual' || source_type === 'ad_hoc') return 'My recipe'
    return null
  }

  const sourceBadge = getSourceBadge()

  // Household context display
  const getHouseholdContextDisplay = () => {
    if (!householdContext) return { text: 'Never cooked', variant: 'warning' as const }
    const { timesCooked } = householdContext
    if (timesCooked === 0) return { text: 'Never cooked', variant: 'warning' as const }
    return { text: `✓ Cooked ${timesCooked}x`, variant: 'success' as const }
  }

  const householdDisplay = getHouseholdContextDisplay()

  // Variant-specific classes
  const containerClasses = `
    ${variant === 'carousel' ? 'min-w-[150px] flex-shrink-0' : ''}
    ${isLastVisible ? 'opacity-70' : ''}
  `.trim()

  return (
    <Link
      to={`/recipes/${id}`}
      className={`block bg-white rounded-[10px] overflow-hidden shadow-sm hover:shadow-md transition-shadow ${containerClasses}`}
    >
      {/* Image container with 4:3 aspect ratio and overlays */}
      {/* paddingBottom: 75% creates 4:3 aspect ratio (3/4 = 0.75) */}
      <div className="relative w-full" style={{ paddingBottom: '75%' }}>
        {/* Image */}
        <div className="absolute inset-0 bg-warm-gray">
          {imageUrl && !imageError ? (
            <img
              src={imageUrl}
              alt={name}
              className="w-full h-full object-cover"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-text-tertiary">
              No image
            </div>
          )}
        </div>

        {/* Source badge overlay (top-left) */}
        {sourceBadge && (
          <div className="absolute top-2 left-2">
            <Pill variant="default">{sourceBadge}</Pill>
          </div>
        )}

        {/* Favorite heart overlay (top-right) */}
        <button
          onClick={(e) => {
            // Prevent card navigation when clicking favorite button
            e.preventDefault()
            e.stopPropagation()
            onFavoriteToggle?.()
          }}
          className="absolute top-2 right-2 p-1.5 rounded-full bg-white/90 hover:bg-white transition-colors"
          aria-label={isFavorited ? 'Remove from favorites' : 'Add to favorites'}
        >
          <Heart
            size={20}
            className={isFavorited ? 'fill-mocha stroke-mocha' : 'stroke-mocha'}
            strokeWidth={2}
          />
        </button>
      </div>

      {/* Content section */}
      <div className="p-3">
        {/* Recipe name: 13px/500, truncate at 2 lines */}
        <h3 className="text-[13px] font-medium text-text-primary line-clamp-2 mb-2">
          {name}
        </h3>

        {/* Metadata row: cook time · servings · cuisine */}
        <div className="text-xs text-text-secondary mb-1.5">
          {totalTime > 0 && <span>{totalTime} min</span>}
          {totalTime > 0 && servings && <span> · </span>}
          {servings && <span>{servings} srv</span>}
          {(totalTime > 0 || servings) && cuisineTag && <span> · </span>}
          {cuisineTag && <span className="lowercase">{cuisineTag}</span>}
        </div>

        {/* Household context line */}
        <div className="text-xs">
          <span
            className={
              householdDisplay.variant === 'success'
                ? 'text-olive font-medium'
                : 'text-mocha'
            }
          >
            {householdDisplay.text}
          </span>
        </div>
      </div>
    </Link>
  )
}
