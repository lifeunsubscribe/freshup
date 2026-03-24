interface StatCardsProps {
  totalItems: number
  expiringSoonCount: number
  lowStockCount: number
}

/**
 * StatCards component displaying pantry statistics
 *
 * Features:
 * - 3-column grid (responsive: stacks on mobile)
 * - Card 1: Total items count
 * - Card 2: Expiring soon count (within 3 days)
 * - Card 3: Low stock count
 * - Cream-dark background with warm-border
 */
export default function StatCards({
  totalItems,
  expiringSoonCount,
  lowStockCount,
}: StatCardsProps) {
  const stats = [
    {
      label: 'Total Items',
      value: totalItems,
      description: 'in pantry',
    },
    {
      label: 'Expiring Soon',
      value: expiringSoonCount,
      description: 'within 3 days',
    },
    {
      label: 'Low Stock',
      value: lowStockCount,
      description: 'staples',
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="bg-cream-dark rounded-card border border-warm-border p-4"
        >
          <div className="text-3xl font-medium text-text-primary mb-1">
            {stat.value}
          </div>
          <div className="text-sm font-medium text-text-primary mb-1">
            {stat.label}
          </div>
          <div className="text-xs text-text-secondary">{stat.description}</div>
        </div>
      ))}
    </div>
  )
}
