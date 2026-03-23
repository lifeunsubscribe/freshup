import { ReactNode } from 'react'

interface SectionHeaderProps {
  children: ReactNode
}

/**
 * SectionHeader renders medium section headings with the signature olive period
 * Typography: 15px / font-medium (500)
 * Usage: <SectionHeader>Fresh Items</SectionHeader> → "Fresh Items."
 */
export default function SectionHeader({ children }: SectionHeaderProps) {
  return (
    <h2 className="text-[15px] font-medium text-text-primary leading-tight">
      {children}
      <span className="text-olive">.</span>
    </h2>
  )
}
