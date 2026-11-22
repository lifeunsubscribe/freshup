import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import Sheet from '../ui/Sheet'
import { useSendFeedback } from '../../api/hooks/useFeedback'
import type { FeedbackKind } from '../../api/types'
import { FEEDBACK_KINDS } from '../../utils/feedbackKinds'

/** The API's limit on a note's length. */
const MAX_LENGTH = 4000

interface FeedbackSheetProps {
  open: boolean
  onClose: () => void
}

/**
 * A note to the developer, sent from the account menu. It is stored with who
 * sent it and which page they were on, and read back on the Profile page.
 */
export default function FeedbackSheet({ open, onClose }: FeedbackSheetProps) {
  const { pathname } = useLocation()
  const send = useSendFeedback()
  const [message, setMessage] = useState('')
  const [kind, setKind] = useState<FeedbackKind>('wrong-info')
  const [sent, setSent] = useState(false)
  const reset = send.reset

  // Each opening starts clean; a note already sent is not shown again.
  // Only on the change from closed to open, whatever else re-renders.
  const wasOpen = useRef(false)
  useEffect(() => {
    if (open && !wasOpen.current) {
      setSent(false)
      reset()
    }
    wasOpen.current = open
  }, [open, reset])

  const trimmed = message.trim()

  function handleSend() {
    send.mutate(
      { message: trimmed, page: pathname, kind },
      {
        onSuccess: () => {
          setMessage('')
          setSent(true)
        },
      }
    )
  }

  return (
    <Sheet
      open={open}
      onClose={onClose}
      title="Send feedback to the developer"
      footer={
        sent ? (
          <button
            onClick={onClose}
            className="w-full h-11 rounded-button bg-olive text-white text-[15px] font-medium"
          >
            Done
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={trimmed.length === 0 || send.isPending}
            className="w-full h-11 rounded-button bg-olive text-white text-[15px] font-medium disabled:opacity-50"
          >
            {send.isPending ? 'Sending...' : 'Send'}
          </button>
        )
      }
    >
      <div className="px-4 pt-2 pb-4 space-y-3">
        {sent ? (
          <p role="status" className="text-[14px] text-text-primary">
            Thanks. Your note is saved for review.
          </p>
        ) : (
          <>
            <fieldset>
              <legend className="text-[13px] text-text-secondary mb-2">What is it about?</legend>
              <div className="flex flex-wrap gap-2">
                {FEEDBACK_KINDS.map((option) => (
                  <button
                    key={option.kind}
                    type="button"
                    onClick={() => setKind(option.kind)}
                    aria-pressed={kind === option.kind}
                    className={`px-3 py-1.5 rounded-pill text-[13px] border ${
                      kind === option.kind
                        ? 'bg-olive text-white border-olive'
                        : 'bg-white text-text-secondary border-warm-btn-border'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </fieldset>
            <label htmlFor="feedback-message" className="block text-[13px] text-text-secondary">
              {kind === 'wrong-info'
                ? 'What is wrong, and where? A wrong amount, an odd name, a missing picture, a recipe in the wrong place. The page you are on is saved with your note.'
                : 'What is working, what is not, what you wish it did. The page you are on is saved with your note.'}
            </label>
            <textarea
              id="feedback-message"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              maxLength={MAX_LENGTH}
              rows={5}
              className="w-full rounded-input border border-warm-border bg-white p-3 text-[14px] text-text-primary"
            />
            {send.isError && (
              <p role="alert" className="text-[13px] text-terra-dark">
                Could not send that. Try again.
              </p>
            )}
          </>
        )}
      </div>
    </Sheet>
  )
}
