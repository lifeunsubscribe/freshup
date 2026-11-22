import { useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import Sheet from '../ui/Sheet'
import { useSendFeedback } from '../../api/hooks/useFeedback'

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
      { message: trimmed, page: pathname },
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
            <label htmlFor="feedback-message" className="block text-[13px] text-text-secondary">
              What is working, what is not, what you wish it did. It is saved along with the page
              you are on.
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
