import { ReactNode } from 'react'

type PillVariant = 'default' | 'success' | 'warning' | 'alert'

interface PillProps {
  children: ReactNode
  variant?: PillVariant
}

/**
 * Pill component for status badges and labels
 *
 * Variants:
 * - default: Cream background with primary text (neutral state)
 * - success: Olive background with cream text (positive state)
 * - warning: Mocha background with cream text (caution state)
 * - alert: Terra background with cream text (attention state)
 *
 * Border radius: 6px (within design system 4-6px spec)
 */
export default function Pill({ children, variant = 'default' }: PillProps) {
  const variantStyles: Record<PillVariant, string> = {
    default: 'bg-cream text-text-primary border border-warm-border',
    success: 'bg-olive text-cream',
    warning: 'bg-mocha text-cream',
    alert: 'bg-terra text-cream',
  }

  return (
    <span
      className={`inline-block px-3 py-1 text-sm font-medium rounded-[6px] ${variantStyles[variant]}`}
    >
      {children}
    </span>
  )
}
