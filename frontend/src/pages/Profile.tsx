import PageContainer from '../components/layout/PageContainer'
import UserSwitcher from '../components/auth/UserSwitcher'
import ProfileHeader from '../components/profile/ProfileHeader'
import DietarySection from '../components/profile/DietarySection'
import AllergiesSection from '../components/profile/AllergiesSection'
import DislikedIngredientsSection from '../components/profile/DislikedIngredientsSection'
import SubstitutionsSection from '../components/profile/SubstitutionsSection'
import { useAuth } from '../contexts/AuthContext'

/**
 * Profile page for managing user preferences and settings
 *
 * Features:
 * - ProfileHeader: user info, role badge, logout
 * - DietarySection: multi-select dietary preferences
 * - AllergiesSection: tag input for allergies
 * - DislikedIngredientsSection: tag input for disliked ingredients
 * - SubstitutionsSection: CRUD for ingredient substitution preferences
 * - UserSwitcher: switch between household members (coordinators only)
 */
export default function Profile() {
  const { currentUser, logout } = useAuth()

  if (!currentUser) {
    return (
      <PageContainer>
        <div className="py-8">
          <p className="text-text-secondary">Loading profile...</p>
        </div>
      </PageContainer>
    )
  }

  return (
    <PageContainer>
      <div className="py-8">
        <h1 className="text-4xl font-medium text-text-primary mb-4">Profile</h1>
        <p className="text-text-secondary mb-6">
          Manage your preferences and settings
        </p>

        <div className="space-y-6">
          {/* Profile Header: name, role, logout */}
          <ProfileHeader user={currentUser} onLogout={logout} />

          {/* Dietary Preferences */}
          <DietarySection currentProfiles={currentUser.dietary_profile} />

          {/* Allergies */}
          <AllergiesSection currentAllergies={currentUser.allergies} />

          {/* Disliked Ingredients */}
          <DislikedIngredientsSection currentDisliked={currentUser.disliked_ingredients} />

          {/* Substitution Preferences */}
          <SubstitutionsSection />

          {/* User Switcher (only for coordinators) */}
          <UserSwitcher />
        </div>
      </div>
    </PageContainer>
  )
}
