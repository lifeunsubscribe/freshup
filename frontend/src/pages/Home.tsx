import PageContainer from '../components/layout/PageContainer'
import GreetingHeader from '../components/home/GreetingHeader'
import QuickActionsGrid from '../components/home/QuickActionsGrid'
import ExpirationAlerts from '../components/home/ExpirationAlerts'
import GroceryPreview from '../components/home/GroceryPreview'
import ReadyToEat from '../components/home/ReadyToEat'

/**
 * Home screen - Primary entry point showing triage-first information
 *
 * Sections:
 * 1. Greeting header: "Good [morning/afternoon/evening], [name]" with current date
 * 2. Quick actions grid: 4 common actions in 2x2 grid
 * 3. Expiration alerts: Items expiring within 3 days with inline actions
 * 4. Grocery preview: Count of unpurchased items with link to grocery list
 * 5. Ready to eat: Horizontal carousel of prepared foods
 *
 * All data loads via React Query hooks with loading/error states
 */
export default function Home() {
  return (
    <PageContainer>
      <div className="py-6 space-y-6">
        {/* Greeting header */}
        <GreetingHeader />

        {/* Quick actions grid */}
        <QuickActionsGrid />

        {/* Expiration alerts */}
        <ExpirationAlerts />

        {/* Grocery preview */}
        <GroceryPreview />

        {/* Ready to eat carousel */}
        <ReadyToEat />
      </div>
    </PageContainer>
  )
}
