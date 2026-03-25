import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import ProfileHeader from './ProfileHeader'
import type { UserResponse } from '../../api/types'

describe('ProfileHeader', () => {
  const mockCoordinator: UserResponse = {
    id: '1',
    name: 'John Doe',
    email: 'john@example.com',
    role: 'coordinator',
    dietary_profile: ['vegetarian'],
    allergies: [],
    disliked_ingredients: [],
    favorite_ingredients: [],
    failed_login_attempts: 0,
    lockout_until: null,
    lockout_count: 0,
  }

  const mockMember: UserResponse = {
    ...mockCoordinator,
    id: '2',
    name: 'Jane Doe',
    email: 'jane@example.com',
    role: 'member',
  }

  it('renders user name and email', () => {
    const mockLogout = vi.fn()
    render(<ProfileHeader user={mockCoordinator} onLogout={mockLogout} />)

    expect(screen.getByText('John Doe')).toBeInTheDocument()
    expect(screen.getByText('john@example.com')).toBeInTheDocument()
  })

  it('displays coordinator badge with correct styling', () => {
    const mockLogout = vi.fn()
    render(<ProfileHeader user={mockCoordinator} onLogout={mockLogout} />)

    const badge = screen.getByText('Coordinator')
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain('bg-olive')
    expect(badge.className).toContain('text-cream')
  })

  it('displays member badge with correct styling', () => {
    const mockLogout = vi.fn()
    render(<ProfileHeader user={mockMember} onLogout={mockLogout} />)

    const badge = screen.getByText('Member')
    expect(badge).toBeInTheDocument()
    expect(badge.className).toContain('bg-cream-dark')
    expect(badge.className).toContain('text-text-primary')
  })

  it('renders logout button', () => {
    const mockLogout = vi.fn()
    render(<ProfileHeader user={mockCoordinator} onLogout={mockLogout} />)

    expect(screen.getByRole('button', { name: /log out/i })).toBeInTheDocument()
  })

  it('calls onLogout when logout button is clicked', async () => {
    const mockLogout = vi.fn().mockResolvedValue(undefined)
    render(<ProfileHeader user={mockCoordinator} onLogout={mockLogout} />)

    const logoutButton = screen.getByRole('button', { name: /log out/i })
    fireEvent.click(logoutButton)

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalledTimes(1)
    })
  })

  it('shows loading state during logout', async () => {
    const mockLogout = vi.fn(() => new Promise((resolve) => setTimeout(resolve, 100)))
    render(<ProfileHeader user={mockCoordinator} onLogout={mockLogout} />)

    const logoutButton = screen.getByRole('button', { name: /log out/i })
    fireEvent.click(logoutButton)

    expect(screen.getByText('Logging out...')).toBeInTheDocument()
    expect(logoutButton).toBeDisabled()
  })

  it('displays error message when logout fails', async () => {
    const mockLogout = vi.fn().mockRejectedValue(new Error('Network error'))
    render(<ProfileHeader user={mockCoordinator} onLogout={mockLogout} />)

    const logoutButton = screen.getByRole('button', { name: /log out/i })
    fireEvent.click(logoutButton)

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })
  })

  it('displays generic error message for non-Error failures', async () => {
    const mockLogout = vi.fn().mockRejectedValue('Unknown error')
    render(<ProfileHeader user={mockCoordinator} onLogout={mockLogout} />)

    const logoutButton = screen.getByRole('button', { name: /log out/i })
    fireEvent.click(logoutButton)

    await waitFor(() => {
      expect(screen.getByText('Failed to log out. Please try again.')).toBeInTheDocument()
    })
  })

  it('clears error message on subsequent logout attempt', async () => {
    const mockLogout = vi
      .fn()
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce(undefined)
    render(<ProfileHeader user={mockCoordinator} onLogout={mockLogout} />)

    const logoutButton = screen.getByRole('button', { name: /log out/i })

    // First attempt - should fail
    fireEvent.click(logoutButton)
    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })

    // Second attempt - should clear error
    fireEvent.click(logoutButton)
    await waitFor(() => {
      expect(screen.queryByText('Network error')).not.toBeInTheDocument()
    })
  })

  it('applies design system styles', () => {
    const mockLogout = vi.fn()
    const { container } = render(<ProfileHeader user={mockCoordinator} onLogout={mockLogout} />)

    const card = container.querySelector('.bg-white')
    expect(card).toBeInTheDocument()
    expect(card?.className).toContain('rounded-card')
    expect(card?.className).toContain('border-warm-border')
  })
})
