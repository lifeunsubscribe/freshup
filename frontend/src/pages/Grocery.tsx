import PageContainer from '../components/layout/PageContainer'

export default function Grocery() {
  return (
    <PageContainer>
      <div className="py-8">
        <h1 className="text-4xl font-medium text-text-primary mb-4">Grocery List</h1>
        <p className="text-text-secondary mb-6">
          Shared shopping list for the household
        </p>

        <div className="bg-white rounded-card border border-warm-border p-6">
          <p className="text-text-secondary">
            Collaborative grocery list with per-store grouping coming soon.
          </p>
        </div>
      </div>
    </PageContainer>
  )
}
