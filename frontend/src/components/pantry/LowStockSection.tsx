import { SectionHeader } from '../ui'
import type { LowStockAlertItem } from '../../api/types'

interface LowStockSectionProps {
  items: LowStockAlertItem[]
}

/**
 * LowStockSection component showing staple items below threshold
 *
 * Features:
 * - Displays item name, current quantity, and threshold
 * - Progress bar showing current vs threshold ratio
 * - Color: terra for low stock, olive for adequate
 * - Empty state: "Stock levels healthy"
 */
export default function LowStockSection({ items }: LowStockSectionProps) {
  return (
    <div className="bg-cream-dark rounded-card border border-warm-border p-6 mb-6">
      <SectionHeader>Low Stock Alerts</SectionHeader>

      {items.length === 0 ? (
        <p className="text-text-secondary mt-4">Stock levels healthy</p>
      ) : (
        <div className="mt-4 space-y-4">
          {items.map((item) => {
            // Calculate percentage for progress bar (current/threshold)
            const percentage = (item.quantity / item.minimum_threshold) * 100

            return (
              <div key={item.id} className="space-y-2">
                {/* Item name and quantities */}
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-text-primary">
                    {item.name}
                  </span>
                  <span className="text-sm text-text-secondary">
                    {item.quantity} / {item.minimum_threshold} {item.unit}
                  </span>
                </div>

                {/* Progress bar */}
                <div
                  className="w-full bg-cream rounded-full h-2 overflow-hidden"
                  role="progressbar"
                  aria-valuenow={item.quantity}
                  aria-valuemin={0}
                  aria-valuemax={item.minimum_threshold}
                  aria-label={`${item.name} stock level: ${item.quantity} of ${item.minimum_threshold} ${item.unit}`}
                >
                  <div
                    className="h-full bg-terra transition-all duration-300"
                    style={{ width: `${Math.min(percentage, 100)}%` }}
                  />
                </div>

                {/* Deficit message */}
                <p className="text-xs text-text-tertiary">
                  Need {item.deficit} {item.unit} more to reach threshold
                </p>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
