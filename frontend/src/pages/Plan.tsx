import PageContainer from '../components/layout/PageContainer'

export default function Plan() {
  return (
    <PageContainer>
      <div className="py-8">
        <h1 className="text-4xl font-bold text-text-primary mb-4">Meal Plan</h1>

        <div className="bg-cream-dark rounded-card border border-warm-border p-8 text-center">
          <div className="max-w-md mx-auto">
            <div className="text-6xl mb-4">🗓️</div>
            <h2 className="text-2xl font-semibold text-text-primary mb-3">
              Coming in Phase 3
            </h2>
            <p className="text-text-secondary">
              Democratic meal planning with household voting, recipe suggestions,
              and auto-scaling will be available in Phase 3.
            </p>
          </div>
        </div>
      </div>
    </PageContainer>
  )
}
