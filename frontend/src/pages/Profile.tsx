import { useState } from 'react'
import PageContainer from '../components/layout/PageContainer'
import UserSwitcher from '../components/auth/UserSwitcher'
import { useAuth } from '../contexts/AuthContext'

export default function Profile() {
  const { currentUser, logout } = useAuth()
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  const handleLogout = async () => {
    setIsLoggingOut(true)
    try {
      await logout()
    } catch (error) {
      // Logout handles navigation, errors are unlikely
      setIsLoggingOut(false)
    }
  }

  return (
    <PageContainer>
      <div className="py-8">
        <h1 className="text-4xl font-bold text-text-primary mb-4">Profile</h1>
        <p className="text-text-secondary mb-6">
          Manage your preferences and settings
        </p>

        <div className="space-y-4">
          {/* User Info Card */}
          <div className="bg-cream-dark rounded-card border border-warm-border p-6">
            <h2 className="text-xl font-semibold text-text-primary mb-4">
              Your Profile
            </h2>
            <div className="space-y-3">
              <div>
                <p className="text-sm text-text-tertiary">Name</p>
                <p className="text-text-primary font-medium">{currentUser?.name}</p>
              </div>
              <div>
                <p className="text-sm text-text-tertiary">Email</p>
                <p className="text-text-primary">{currentUser?.email}</p>
              </div>
              <div>
                <p className="text-sm text-text-tertiary">Role</p>
                <p className="text-text-primary capitalize">{currentUser?.role}</p>
              </div>
              {currentUser?.dietary_profile && currentUser.dietary_profile.length > 0 && (
                <div>
                  <p className="text-sm text-text-tertiary">Dietary Profile</p>
                  <p className="text-text-primary">
                    {currentUser.dietary_profile.join(', ')}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* User Switcher (only for coordinators) */}
          <UserSwitcher />

          {/* Logout Button */}
          <div className="bg-cream-dark rounded-card border border-warm-border p-6">
            <h2 className="text-xl font-semibold text-text-primary mb-4">
              Account Actions
            </h2>
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
    </PageContainer>
  )
}
