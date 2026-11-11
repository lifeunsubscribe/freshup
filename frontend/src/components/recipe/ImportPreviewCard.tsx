import { useState } from 'react'
import { Info, ExternalLink } from 'lucide-react'
import Pill from '../ui/Pill'
import { isUnparseableQuantity } from '../../constants/recipe'
import type { RecipeResponse } from '../../api/types'

export interface ImportPreviewCardProps {
  recipe: RecipeResponse
  /** Names of ingredients that had no parseable amount (sentinel 0.001). */
  warnings?: string[]
}

function StatTile({ value, label }: { value: string; label: string }) {
  return (
    <div className="py-3 text-center bg-cream border border-warm-border rounded-card">
      <p className="text-[15px] font-medium text-text-primary">{value}</p>
      <p className="text-[11px] text-text-secondary">{label}</p>
    </div>
  )
}

/**
 * Displays the full recipe preview after a successful import, before the user
 * saves it to their library. Shows title, image, times, servings, tags,
 * ingredient list, a no-amount note when applicable, and a source attribution.
 */
export default function ImportPreviewCard({ recipe, warnings }: ImportPreviewCardProps) {
  const [imageError, setImageError] = useState(false)

  const {
    name,
    source_image,
    source_url,
    source_type,
    prep_time_minutes,
    cook_time_minutes,
    base_servings,
    tags,
    ingredients,
  } = recipe

  // Derive hostname for the "From X · view original" attribution line.
  let sourceHost = source_type === 'hellofresh_card' ? 'hellofresh.com' : ''
  if (!sourceHost && source_url) {
    try {
      sourceHost = new URL(source_url).hostname.replace(/^www\./, '')
    } catch {
      sourceHost = source_url
    }
  }

  // Source badge label
  const sourceBadge = source_type === 'hellofresh_card' ? 'HelloFresh' : sourceHost || null

  const noAmountWarning =
    warnings && warnings.length > 0
      ? `No amount given for: ${warnings.join(', ')}. They are listed by name only.`
      : null

  return (
    <div className="mx-4 bg-white border border-warm-border rounded-card-lg overflow-hidden">
      {/* Image */}
      <div className="relative">
        <div className="aspect-[4/3] w-full bg-warm-gray">
          {source_image && !imageError ? (
            <img
              src={source_image}
              alt={name}
              className="w-full h-full object-cover"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-text-tertiary text-[13px]">
              No image
            </div>
          )}
        </div>
        {sourceBadge && (
          <div className="absolute top-2 left-2">
            <Pill variant="default">{sourceBadge}</Pill>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4">
        <h2 className="text-[22px] font-medium leading-[1.3] text-text-primary">
          {name}
          <span className="text-olive">.</span>
        </h2>

        {/* Tags */}
        {tags.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mt-3">
            {tags.map((tag) => (
              <span
                key={tag}
                className="text-[11px] text-text-secondary bg-cream-icon rounded-tag px-2.5 py-1"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Stat tiles: prep / cook / servings */}
        <div className="grid grid-cols-3 gap-2 mt-4">
          <StatTile
            value={prep_time_minutes != null ? `${prep_time_minutes} min` : '—'}
            label="Prep"
          />
          <StatTile
            value={cook_time_minutes != null ? `${cook_time_minutes} min` : '—'}
            label="Cook"
          />
          <StatTile value={String(base_servings)} label="Servings" />
        </div>

        {/* Ingredients */}
        <div className="border-t border-dashed border-warm mt-5 pt-4">
          <div className="flex items-baseline justify-between">
            <h3 className="text-[15px] font-medium text-text-primary">
              Ingredients<span className="text-olive">.</span>
            </h3>
            <span className="text-[12px] text-text-secondary">{ingredients.length} found</span>
          </div>

          <ul className="mt-1">
            {ingredients.map((ing) => {
              const noAmount = isUnparseableQuantity(ing.quantity)
              return (
                <li
                  key={ing.id}
                  className="flex items-baseline gap-3 py-2.5 border-b border-warm-divider last:border-0"
                >
                  <span className="w-[68px] shrink-0 text-[13px] text-text-secondary">
                    {noAmount ? '' : `${ing.quantity}${ing.unit ? ' ' + ing.unit : ''}`}
                  </span>
                  <span className="flex-1 text-[14px] text-text-primary">{ing.ingredient_name}</span>
                </li>
              )
            })}
          </ul>
        </div>

        {/* No-amount note */}
        {noAmountWarning && (
          <div className="flex gap-2 p-3 mt-3 rounded-card bg-mocha-light border border-mocha-border text-[12px] leading-[1.4] text-mocha-dark">
            <Info size={16} className="text-mocha shrink-0 mt-0.5" />
            <p>{noAmountWarning}</p>
          </div>
        )}

        {/* Source attribution */}
        {sourceHost && source_url && (
          <a
            href={source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 min-h-[44px] text-[12px] text-olive mt-1"
          >
            From {sourceHost} · view original
            <ExternalLink size={14} />
          </a>
        )}
      </div>
    </div>
  )
}
