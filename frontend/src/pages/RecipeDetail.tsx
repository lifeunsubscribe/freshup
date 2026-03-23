import { useParams } from 'react-router-dom'
import PageContainer from '../components/layout/PageContainer'

export default function RecipeDetail() {
  const { id } = useParams<{ id: string }>()

  return (
    <PageContainer>
      <div className="py-8">
        <h1 className="text-4xl font-bold text-text-primary mb-4">Recipe Detail</h1>
        <p className="text-text-secondary mb-6">
          Recipe ID: {id}
        </p>

        <div className="bg-cream-dark rounded-card border border-warm-border p-6">
          <p className="text-text-secondary">
            Recipe ingredients, steps, and nutritional information will appear here.
          </p>
        </div>
      </div>
    </PageContainer>
  )
}
