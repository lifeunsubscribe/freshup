import { Camera } from 'lucide-react'

interface ScanReceiptTabProps {
  onSwitchToList: () => void
}

/**
 * ScanReceiptTab component - Phase 4 readiness placeholder
 *
 * Features:
 * - Camera icon (32px)
 * - "Coming in Phase 4" message
 * - Fallback button to switch to "From list" tab
 * - Warm, cozy messaging (not clinical)
 */
export default function ScanReceiptTab({ onSwitchToList }: ScanReceiptTabProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-6">
      {/* Camera icon container */}
      <div className="w-16 h-16 rounded-lg bg-cream-icon flex items-center justify-center mb-4">
        <Camera className="w-8 h-8 text-text-secondary" />
      </div>

      {/* Heading */}
      <h2 className="text-xl font-medium text-text-primary mb-2 text-center">
        Receipt scanning coming soon
      </h2>

      {/* Description */}
      <p className="text-sm text-text-secondary text-center mb-6 max-w-md">
        In Phase 4, you'll be able to scan or upload receipts to automatically add items to your pantry. For now, use your grocery list below.
      </p>

      {/* Fallback button */}
      <button
        onClick={onSwitchToList}
        className="px-6 py-3 bg-olive text-white rounded-button font-medium hover:bg-olive-dark transition-colors"
        type="button"
      >
        Use grocery list instead
      </button>
    </div>
  )
}
