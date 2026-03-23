import PageContainer from '../components/layout/PageContainer'

export default function Profile() {
  return (
    <PageContainer>
      <div className="py-8">
        <h1 className="text-4xl font-bold text-text-primary mb-4">Profile</h1>
        <p className="text-text-secondary mb-6">
          Manage your preferences and settings
        </p>

        <div className="bg-cream-dark rounded-card border border-warm-border p-6">
          <p className="text-text-secondary">
            User profile management with dietary preferences, allergies, and favorite ingredients coming soon.
          </p>
        </div>
      </div>
    </PageContainer>
  )
}
