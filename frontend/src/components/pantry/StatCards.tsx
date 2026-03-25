interface StatCardsProps {
  totalItems: number
  expiringSoonCount: number
  lowStockCount: number
}

/**
 * StatCards component displaying pantry statistics
 *
 * Features:
 * - Compact horizontal row layout (3 cards)
 * - Card 1: Total items count (no accent)
 * - Card 2: Expiring soon count with terra accent (#c2715a)
 * - Card 3: Low stock count with mocha accent (#a08b6e)
 * - Design system alignment per Section 6 (Pantry)
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
      accentColor: null,
    },
    {
      label: 'Expiring Soon',
      value: expiringSoonCount,
      description: 'within 3 days',
      accentColor: 'terra', // Terra urgency indicator
    },
    {
      label: 'Low Stock',
      value: lowStockCount,
      description: 'staples',
      accentColor: 'mocha', // Mocha warning indicator
    },
  ]

  return (
    <div className="grid grid-cols-3 gap-3 mb-6">
      {stats.map((stat) => (
        <div
          key={stat.label}
          className="bg-white rounded-card border border-warm-border p-3"
        >
          <div
            className={`text-2xl font-medium mb-1 ${
              stat.accentColor === 'terra'
                ? 'text-terra'
                : stat.accentColor === 'mocha'
                  ? 'text-mocha'
                  : 'text-text-primary'
            }`}
          >
            {stat.value}
          </div>
          <div className="text-xs font-medium text-text-primary mb-0.5">
            {stat.label}
          </div>
          <div className="text-[10px] text-text-secondary">{stat.description}</div>
        </div>
      ))}
    </div>
  )
}
