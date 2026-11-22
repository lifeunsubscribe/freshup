import { useEffect, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { LogOut, UserRound } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'

/**
 * The account button anchored at the top right of every signed-in page.
 * It opens a small menu: who is signed in, their profile (preferences,
 * allergies, household), and log out.
 */
export default function ProfileMenu() {
  const { currentUser, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const container = useRef<HTMLDivElement>(null)
  const { pathname } = useLocation()

  // Going somewhere closes the menu.
  useEffect(() => setOpen(false), [pathname])

  useEffect(() => {
    if (!open) return
    const onPointerDown = (event: MouseEvent) => {
      if (!container.current?.contains(event.target as Node)) setOpen(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  if (!currentUser) return null
  const initial = currentUser.name.trim().charAt(0).toUpperCase() || '?'

  return (
    <div ref={container} className="absolute top-3 right-4 z-30">
      <button
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center justify-center w-9 h-9 rounded-full bg-olive text-white text-[14px] font-medium shadow-sm"
      >
        {initial}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Account"
          className="absolute right-0 mt-2 w-60 bg-white rounded-card border border-warm-border shadow-lg overflow-hidden"
        >
          <div className="px-4 py-3 border-b border-warm-divider">
            <p className="text-[14px] font-medium text-text-primary truncate">{currentUser.name}</p>
            <p className="text-[12px] text-text-tertiary truncate">{currentUser.email}</p>
          </div>
          <Link
            to="/profile"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="flex items-start gap-3 px-4 py-3 hover:bg-cream-surface"
          >
            <UserRound size={16} className="mt-0.5 text-text-secondary" />
            <span>
              <span className="block text-[14px] text-text-primary">My profile</span>
              <span className="block text-[12px] text-text-secondary">
                Preferences, allergies and household
              </span>
            </span>
          </Link>
          <button
            role="menuitem"
            onClick={() => {
              setOpen(false)
              void logout()
            }}
            className="flex w-full items-center gap-3 px-4 py-3 border-t border-warm-divider text-left text-[14px] text-text-primary hover:bg-cream-surface"
          >
            <LogOut size={16} className="text-text-secondary" />
            Log out
          </button>
        </div>
      )}
    </div>
  )
}
