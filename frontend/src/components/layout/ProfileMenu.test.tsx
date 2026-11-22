import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import ProfileMenu from './ProfileMenu'
import { renderWithProviders } from '../../test/renderWithProviders'

const logout = vi.fn()
let currentUser: { name: string; email: string } | undefined

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ currentUser, logout }),
}))

function openMenu() {
  fireEvent.click(screen.getByRole('button', { name: 'Account menu' }))
}

describe('ProfileMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    currentUser = { name: 'Sarah', email: 'sarah@example.test' }
    logout.mockResolvedValue(undefined)
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

  it('renders nothing when nobody is signed in', () => {
    currentUser = undefined
    const { container } = renderWithProviders(<ProfileMenu />)

    expect(container).toBeEmptyDOMElement()
  })
})
