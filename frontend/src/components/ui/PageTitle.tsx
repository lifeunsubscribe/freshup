import { ReactNode } from 'react'

interface PageTitleProps {
  children: ReactNode
}

/**
 * PageTitle renders large page headings with the signature olive period
 * Typography: 22px / font-medium (500)
 * Usage: <PageTitle>Pantry</PageTitle> → "Pantry."
 */
export default function PageTitle({ children }: PageTitleProps) {
  return (
    <h1 className="text-[22px] font-medium text-text-primary leading-tight">
      {children}
      <span className="text-olive">.</span>
    </h1>
  )
}
