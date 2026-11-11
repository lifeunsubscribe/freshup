import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Sheet from './Sheet'

// jsdom provides document.body, so createPortal works without extra setup

describe('Sheet', () => {
  describe('open={false}', () => {
    it('renders no dialog element when closed', () => {
      render(
        <Sheet open={false} onClose={() => {}} title="Test">
          <p>content</p>
        </Sheet>
      )
      expect(screen.queryByRole('dialog')).toBeNull()
    })
  })

  describe('open={true}', () => {
    it('renders title, children, and footer in a portal with role=dialog and aria-modal', () => {
      render(
        <Sheet
          open
          onClose={() => {}}
          title="Pantry check"
          footer={<button>Confirm</button>}
        >
          <p>Sheet content</p>
        </Sheet>
      )
      const dialog = screen.getByRole('dialog')
      expect(dialog).toBeInTheDocument()
      expect(dialog).toHaveAttribute('aria-modal', 'true')
      // title with olive period
      expect(screen.getByText('Pantry check', { exact: false })).toBeInTheDocument()
      // children
      expect(screen.getByText('Sheet content')).toBeInTheDocument()
      // footer
      expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument()
    })

    it('renders title with aria-labelledby pointing at the heading', () => {
      render(
        <Sheet open onClose={() => {}} title="Cook tonight">
          <p>body</p>
        </Sheet>
      )
      const dialog = screen.getByRole('dialog')
      const labelledById = dialog.getAttribute('aria-labelledby')
      expect(labelledById).toBeTruthy()
      const titleEl = document.getElementById(labelledById!)
      expect(titleEl).not.toBeNull()
      expect(titleEl).toHaveTextContent('Cook tonight')
    })

    it('renders into document.body (portal)', () => {
      const { container } = render(
        <Sheet open onClose={() => {}} title="Timer">
          <p>timer body</p>
        </Sheet>
      )
      // The dialog should NOT be inside the React root container
      expect(container.querySelector('[role="dialog"]')).toBeNull()
      // But should exist in the document
      expect(document.body.querySelector('[role="dialog"]')).not.toBeNull()
    })

    it('omits footer slot when footer prop is not provided', () => {
      render(
        <Sheet open onClose={() => {}} title="Why this order">
          <p>content</p>
        </Sheet>
      )
      // Only the Close button should be present (no footer button)
      const buttons = screen.getAllByRole('button')
      expect(buttons).toHaveLength(1)
      expect(buttons[0]).toHaveAttribute('aria-label', 'Close')
    })
  })

  describe('onClose triggers', () => {
    it('calls onClose when Escape is pressed', async () => {
      const onClose = vi.fn()
      render(
        <Sheet open onClose={onClose} title="Arrange">
          <p>body</p>
        </Sheet>
      )
      await userEvent.keyboard('{Escape}')
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when the scrim (outer backdrop) is clicked', () => {
      const onClose = vi.fn()
      const { container } = render(
        <Sheet open onClose={onClose} title="Pantry check">
          <p>body</p>
        </Sheet>
      )
      // The outermost fixed wrapper is the scrim click target
      const wrapper = container.ownerDocument.body.querySelector('.fixed.inset-0') as HTMLElement
      expect(wrapper).not.toBeNull()
      fireEvent.mouseDown(wrapper)
      fireEvent.click(wrapper)
      expect(onClose).toHaveBeenCalledTimes(1)
    })

    it('does NOT call onClose when a click occurs inside the panel', () => {
      const onClose = vi.fn()
      render(
        <Sheet open onClose={onClose} title="Pantry check">
          <p>Panel content</p>
        </Sheet>
      )
      fireEvent.click(screen.getByText('Panel content'))
      expect(onClose).not.toHaveBeenCalled()
    })

    it('does NOT call onClose when a drag starts on the panel and ends on the scrim', () => {
      const onClose = vi.fn()
      render(
        <Sheet open onClose={onClose} title="Pantry check">
          <p>Panel content</p>
        </Sheet>
      )
      const panel = screen.getByRole('dialog')
      const wrapper = panel.parentElement!
      fireEvent.mouseDown(panel)
      fireEvent.click(wrapper)
      expect(onClose).not.toHaveBeenCalled()
    })

    it('calls onClose when the close button is clicked', () => {
      const onClose = vi.fn()
      render(
        <Sheet open onClose={onClose} title="New timer">
          <p>body</p>
        </Sheet>
      )
      fireEvent.click(screen.getByRole('button', { name: 'Close' }))
      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })

  describe('focus management', () => {
    beforeEach(() => {
      // Ensure a clean body before each focus test
      document.body.innerHTML = ''
    })

    it('moves focus inside the sheet when opened', () => {
      const { rerender } = render(
        <Sheet open={false} onClose={() => {}} title="Cook tonight">
          <button>First action</button>
        </Sheet>
      )
      rerender(
        <Sheet open onClose={() => {}} title="Cook tonight">
          <button>First action</button>
        </Sheet>
      )
      // Focus should now be on the first focusable element (the button)
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'First action' }))
    })

    it('falls back to focusing the panel itself when no focusable child exists', () => {
      const { rerender } = render(
        <Sheet open={false} onClose={() => {}} title="Why this order">
          <p>No buttons here</p>
        </Sheet>
      )
      rerender(
        <Sheet open onClose={() => {}} title="Why this order">
          <p>No buttons here</p>
        </Sheet>
      )
      // Panel has tabIndex=-1 and should receive focus
      const dialog = screen.getByRole('dialog')
      expect(document.activeElement).toBe(dialog)
    })

    it('returns focus to the previously focused element when closed', () => {
      // Create a trigger button in the document
      const trigger = document.createElement('button')
      trigger.textContent = 'Open sheet'
      document.body.appendChild(trigger)
      trigger.focus()
      expect(document.activeElement).toBe(trigger)

      const { rerender } = render(
        <Sheet open onClose={() => {}} title="Timer">
          <p>body</p>
        </Sheet>
      )
      // Focus moved into sheet; now close it
      rerender(
        <Sheet open={false} onClose={() => {}} title="Timer">
          <p>body</p>
        </Sheet>
      )
      expect(document.activeElement).toBe(trigger)
      trigger.remove()
    })

    it('Tab on the last focusable element wraps focus to the first', async () => {
      const user = userEvent.setup()
      render(
        <Sheet open onClose={() => {}} title="Cook tonight">
          <button>Panel button</button>
        </Sheet>
      )
      // DOM order inside the dialog: Close button (header), Panel button (content)
      const closeBtn = screen.getByRole('button', { name: 'Close' })
      const panelBtn = screen.getByRole('button', { name: 'Panel button' })

      panelBtn.focus()
      await user.keyboard('{Tab}')
      expect(document.activeElement).toBe(closeBtn)
    })

    it('Shift+Tab on the first focusable element wraps focus to the last', async () => {
      const user = userEvent.setup()
      render(
        <Sheet open onClose={() => {}} title="Cook tonight">
          <button>Panel button</button>
        </Sheet>
      )
      const closeBtn = screen.getByRole('button', { name: 'Close' })
      const panelBtn = screen.getByRole('button', { name: 'Panel button' })

      closeBtn.focus()
      await user.keyboard('{Shift>}{Tab}{/Shift}')
      expect(document.activeElement).toBe(panelBtn)
    })
  })

  describe('scroll lock', () => {
    it('sets body overflow to hidden while open', () => {
      render(
        <Sheet open onClose={() => {}} title="Arrange rows">
          <p>body</p>
        </Sheet>
      )
      expect(document.body.style.overflow).toBe('hidden')
    })

    it('restores body overflow when closed', () => {
      document.body.style.overflow = ''
      const { rerender } = render(
        <Sheet open onClose={() => {}} title="Arrange rows">
          <p>body</p>
        </Sheet>
      )
      rerender(
        <Sheet open={false} onClose={() => {}} title="Arrange rows">
          <p>body</p>
        </Sheet>
      )
      expect(document.body.style.overflow).toBe('')
    })
  })
})
