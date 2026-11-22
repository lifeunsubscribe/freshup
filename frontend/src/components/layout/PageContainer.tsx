import { ReactNode } from 'react'

interface PageContainerProps {
  children: ReactNode
}

/**
 * PageContainer provides consistent horizontal padding for all pages,
 * reserves space for the fixed bottom navigation, and leaves a strip at the
 * top for the account button anchored in the top right corner (ProfileMenu)
 */
export default function PageContainer({ children }: PageContainerProps) {
  return (
    <div className="px-4 pt-9 pb-20 min-h-screen bg-cream">
      {children}
    </div>
  )
}
