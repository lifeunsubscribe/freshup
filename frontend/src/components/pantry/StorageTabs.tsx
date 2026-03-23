import { StorageLocation } from '../../api/types'

type StorageTab = 'all' | StorageLocation

interface StorageTabsProps {
  activeTab: StorageTab
  onTabChange: (tab: StorageTab) => void
}

/**
 * StorageTabs component for filtering pantry inventory by storage location
 *
 * Features:
 * - Four tabs: All | Fridge | Freezer | Pantry
 * - Active tab: olive background with cream text
 * - Inactive tabs: cream background with primary text
 * - Applies storage location filter to inventory list
 */
export default function StorageTabs({ activeTab, onTabChange }: StorageTabsProps) {
  const tabs: { value: StorageTab; label: string }[] = [
    { value: 'all', label: 'All' },
    { value: StorageLocation.FRIDGE, label: 'Fridge' },
    { value: StorageLocation.FREEZER, label: 'Freezer' },
    { value: StorageLocation.PANTRY, label: 'Pantry' },
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
