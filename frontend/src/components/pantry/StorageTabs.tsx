import { StorageLocation } from '../../api/types'
import { getEnumOptions } from '../../utils/enumUtils'

type StorageTab = 'all' | StorageLocation

interface StorageTabsProps {
  activeTab: StorageTab
  onTabChange: (tab: StorageTab) => void
}

/**
 * StorageTabs component for filtering pantry inventory by storage location
 *
 * Features:
 * - Dynamically generated tabs from StorageLocation enum (All + all enum values)
 * - Active tab: olive background with cream text
 * - Inactive tabs: cream background with primary text
 * - Applies storage location filter to inventory list
 */
export default function StorageTabs({ activeTab, onTabChange }: StorageTabsProps) {
  // Generate tabs dynamically from enum
  const tabs: { value: StorageTab; label: string }[] = [
    { value: 'all', label: 'All' },
    ...getEnumOptions(StorageLocation).map((option) => ({
      value: option.value as StorageLocation,
      label: option.label,
    })),
  ]

  return (
    <div className="flex gap-2 mb-6" role="tablist">
      {tabs.map((tab) => {
        const isActive = activeTab === tab.value

        return (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onTabChange(tab.value)}
            className={`px-4 py-2 text-sm font-medium rounded-[8px] transition-colors ${
              isActive
                ? 'bg-olive text-cream'
                : 'bg-cream text-text-primary border border-warm-border hover:bg-cream-dark'
            }`}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
