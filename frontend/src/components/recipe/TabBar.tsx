type TabType = 'ingredients' | 'cook' | 'nutrition'

interface TabBarProps {
  activeTab: TabType
  onTabChange: (tab: TabType) => void
}

/**
 * TabBar component for recipe detail navigation
 *
 * Features:
 * - Three tabs: Ingredients | Cook & enjoy! | Nutrition
 * - Active tab indicated with olive underline
 * - Horizontal scroll on mobile if needed
 */
export default function TabBar({ activeTab, onTabChange }: TabBarProps) {
  const tabs: Array<{ id: TabType; label: string }> = [
    { id: 'ingredients', label: 'Ingredients' },
    { id: 'cook', label: 'Cook & enjoy!' },
    { id: 'nutrition', label: 'Nutrition' },
  ]

  return (
    <div className="border-b border-warm-border mb-6">
      <div className="flex gap-6 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`
              pb-3 px-1 text-sm font-medium whitespace-nowrap transition-colors
              ${activeTab === tab.id
                ? 'text-olive border-b-2 border-olive'
                : 'text-text-secondary hover:text-text-primary'
              }
            `}
            aria-label={tab.label}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  )
}

export type { TabType }
