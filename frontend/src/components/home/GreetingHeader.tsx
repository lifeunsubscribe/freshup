import { useCurrentUser } from '../../api'

/**
 * GreetingHeader displays personalized greeting based on time of day
 *
 * Features:
 * - Time-based greeting: "Good morning/afternoon/evening"
 * - Shows logged-in user's display name
 * - Displays current date in readable format
 * - Morning: 5:00-11:59, Afternoon: 12:00-16:59, Evening: 17:00-4:59
 */
export default function GreetingHeader() {
  const { data: user } = useCurrentUser()

  // Get time-based greeting
  const getGreeting = () => {
    const hour = new Date().getHours()
    if (hour >= 5 && hour < 12) return 'morning'
    if (hour >= 12 && hour < 17) return 'afternoon'
    return 'evening'
  }

  // Format current date
  const formatDate = () => {
    const now = new Date()
    return now.toLocaleDateString('en-US', {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
    })
  }

  const greeting = getGreeting()
  const displayName = user?.display_name || user?.username || 'there'

  return (
    <div className="mb-2">
      <h1 className="text-[22px] font-medium text-text-primary leading-tight">
        Good {greeting}, {displayName}
        <span className="text-olive">.</span>
      </h1>
      <p className="text-sm text-text-secondary mt-1">{formatDate()}</p>
    </div>
  )
}
