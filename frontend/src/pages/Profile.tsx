import PageContainer from '../components/layout/PageContainer'
import PageTitle from '../components/ui/PageTitle'
import UserSwitcher from '../components/auth/UserSwitcher'
import ProfileHeader from '../components/profile/ProfileHeader'
import DietarySection from '../components/profile/DietarySection'
import AllergiesSection from '../components/profile/AllergiesSection'
import TastePreferencesSection from '../components/profile/TastePreferencesSection'
import SubstitutionsSection from '../components/profile/SubstitutionsSection'
import SourceHealthSection from '../components/profile/SourceHealthSection'
import FeedbackSection from '../components/profile/FeedbackSection'
import { useAuth } from '../contexts/AuthContext'

/**
 * Profile page for managing user preferences and settings
 *
 * Features:
 * - ProfileHeader: user info, role badge, logout
 * - DietarySection: multi-select dietary preferences
 * - AllergiesSection: tag input for allergies
 * - TastePreferencesSection: segmented-control taste map (replaces DislikedIngredientsSection)
 * - SubstitutionsSection: CRUD for ingredient substitution preferences
 * - FeedbackSection: notes sent from the account menu (coordinators only)
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
        <PageTitle>Profile</PageTitle>
        <p className="text-text-secondary mb-6 mt-2">
          Manage your preferences and settings
        </p>

        <div className="space-y-6">
          {/* Profile Header: name, role, logout */}
          <ProfileHeader user={currentUser} onLogout={logout} />

          {/* Dietary Preferences */}
          <DietarySection currentProfiles={currentUser.dietary_profile} />

          {/* Allergies */}
          <AllergiesSection currentAllergies={currentUser.allergies} />

          {/* Taste Preferences */}
          <TastePreferencesSection currentTastePreferences={currentUser.taste_preferences} />

          {/* Substitution Preferences */}
          <SubstitutionsSection />

          {/* Recipe source health (only for coordinators) */}
          <SourceHealthSection />

          {/* Notes sent with "Send feedback" (only for coordinators) */}
          <FeedbackSection />

          {/* User Switcher (only for coordinators) */}
          <UserSwitcher />
        </div>
      </div>
    </PageContainer>
  )
}
