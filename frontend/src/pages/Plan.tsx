import { useState } from 'react'
import { Link } from 'react-router-dom'
import PageContainer from '../components/layout/PageContainer'
import PageTitle from '../components/ui/PageTitle'
import SectionHeader from '../components/ui/SectionHeader'
import PlanCard from '../components/plan/PlanCard'
import { useAuth } from '../contexts/AuthContext'
import { addDays, todayStr, weekStartOf, weekTitle } from '../utils/week'

/** How many sample weeks show under the current one before "Show another week". */
const UPCOMING_WEEKS = 2

/**
 * Plan page: the current week as one large plan card, then sample weeks for
 * planning ahead. Each card opens its week in the editor at /plan/:weekStart.
 */
export default function Plan() {
  const { currentUser } = useAuth()
  const thisWeek = weekStartOf(new Date())
  const today = todayStr()
  const [upcomingCount, setUpcomingCount] = useState(UPCOMING_WEEKS)
  const upcoming = Array.from({ length: upcomingCount }, (_, i) => addDays(thisWeek, 7 * (i + 1)))

  return (
    <PageContainer>
      <div className="py-6 space-y-4">
        <PageTitle>Plan</PageTitle>

        <PlanCard
          weekStart={thisWeek}
          title="This week"
          ownerName={currentUser?.name}
          today={today}
          size="large"
          autoFill
        />

        <div className="pt-2">
          <SectionHeader subtitle="Sample weeks, ready if you want to plan ahead.">
            Coming up
          </SectionHeader>
        </div>

        {upcoming.map((weekStart) => (
          <PlanCard
            key={weekStart}
            weekStart={weekStart}
            title={weekTitle(weekStart, thisWeek)}
            ownerName={currentUser?.name}
            today={today}
            size="compact"
            autoFill
          />
        ))}

        <div className="flex items-center justify-between">
          <button
            onClick={() => setUpcomingCount((n) => n + 1)}
            className="px-3 h-9 rounded-button-sm border border-warm-btn-border bg-white text-text-secondary text-[13px] font-medium"
          >
            Show another week
          </button>
          <Link to={`/plan/${addDays(thisWeek, -7)}`} className="text-[13px] text-olive">
            Last week
          </Link>
        </div>
      </div>
    </PageContainer>
  )
}
