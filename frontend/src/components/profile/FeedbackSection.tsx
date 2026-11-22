import { useAuth } from '../../contexts/AuthContext'
import { UserRole } from '../../api/types'
import { useFeedbackList } from '../../api/hooks/useFeedback'
import { feedbackKindLabel } from '../../utils/feedbackKinds'

/** Notes sent from the account menu's "Send feedback", newest first. Coordinators only. */
export default function FeedbackSection() {
  const { currentUser } = useAuth()

  if (!currentUser || currentUser.role !== UserRole.COORDINATOR) {
    return null
  }

  return <FeedbackContent />
}

function when(createdAt: string): string {
  const date = new Date(createdAt)
  return Number.isNaN(date.getTime())
    ? ''
    : date.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function FeedbackContent() {
  const { data: notes, isLoading, isError } = useFeedbackList()

  return (
    <div id="feedback" className="bg-white rounded-card border border-warm-border p-6">
      <h2 className="text-xl font-medium text-text-primary mb-4">Feedback.</h2>

      {isLoading && <p className="text-[14px] text-text-secondary">Loading...</p>}
      {isError && <p className="text-[14px] text-mocha">Could not read feedback.</p>}
      {notes && notes.length === 0 && (
        <p className="text-[14px] text-text-secondary">
          Nothing yet. Notes sent with "Send feedback" in the account menu show up here.
        </p>
      )}

      {notes && notes.length > 0 && (
        <ul className="space-y-3">
          {notes.map((note) => (
            <li key={note.id} className="rounded-card border border-warm-border p-3">
              <p className="text-[11px] font-medium uppercase tracking-wide text-olive-dark mb-1">
                {feedbackKindLabel(note.kind)}
              </p>
              <p className="text-[14px] text-text-primary whitespace-pre-wrap">{note.message}</p>
              <p className="mt-1.5 text-[12px] text-text-tertiary">
                {[note.user_name, when(note.created_at), note.page].filter(Boolean).join(' · ')}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
