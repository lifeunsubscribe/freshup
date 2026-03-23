import { Refrigerator, Snowflake, Box, Home } from 'lucide-react'
import { StorageLocation } from '../../api/types'

interface StorageBadgeProps {
  storageLocation: string
  onCycle?: (newLocation: string) => void
  disabled?: boolean
}

/**
 * StorageBadge component displays and cycles through storage locations
 *
 * Features:
 * - Icon + label for each storage type (fridge, freezer, pantry, counter)
 * - Tappable: cycles through storage locations
 * - Cycle order: pantry → fridge → freezer → counter → pantry
 * - 44px touch target for mobile usability
 * - Disabled state when mutation is pending
 */
export default function StorageBadge({
  storageLocation,
  onCycle,
  disabled = false,
}: StorageBadgeProps) {
  // Get the next storage location in the cycle
  const getNextLocation = (current: string): string => {
    const cycle: string[] = [
      StorageLocation.PANTRY,
      StorageLocation.FRIDGE,
      StorageLocation.FREEZER,
      'counter', // Not in enum but used in the app
    ]
    const currentIndex = cycle.indexOf(current)
    const nextIndex = (currentIndex + 1) % cycle.length
    return cycle[nextIndex]
  }

  const handleClick = () => {
    if (!disabled && onCycle) {
      const nextLocation = getNextLocation(storageLocation)
      onCycle(nextLocation)
    }
  }

  // Get icon and label for storage location
  const getStorageDisplay = (location: string) => {
    switch (location) {
      case StorageLocation.FRIDGE:
        return { icon: Refrigerator, label: 'Fridge', color: 'text-mocha' }
      case StorageLocation.FREEZER:
        return { icon: Snowflake, label: 'Freezer', color: 'text-olive' }
      case StorageLocation.PANTRY:
        return { icon: Box, label: 'Pantry', color: 'text-text-secondary' }
      case 'counter':
        return { icon: Home, label: 'Counter', color: 'text-terra' }
      default:
        return { icon: Box, label: location, color: 'text-text-secondary' }
    }
  }

  const { icon: Icon, label, color } = getStorageDisplay(storageLocation)

  return (
    <button
      onClick={handleClick}
      disabled={disabled || !onCycle}
      className={`
        inline-flex items-center gap-1.5 px-2.5 py-1.5
        bg-cream border border-warm-border rounded-[6px]
        text-xs font-medium
        min-h-[44px] touch-manipulation
        transition-all
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:bg-warm-gray active:scale-95'}
        ${!onCycle ? 'cursor-default' : ''}
      `}
      aria-label={onCycle ? `Change storage from ${label}` : `Stored in ${label}`}
      type="button"
    >
      <Icon size={14} className={color} />
      <span className="text-text-primary">{label}</span>
    </button>
  )
}
