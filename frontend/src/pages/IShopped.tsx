import PageContainer from '../components/layout/PageContainer'

export default function IShopped() {
  return (
    <PageContainer>
      <div className="py-8">
        <h1 className="text-4xl font-bold text-text-primary mb-4">I Shopped</h1>
        <p className="text-text-secondary mb-6">
          Add items to your inventory
        </p>

        <div className="bg-cream-dark rounded-card border border-warm-border p-6">
          <p className="text-text-secondary">
            Receipt upload and manual item entry features coming soon.
          </p>
        </div>
      </div>
    </PageContainer>
  )
}
