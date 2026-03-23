import PageContainer from '../components/layout/PageContainer'
import { PageTitle, SectionHeader, Pill, CategoryLabel } from '../components/ui'

export default function Pantry() {
  return (
    <PageContainer>
      <div className="py-8">
        <PageTitle>Pantry</PageTitle>
        <p className="text-text-secondary mb-6 mt-2">
          Manage your kitchen inventory
        </p>

        <div className="bg-cream-dark rounded-card border border-warm-border p-6 mb-6">
          <SectionHeader>Fresh Items</SectionHeader>
          <div className="mt-4 space-y-3">
            <div className="flex items-center gap-3">
              <CategoryLabel>Produce</CategoryLabel>
              <Pill variant="success">Fresh</Pill>
              <span className="text-text-secondary">Tomatoes (3)</span>
            </div>
            <div className="flex items-center gap-3">
              <CategoryLabel>Dairy</CategoryLabel>
              <Pill variant="warning">Expiring Soon</Pill>
              <span className="text-text-secondary">Milk (1qt)</span>
            </div>
            <div className="flex items-center gap-3">
              <CategoryLabel>Protein</CategoryLabel>
              <Pill variant="alert">Check Date</Pill>
              <span className="text-text-secondary">Ground Beef (1lb)</span>
            </div>
            <div className="flex items-center gap-3">
              <CategoryLabel>Pantry</CategoryLabel>
              <Pill>Stocked</Pill>
              <span className="text-text-secondary">Rice (5lbs)</span>
            </div>
          </div>
        </div>

        <div className="bg-cream-dark rounded-card border border-warm-border p-6">
          <p className="text-text-secondary">
            Full inventory management features for fridge, freezer, and pantry items coming soon.
          </p>
        </div>
      </div>
    </PageContainer>
  )
}
