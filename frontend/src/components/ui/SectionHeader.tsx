import { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

interface SectionHeaderProps {
  children: ReactNode
  linkTo?: string
  linkText?: string
}

/**
 * SectionHeader renders medium section headings with the signature olive period
 * Typography: 15px / font-medium (500)
 * Usage: <SectionHeader>Fresh Items</SectionHeader> → "Fresh Items."
 * Optional "See all" link can be added via linkTo and linkText props
 */
export default function SectionHeader({ children, linkTo, linkText = 'See all' }: SectionHeaderProps) {
  return (
    <div className="flex items-center justify-between">
      <h2 className="text-[15px] font-medium text-text-primary leading-tight">
        {children}
        <span className="text-olive">.</span>
      </h2>
      {linkTo && (
        <Link
          to={linkTo}
          className="flex items-center gap-1 text-xs text-olive hover:text-olive-dark transition-colors"
        >
          {linkText}
          <ChevronRight size={14} />
        </Link>
      )}
    </div>
  )
}
