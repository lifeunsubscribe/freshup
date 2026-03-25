import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

interface RecipeHeaderProps {
  title: string
  subtitle?: string
  imageUrl?: string
}

/**
 * RecipeHeader component for recipe detail view
 *
 * Features:
 * - Back navigation button (top-left)
 * - Recipe title (26px/500) with olive period
 * - Subtitle below title
 * - Hero image with 4:3 aspect ratio
 */
export default function RecipeHeader({ title, subtitle, imageUrl }: RecipeHeaderProps) {
  const navigate = useNavigate()

  return (
    <div className="mb-4">
      {/* Back button */}
      <button
        onClick={() => navigate(-1)}
        className="flex items-center gap-2 mb-4 text-text-secondary hover:text-text-primary transition-colors"
        aria-label="Go back"
      >
        <ArrowLeft size={20} />
        <span className="text-sm font-medium">Back</span>
      </button>

      {/* Hero image (4:3 aspect ratio) */}
      {imageUrl && (
        <div className="relative w-full mb-4 rounded-card overflow-hidden bg-warm-gray" style={{ paddingBottom: '75%' }}>
          <img
            src={imageUrl}
            alt={title}
            className="absolute inset-0 w-full h-full object-cover"
            onError={(e) => {
              // Hide image on error
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
