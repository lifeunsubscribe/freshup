import { useState } from 'react'
import { UserResponse } from '../../api/types'

interface ProfileHeaderProps {
  user: UserResponse
  onLogout: () => Promise<void>
}

/**
 * ProfileHeader component displaying user info and logout action
 *
 * Features:
 * - User name display
 * - Role badge (coordinator/member) with color coding
 * - Logout button with loading state
 * - Error handling for logout failures
 */
export default function ProfileHeader({ user, onLogout }: ProfileHeaderProps) {
  const [isLoggingOut, setIsLoggingOut] = useState(false)
  const [logoutError, setLogoutError] = useState<string | null>(null)

  const handleLogout = async () => {
    setIsLoggingOut(true)
    setLogoutError(null)
    try {
      await onLogout()
    } catch (error) {
      if (error instanceof Error) {
        setLogoutError(error.message)
      } else {
        setLogoutError('Failed to log out. Please try again.')
      }
      setIsLoggingOut(false)
    }
  }

  return (
    <div className="bg-white rounded-card border border-warm-border p-6">
      <div className="flex items-start justify-between">
        <div className="space-y-3">
          <div>
            <h2 className="text-2xl font-medium text-text-primary">{user.name}</h2>
            <p className="text-sm text-text-tertiary mt-1">{user.email}</p>
          </div>

          <div>
            <span
              className={`inline-block px-3 py-1 text-sm font-medium rounded-[6px] ${
                user.role === 'coordinator'
                  ? 'bg-olive text-cream'
                  : 'bg-cream-dark text-text-primary border border-warm-border'
              }`}
            >
              {user.role === 'coordinator' ? 'Coordinator' : 'Member'}
            </span>
          </div>
        </div>

        <div className="space-y-2">
          {logoutError && (
            <div className="rounded-button border border-terra bg-terra/10 p-3 max-w-xs">
              <p className="text-sm text-terra-dark">{logoutError}</p>
            </div>
          )}
          <button
            onClick={handleLogout}
            disabled={isLoggingOut}
            className="px-6 py-2 rounded-button bg-terra text-cream font-medium hover:bg-terra-dark focus:outline-none focus:ring-2 focus:ring-terra focus:ring-offset-2 focus:ring-offset-cream disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoggingOut ? 'Logging out...' : 'Log out'}
          </button>
        </div>
      </div>
    </div>
  )
}
