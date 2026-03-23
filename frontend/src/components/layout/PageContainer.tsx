import { ReactNode } from 'react'

interface PageContainerProps {
  children: ReactNode
}

/**
 * PageContainer provides consistent horizontal padding for all pages
 * and reserves space for the fixed bottom navigation
 */
export default function PageContainer({ children }: PageContainerProps) {
  return (
    <div className="px-4 pb-20 min-h-screen bg-cream">
      {children}
    </div>
  )
}
