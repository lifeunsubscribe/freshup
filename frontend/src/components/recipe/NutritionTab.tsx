interface NutritionTabProps {
  nutritionalInfo: Record<string, unknown> | null
}

/**
 * Display names for schema.org NutritionInformation keys, in nutrition-label
 * order. Imported recipes store nutrients under these raw keys
 * (e.g. "saturatedFatContent").
 */
const NUTRIENT_LABELS: Array<[key: string, label: string]> = [
  ['servingSize', 'Serving size'],
  ['calories', 'Calories'],
  ['fatContent', 'Fat'],
  ['saturatedFatContent', 'Saturated fat'],
  ['transFatContent', 'Trans fat'],
  ['unsaturatedFatContent', 'Unsaturated fat'],
  ['cholesterolContent', 'Cholesterol'],
  ['sodiumContent', 'Sodium'],
  ['carbohydrateContent', 'Carbohydrates'],
  ['fiberContent', 'Fiber'],
  ['sugarContent', 'Sugar'],
  ['proteinContent', 'Protein'],
]
const LABELS = new Map(NUTRIENT_LABELS)
const ORDER = new Map(NUTRIENT_LABELS.map(([key], i) => [key, i]))

/** Fallback for unknown keys: "vitaminCContent" / "vitamin_c" → "Vitamin c". */
function nutrientLabel(key: string): string {
  const known = LABELS.get(key)
  if (known) return known
  const words = key
    .replace(/Content$/, '')
    .replace(/_/g, ' ')
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .trim()
    .toLowerCase()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/**
 * NutritionTab component displays nutritional information
 *
 * Features:
 * - Readable labels for schema.org nutrient keys, in nutrition-label order
 * - Unknown keys keep their stored order after the known ones
 * - Shows "Not available" message if no data
 */
export default function NutritionTab({ nutritionalInfo }: NutritionTabProps) {
  if (!nutritionalInfo || Object.keys(nutritionalInfo).length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-text-secondary">Nutritional information not available for this recipe.</p>
      </div>
    )
  }

  const entries = Object.entries(nutritionalInfo).sort(
    ([a], [b]) => (ORDER.get(a) ?? Infinity) - (ORDER.get(b) ?? Infinity)
  )

  return (
    <div className="space-y-3">
      {entries.map(([key, value]) => (
        <div
          key={key}
          className="flex justify-between items-center py-3 border-b border-warm-border last:border-b-0"
        >
          <span className="text-sm font-medium text-text-primary">{nutrientLabel(key)}</span>
          <span className="text-sm text-text-secondary">{String(value)}</span>
        </div>
      ))}
    </div>
  )
}
