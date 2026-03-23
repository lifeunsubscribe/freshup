import PageContainer from '../components/layout/PageContainer'
import { useAuth } from '../contexts/AuthContext'

export default function Home() {
  const { currentUser } = useAuth()

  return (
    <PageContainer>
      <div className="py-8">
        <h1 className="text-4xl font-bold text-text-primary mb-4">FreshUp</h1>
        <p className="text-lg text-text-secondary mb-8">
          Privacy-First Kitchen Management System
        </p>

        <div className="space-y-4">
          <div className="bg-cream-dark rounded-card border border-warm-border p-6">
            <h2 className="text-2xl font-semibold text-text-primary mb-2">
              Welcome, {currentUser?.name}
            </h2>
            <p className="text-text-secondary">
              Your kitchen dashboard is ready. Quick actions and meal suggestions will appear here.
            </p>
          </div>
        </div>
      </div>
    </PageContainer>
  )
}
