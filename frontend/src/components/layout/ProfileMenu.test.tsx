import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import ProfileMenu from './ProfileMenu'
import { renderWithProviders } from '../../test/renderWithProviders'

const logout = vi.fn()
let currentUser: { name: string; email: string } | undefined

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ currentUser, logout }),
}))

const sendMutate = vi.fn()
let sendState = { isPending: false, isError: false }
vi.mock('../../api/hooks/useFeedback', () => ({
  useSendFeedback: () => ({ mutate: sendMutate, reset: vi.fn(), ...sendState }),
}))

function openMenu() {
  fireEvent.click(screen.getByRole('button', { name: 'Account menu' }))
}

describe('ProfileMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    currentUser = { name: 'Sarah', email: 'sarah@example.test' }
    logout.mockResolvedValue(undefined)
    sendState = { isPending: false, isError: false }
  })

  it('shows the signed-in person\'s initial, with the menu closed', () => {
    renderWithProviders(<ProfileMenu />)

    const button = screen.getByRole('button', { name: 'Account menu' })
    expect(button).toHaveTextContent('S')
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('opens a menu with who is signed in, their profile and log out', () => {
    renderWithProviders(<ProfileMenu />)
    openMenu()

    expect(screen.getByRole('menu', { name: 'Account' })).toBeInTheDocument()
    expect(screen.getByText('Sarah')).toBeInTheDocument()
    expect(screen.getByText('sarah@example.test')).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /My profile/ })).toHaveAttribute('href', '/profile')
    expect(screen.getByRole('menuitem', { name: /My recipes/ })).toHaveAttribute('href', '/my-recipes')
    expect(screen.getByRole('menuitem', { name: 'Log out' })).toBeInTheDocument()
  })

  it('logs out from the menu', () => {
    renderWithProviders(<ProfileMenu />)
    openMenu()
    fireEvent.click(screen.getByRole('menuitem', { name: 'Log out' }))

    expect(logout).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('closes on Escape, on a press outside, and on the button again', () => {
    renderWithProviders(<ProfileMenu />)

    openMenu()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()

    openMenu()
    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()

    openMenu()
    openMenu()
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('stays open for a press inside the menu', () => {
    renderWithProviders(<ProfileMenu />)
    openMenu()
    fireEvent.mouseDown(screen.getByText('sarah@example.test'))

    expect(screen.getByRole('menu')).toBeInTheDocument()
  })

  describe('send feedback', () => {
    function openFeedback() {
      openMenu()
      fireEvent.click(screen.getByRole('menuitem', { name: /Send feedback/ }))
    }

    it('opens a sheet for a note to the developer and closes the menu', () => {
      renderWithProviders(<ProfileMenu />, { route: '/plan/2026-11-15' })
      openFeedback()

      expect(screen.getByRole('dialog', { name: 'Send feedback to the developer' })).toBeInTheDocument()
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled()
    })

    it('sends the note with the page it was written on, then says it is saved', () => {
      sendMutate.mockImplementation((_note, options) => options.onSuccess())
      renderWithProviders(<ProfileMenu />, { route: '/plan/2026-11-15' })
      openFeedback()
      fireEvent.change(screen.getByRole('textbox'), {
        target: { value: '  The swap button is hard to find.  ' },
      })
      fireEvent.click(screen.getByRole('button', { name: 'Send' }))

      expect(sendMutate).toHaveBeenCalledWith(
        { message: 'The swap button is hard to find.', page: '/plan/2026-11-15' },
        expect.anything()
      )
      expect(screen.getByRole('status')).toHaveTextContent('Your note is saved for review.')
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument()

      fireEvent.click(screen.getByRole('button', { name: 'Done' }))
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('keeps the note and says so when it could not be sent', () => {
      sendState = { isPending: false, isError: true }
      renderWithProviders(<ProfileMenu />)
      openFeedback()
      fireEvent.change(screen.getByRole('textbox'), { target: { value: 'A note' } })

      expect(screen.getByRole('alert')).toHaveTextContent('Could not send that. Try again.')
      expect(screen.getByRole('textbox')).toHaveValue('A note')
    })
  })

  it('renders nothing when nobody is signed in', () => {
    currentUser = undefined
    const { container } = renderWithProviders(<ProfileMenu />)

    expect(container).toBeEmptyDOMElement()
  })
})
