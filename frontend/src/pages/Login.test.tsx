import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, within } from '@testing-library/react'
import Login from './Login'
import { renderWithProviders } from '../test/renderWithProviders'

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ login: vi.fn() }),
}))

describe('Login page', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('shows the development login and fills it in, on the dev server', () => {
    vi.stubEnv('VITE_DEV_LOGIN_EMAIL', 'dev@example.test')
    vi.stubEnv('VITE_DEV_LOGIN_PASSWORD', 'dev-password')

    renderWithProviders(<Login />)

    const box = within(screen.getByLabelText('Development login'))
    expect(box.getByText('dev@example.test')).toBeInTheDocument()
    expect(box.getByText('dev-password')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveValue('dev@example.test')
    expect(screen.getByLabelText('Password')).toHaveValue('dev-password')
  })

  it('shows nothing and fills nothing when no dev login is set', () => {
    renderWithProviders(<Login />)

    expect(screen.queryByLabelText('Development login')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveValue('')
    expect(screen.getByLabelText('Password')).toHaveValue('')
  })

  it('shows nothing outside the dev server, whatever the variables say', () => {
    vi.stubEnv('VITE_DEV_LOGIN_EMAIL', 'dev@example.test')
    vi.stubEnv('VITE_DEV_LOGIN_PASSWORD', 'dev-password')
    vi.stubEnv('DEV', false)

    renderWithProviders(<Login />)

    expect(screen.queryByLabelText('Development login')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveValue('')
  })
})
