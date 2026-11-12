import { useAuth } from '../../contexts/AuthContext'
import { UserRole } from '../../api/types'
import { useSourceHealth } from '../../api/hooks/useSourceHealth'
import SourceHealthRow from './SourceHealthRow'

export default function SourceHealthSection() {
  const { currentUser } = useAuth()

  if (!currentUser || currentUser.role !== UserRole.COORDINATOR) {
    return null
  }

  return <SourceHealthContent />
}

function SourceHealthContent() {
  const { data: statuses, isLoading, isError } = useSourceHealth()

  return (
    <div id="recipe-sources" className="bg-white rounded-card border border-warm-border p-6">
      <h2 className="text-xl font-medium text-text-primary mb-4">Recipe sources.</h2>

      {isError && (
        <p className="text-[14px] text-mocha">Could not read source status.</p>
      )}

      {!isError && (
        <div className="rounded-card border border-warm-border overflow-hidden">
          {isLoading && !statuses ? (
            // Show two placeholder loading rows while query is in-flight
            <>
              {(['hellofresh', 'kitchen_sanctuary'] as const).map((s) => (
                <SourceHealthRow
                  key={s}
                  source={{ source_type: s, status: 'never_checked', checked_at: null, failing_since: null, detail: null, import_mode: null }}
                  isLoading={true}
                />
              ))}
            </>
          ) : (
            statuses?.map((s) => (
              <SourceHealthRow key={s.source_type} source={s} />
            ))
          )}
        </div>
      )}
    </div>
  )
}
