import { useState, useEffect } from 'react'
import { useCurrentUser } from '../../api'

/**
 * GreetingHeader displays personalized greeting based on time of day
 *
 * Features:
 * - Time-based greeting: "Good morning/afternoon/evening"
 * - Shows logged-in user's display name
 * - Displays current date in readable format
 * - Morning: 5:00-11:59, Afternoon: 12:00-16:59, Evening: 17:00-4:59
 * - Automatically refreshes when app regains visibility or every minute
 */
export default function GreetingHeader() {
  const { data: user, isLoading, isError } = useCurrentUser()

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

  // State for greeting and date to enable automatic refresh
  const [greeting, setGreeting] = useState(() => getGreeting())
  const [formattedDate, setFormattedDate] = useState(() => formatDate())

  // Update greeting and date values
  const updateGreetingAndDate = () => {
    setGreeting(getGreeting())
    setFormattedDate(formatDate())
  }

  // Refresh on visibility change (when user returns to app)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        updateGreetingAndDate()
      }
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [])

  // Refresh every minute to catch time boundary changes (e.g., 11:59 AM → 12:00 PM, midnight date change)
  useEffect(() => {
    const intervalId = setInterval(updateGreetingAndDate, 60000) // 60000ms = 1 minute
    return () => {
      clearInterval(intervalId)
    }
  }, [])

  // Handle loading and error states for user data
  const getDisplayName = () => {
    if (isLoading) return '...'
    if (isError) return 'there'
    return user?.display_name || user?.username || 'there'
  }

  const displayName = getDisplayName()

  return (
    <div className="mb-2">
      <h1 className="text-[22px] font-medium text-text-primary leading-tight">
        Good {greeting}, {displayName}
        <span className="text-olive">.</span>
      </h1>
      <p className="text-sm text-text-secondary mt-1">{formattedDate}</p>
    </div>
  )
}
