import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Bookmark, Heart, Timer } from 'lucide-react'
import type { TabType } from './TabBar'
import type { CookTimer } from '../../hooks/useCookTimers'
import TimerPills from './TimerPills'

interface RecipeHeaderProps {
  title: string
  subtitle?: string
  imageUrl?: string
  isBookmarked?: boolean
  isLiked?: boolean
  onBookmarkToggle?: () => void
  onLikeToggle?: () => void
  isEngagementLoading?: boolean
  // Cook-tab timer slot
  activeTab?: TabType
  timers?: CookTimer[]
  onDismissTimer?: (id: string) => void
  onOpenTimerSheet?: () => void
  /** Shown under the title and above the photo: attribution, pills, rating line. */
  children?: ReactNode
}

/**
 * RecipeHeader component for recipe detail view.
 *
 * Order follows docs/mockups/recipe-acquisition/3-recipe-detail.html: top bar,
 * title, whatever the page passes as children, then the photo.
 *
 * Top-bar right slot:
 *   - Cook tab: timer button (opens NewTimerSheet) + TimerPills
 *   - Other tabs: bookmark and heart buttons
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
  activeTab,
  timers = [],
  onDismissTimer,
  onOpenTimerSheet,
  children,
}: RecipeHeaderProps) {
  const navigate = useNavigate()
  const isCookTab = activeTab === 'cook'

  return (
    <div className="mb-4">
      {/* Top bar: back button on left, right slot depends on active tab */}
      <div className="flex items-center justify-between mb-2">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-2 text-text-secondary hover:text-text-primary transition-colors"
          aria-label="Go back"
        >
          <ArrowLeft size={20} />
          <span className="text-sm font-medium">Back</span>
        </button>

        {isCookTab ? (
          /* Cook tab: timer button + live timer pills */
          <div className="flex items-center gap-2 min-w-0">
            {timers.length > 0 && onDismissTimer && (
              <TimerPills timers={timers} onDismiss={onDismissTimer} />
            )}
            <button
              onClick={onOpenTimerSheet}
              className="w-11 h-11 flex items-center justify-center rounded-button hover:bg-cream-dark transition-colors flex-shrink-0"
              aria-label="New timer"
            >
              <Timer size={22} className="stroke-text-secondary" strokeWidth={1.8} />
            </button>
          </div>
        ) : (
          /* Ingredients / Nutrition tabs: bookmark and heart */
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
        )}
      </div>

      {/* Title with olive period */}
      <h1 className="text-[26px] font-medium leading-[1.3] text-text-primary">
        {title}
        <span className="text-olive">.</span>
      </h1>

      {/* Subtitle */}
      {subtitle && (
        <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>
      )}

      {children}

      {/* Hero image (4:3, 16px radius) */}
      {imageUrl && (
        <div className="relative w-full mt-4 aspect-[4/3] rounded-image-hero overflow-hidden bg-warm-gray">
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
    </div>
  )
}
