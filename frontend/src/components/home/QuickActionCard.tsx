import { ReactNode } from 'react'

export interface QuickActionCardProps {
  icon: ReactNode
  title: string
  description: string
  onClick: () => void
}

/**
 * QuickActionCard component for home screen quick actions grid
 *
 * Features:
 * - Icon container: 32x32px square with 8px border radius and cream background
 * - Icon: 18px, olive green stroke (styled by parent)
 * - Title: 14px font weight 500
 * - Description: 12px secondary text color
 * - Card: white background with 12px border radius
 * - Hover state: background shifts to #f4f2ea
 * - Fully accessible with semantic button element
 * - 2-column grid layout handled by parent container
 *
 * @example
 * ```tsx
 * import { Plus } from 'lucide-react'
 *
 * <QuickActionCard
 *   icon={<Plus size={18} className="stroke-olive" strokeWidth={2} />}
 *   title="Add Item"
 *   description="Add a new grocery item"
 *   onClick={() => navigate('/grocery/add')}
 * />
 * ```
 */
export default function QuickActionCard({
  icon,
  title,
  description,
  onClick,
}: QuickActionCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full bg-white rounded-card p-4 text-left transition-colors duration-200 hover:bg-[#f4f2ea] focus:outline-none focus:ring-2 focus:ring-olive focus:ring-offset-2"
    >
      {/* Icon container: 32x32px, rounded 8px, cream background */}
      <div className="w-8 h-8 rounded-button bg-cream flex items-center justify-center mb-3">
        {icon}
      </div>

      {/* Title: 14px/500 */}
      <h3 className="text-sm font-medium text-text-primary mb-1">{title}</h3>

      {/* Description: 12px secondary text */}
      <p className="text-xs text-text-secondary">{description}</p>
    </button>
  )
}
