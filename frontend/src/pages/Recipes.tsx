import PageContainer from '../components/layout/PageContainer'

export default function Recipes() {
  return (
    <PageContainer>
      <div className="py-8">
        <h1 className="text-4xl font-bold text-text-primary mb-4">Recipes</h1>
        <p className="text-text-secondary mb-6">
          Browse and manage your recipe collection
        </p>

        <div className="bg-cream-dark rounded-card border border-warm-border p-6">
          <p className="text-text-secondary">
            Recipe browsing, filtering, and management features coming soon.
          </p>
        </div>
      </div>
    </PageContainer>
  )
}
