import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Bookmark, Heart } from 'lucide-react'

interface RecipeHeaderProps {
  title: string
  subtitle?: string
  imageUrl?: string
  isBookmarked?: boolean
  isLiked?: boolean
  onBookmarkToggle?: () => void
  onLikeToggle?: () => void
  isEngagementLoading?: boolean
}

/**
 * RecipeHeader component for recipe detail view
 *
 * Features:
 * - Back navigation button (top-left)
 * - Bookmark and heart glyph buttons (top-right, 44px touch targets)
 * - Recipe title (26px/500) with olive period
 * - Subtitle below title
 * - Hero image with 4:3 aspect ratio
 */
export default function RecipeHeader({
  title,
  subtitle,
  imageUrl,
  isBookmarked = false,
  isLiked = false,
  onBookmarkToggle,
  onLikeToggle,
  isEngagementLoading = false,
}: RecipeHeaderProps) {
  const navigate = useNavigate()

  return (
    <div className="mb-4">
      {/* Top bar: back button on left, engagement glyphs on right */}
      <div className="flex items-center justify-between mb-4">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
          aria-label="Go back"
        >
          <ArrowLeft size={20} />
          <span className="text-sm font-medium">Back</span>
        </button>

        <div className="flex items-center gap-1">
          <button
            onClick={onBookmarkToggle}
            disabled={isEngagementLoading || !onBookmarkToggle}
            className="w-11 h-11 flex items-center justify-center rounded-button hover:bg-cream-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={isBookmarked ? 'Remove bookmark' : 'Bookmark recipe'}
            aria-pressed={isBookmarked}
          >
            <Bookmark
              size={22}
              className={isBookmarked ? 'fill-olive stroke-olive' : 'stroke-text-secondary'}
              strokeWidth={1.8}
            />
          </button>

          <button
            onClick={onLikeToggle}
            disabled={isEngagementLoading || !onLikeToggle}
            className="w-11 h-11 flex items-center justify-center rounded-button hover:bg-cream-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            aria-label={isLiked ? 'Unlike recipe' : 'Like recipe'}
            aria-pressed={isLiked}
          >
            <Heart
              size={22}
              className={isLiked ? 'fill-olive stroke-olive' : 'stroke-text-secondary'}
              strokeWidth={1.8}
            />
          </button>
        </div>
      </div>

      {/* Hero image (4:3 aspect ratio) */}
      {imageUrl && (
        <div className="relative w-full mb-4 rounded-card overflow-hidden bg-warm-gray" style={{ paddingBottom: '75%' }}>
          <img
            src={imageUrl}
            alt={title}
            className="absolute inset-0 w-full h-full object-cover"
            onError={(e) => {
              e.currentTarget.style.display = 'none'
            }}
          />
        </div>
      )}

      {/* Title with olive period */}
      <h1 className="text-[26px] font-medium text-text-primary mb-1">
        {title}
        <span className="text-olive">.</span>
      </h1>

      {/* Subtitle */}
      {subtitle && (
        <p className="text-sm text-text-secondary">{subtitle}</p>
      )}
    </div>
  )
}
