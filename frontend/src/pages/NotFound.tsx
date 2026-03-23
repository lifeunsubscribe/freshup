import { Link } from 'react-router-dom'
import PageContainer from '../components/layout/PageContainer'

export default function NotFound() {
  return (
    <PageContainer>
      <div className="py-8 text-center">
        <h1 className="text-4xl font-bold text-text-primary mb-4">404</h1>
        <p className="text-lg text-text-secondary mb-8">
          Page not found
        </p>
        <Link
          to="/"
          className="inline-block bg-olive text-cream px-6 py-2 rounded-lg hover:bg-olive/90 transition-colors"
        >
          Go Home
        </Link>
      </div>
    </PageContainer>
  )
}
