import { ReactNode, useEffect, useRef, useId } from 'react'
import { createPortal } from 'react-dom'

// Elements that can receive keyboard focus (excludes tabIndex="-1")
const FOCUSABLE_SELECTORS = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

interface SheetProps {
  open: boolean
  onClose: () => void
  title: string
  children: ReactNode
  footer?: ReactNode
  ariaLabel?: string
}

export default function Sheet({ open, onClose, title, children, footer, ariaLabel }: SheetProps) {
  const titleId = useId()
  const panelRef = useRef<HTMLDivElement>(null)
  const prevFocusRef = useRef<HTMLElement | null>(null)

  // Move focus into the sheet on open; return it to the trigger on close
  useEffect(() => {
    if (open) {
      prevFocusRef.current = document.activeElement as HTMLElement
      const firstFocusable = panelRef.current?.querySelector<HTMLElement>(FOCUSABLE_SELECTORS)
      ;(firstFocusable ?? panelRef.current)?.focus()
    } else if (prevFocusRef.current) {
      prevFocusRef.current.focus()
      prevFocusRef.current = null
    }
  }, [open])

  // Escape closes; Tab/Shift+Tab cycles within the panel
  useEffect(() => {
    if (!open) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
        return
      }
      if (e.key !== 'Tab') return
      const panel = panelRef.current
      if (!panel) return
      const focusable = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTORS))
      if (focusable.length === 0) return
      const first = focusable[0]
      const last = focusable[focusable.length - 1]
      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault()
          last.focus()
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault()
          first.focus()
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, onClose])

  // Lock body scroll while sheet is open
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-end justify-center"
      onClick={onClose}
    >
      {/* Scrim */}
      <div className="absolute inset-0 bg-text-primary/30" aria-hidden="true" />

      {/* Sheet panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        {...(ariaLabel ? { 'aria-label': ariaLabel } : {})}
        tabIndex={-1}
        className="relative w-full max-w-[480px] max-h-[85vh] bg-cream rounded-t-card-lg flex flex-col overflow-hidden outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Visual drag handle (decorative) */}
        <div className="w-9 h-1 rounded-full bg-warm mx-auto mt-2 shrink-0" aria-hidden="true" />

        {/* Header: title and close affordance */}
        <div className="flex items-center justify-between px-4 py-3 shrink-0">
          <h2
            id={titleId}
            className="text-[22px] font-medium leading-[1.3] text-text-primary"
          >
            {title}<span className="text-olive" aria-hidden="true">.</span>
          </h2>
          <button
            onClick={onClose}
            className="w-11 h-11 flex items-center justify-center text-text-secondary -mr-2"
            aria-label="Close"
          >
            <svg
              className="w-5 h-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto">
          {children}
        </div>

        {/* Sticky footer — stays visible while content scrolls */}
        {footer && (
          <div className="shrink-0 border-t border-warm-border">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body
  )
}
