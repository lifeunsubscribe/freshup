import { useState, useRef, useEffect } from 'react'

interface ActionBarProps {
  onCookThis: () => Promise<void>
  onAddToPlan: () => void
  isLoading?: boolean
}

export default function ActionBar({
  onCookThis,
  onAddToPlan,
  isLoading = false,
}: ActionBarProps) {
  const [isCooking, setIsCooking] = useState(false)
  const [cookSuccess, setCookSuccess] = useState(false)
  const cookSuccessTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    return () => {
      if (cookSuccessTimeoutRef.current) clearTimeout(cookSuccessTimeoutRef.current)
    }
  }, [])

  const handleCookThis = async () => {
    if (isCooking || cookSuccess) return
    setIsCooking(true)
    try {
      await onCookThis()
      setCookSuccess(true)
      cookSuccessTimeoutRef.current = setTimeout(() => {
        setCookSuccess(false)
        cookSuccessTimeoutRef.current = null
      }, 2000)
    } catch {
      // error surfaced by parent via banner
    } finally {
      setIsCooking(false)
    }
  }

  return (
    <div className="fixed bottom-0 left-0 right-0 bg-cream border-t border-warm-border shadow-lg z-10">
      <div className="max-w-2xl mx-auto px-4 py-3 flex items-center gap-3">
        {/* I cooked this */}
        <button
          onClick={handleCookThis}
          disabled={isLoading || isCooking}
          className="flex-1 bg-cream text-text-primary font-medium py-3 px-4 rounded-button border-2 border-warm-border hover:bg-cream-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {cookSuccess ? 'Cooked!' : 'I cooked this'}
        </button>

        {/* Add to plan */}
        <button
          onClick={onAddToPlan}
          disabled={isLoading}
          className="flex-1 bg-olive text-cream font-medium py-3 px-4 rounded-button hover:bg-olive-dark transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Add to plan
        </button>
      </div>
    </div>
  )
}
