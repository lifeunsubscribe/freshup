interface NutritionTabProps {
  nutritionalInfo: Record<string, unknown> | null
}

/**
 * NutritionTab component displays nutritional information
 *
 * Features:
 * - Displays nutritional_info JSON if available
 * - Shows "Not available" message if no data
 * - Future enhancement: format nutrition data in structured layout
 */
export default function NutritionTab({ nutritionalInfo }: NutritionTabProps) {
  if (!nutritionalInfo || Object.keys(nutritionalInfo).length === 0) {
    return (
      <div className="text-center py-8">
        <p className="text-text-secondary">Nutritional information not available for this recipe.</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {Object.entries(nutritionalInfo).map(([key, value]) => (
        <div
          key={key}
          className="flex justify-between items-center py-3 border-b border-warm-border last:border-b-0"
        >
          <span className="text-sm font-medium text-text-primary capitalize">
            {key.replace(/_/g, ' ')}
          </span>
          <span className="text-sm text-text-secondary">
            {String(value)}
          </span>
        </div>
      ))}
    </div>
  )
}
