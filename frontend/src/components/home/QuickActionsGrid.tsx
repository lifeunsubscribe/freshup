import { useNavigate } from 'react-router-dom'
import { ShoppingBag, Snowflake, Cookie, Search } from 'lucide-react'
import QuickActionCard from './QuickActionCard'

/**
 * QuickActionsGrid displays a 2x2 grid of quick action buttons on the home screen
 *
 * Actions:
 * - "I shopped": Navigate to /shopped (bulk purchase flow)
 * - "I froze/thawed": Navigate to /pantry (storage management)
 * - "I ate snacks": Navigate to /pantry with category filter (snack tracking)
 * - "What's around?": Navigate to /pantry (inventory overview)
 */
export default function QuickActionsGrid() {
  const navigate = useNavigate()

  return (
    <div className="grid grid-cols-2 gap-3">
      <QuickActionCard
        icon={<ShoppingBag size={18} className="stroke-olive" strokeWidth={2} />}
        title="I shopped"
        description="Add groceries to pantry"
        onClick={() => navigate('/shopped')}
      />
      <QuickActionCard
        icon={<Snowflake size={18} className="stroke-olive" strokeWidth={2} />}
        title="I froze/thawed"
        description="Update storage"
        onClick={() => navigate('/pantry')}
      />
      <QuickActionCard
        icon={<Cookie size={18} className="stroke-olive" strokeWidth={2} />}
        title="I ate snacks"
        description="Log consumption"
        onClick={() => navigate('/pantry')}
      />
      <QuickActionCard
        icon={<Search size={18} className="stroke-olive" strokeWidth={2} />}
        title="What's around?"
        description="View all inventory"
        onClick={() => navigate('/pantry')}
      />
    </div>
  )
}
