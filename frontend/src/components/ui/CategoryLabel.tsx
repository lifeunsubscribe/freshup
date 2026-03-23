import { ReactNode } from 'react'

interface CategoryLabelProps {
  children: ReactNode
}

/**
 * CategoryLabel renders small uppercase labels for categories
 * Typography: 12px / uppercase / 0.06em letter-spacing
 * Uses tertiary text color for subtle appearance
 * Usage: <CategoryLabel>Produce</CategoryLabel> → "PRODUCE"
 */
export default function CategoryLabel({ children }: CategoryLabelProps) {
  return (
    <span className="text-xs uppercase tracking-[0.06em] text-text-tertiary font-medium">
      {children}
    </span>
  )
}
