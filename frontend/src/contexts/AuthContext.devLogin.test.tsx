import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ProtectedRoute from '../components/auth/ProtectedRoute'
import { AuthProvider, useAuth } from './AuthContext'
import { devLoginCredentials } from '../api/devLogin'
import { ApiException } from '../api/client'

// The session the mocked hooks report. Tests change it to stand in for the
// token store and the /auth/me result.
const session = { hasToken: false, user: undefined as { id: string } | undefined }

const loginMutateAsync = vi.fn()
const logoutMutateAsync = vi.fn()
const refetch = vi.fn()

vi.mock('../api/hooks/useAuth', () => ({
  useCurrentUser: () => ({
    data: session.user,
    isLoading: false,
    isError: false,
    refetch,
  }),
  useLogin: () => ({ mutateAsync: loginMutateAsync }),
  useLogout: () => ({ mutateAsync: logoutMutateAsync }),
  useSwitchUser: () => ({ mutateAsync: vi.fn() }),
}))

vi.mock('../api/client', () => ({
  isAuthenticated: () => session.hasToken,
  ApiException: class ApiException extends Error {
    status: number
    constructor(message: string, status: number) {
      super(message)
      this.status = status
    }
  },
}))

function LogoutButton() {
  const { logout } = useAuth()
  return <button onClick={() => void logout()}>Log out</button>
}

function renderApp(initialPath = '/') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>Login Page</div>} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
                <LogoutButton />
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  )
}

function configureDevLogin() {
  vi.stubEnv('VITE_DEV_LOGIN_EMAIL', 'dev@example.test')
  vi.stubEnv('VITE_DEV_LOGIN_PASSWORD', 'dev-password')
}

/** A successful login stores a token; the refetch that follows loads the user. */
function loginWillSucceed() {
  loginMutateAsync.mockImplementation(async () => {
    session.hasToken = true
  })
  refetch.mockImplementation(async () => {
    session.user = { id: 'user-1' }
    return { isError: false }
  })
}

describe('development automatic login', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    session.hasToken = false
    session.user = undefined
    logoutMutateAsync.mockImplementation(async () => {
      session.hasToken = false
      session.user = undefined
    })
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('signs in with the configured login when there is no session', async () => {
    configureDevLogin()
    loginWillSucceed()

    renderApp()

    expect(await screen.findByText('Protected Content')).toBeInTheDocument()
    expect(loginMutateAsync).toHaveBeenCalledTimes(1)
    expect(loginMutateAsync).toHaveBeenCalledWith({
      email: 'dev@example.test',
      password: 'dev-password',
    })
  })

  it('shows loading, not the login page, while it signs in', async () => {
    configureDevLogin()
    let finishLogin: () => void = () => {}
    loginMutateAsync.mockImplementation(
      () => new Promise<void>((resolve) => { finishLogin = resolve })
    )
    refetch.mockResolvedValue({ isError: true })

    renderApp()

    expect(screen.getByText('Loading...')).toBeInTheDocument()
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument()

    finishLogin()
    expect(await screen.findByText('Login Page')).toBeInTheDocument()
  })

  it('leaves the login page once signed in', async () => {
    configureDevLogin()
    loginWillSucceed()

    renderApp('/login')

    expect(await screen.findByText('Protected Content')).toBeInTheDocument()
  })

  it('falls back to the login page when the login is rejected, and tries once', async () => {
    configureDevLogin()
    loginMutateAsync.mockRejectedValue(new Error('Invalid credentials'))

    renderApp()

    expect(await screen.findByText('Login Page')).toBeInTheDocument()
    expect(loginMutateAsync).toHaveBeenCalledTimes(1)
    expect(refetch).not.toHaveBeenCalled()
  })

  it('waits for an API that is not answering yet, then signs in', async () => {
    configureDevLogin()
    let calls = 0
    loginMutateAsync.mockImplementation(async () => {
      calls += 1
      if (calls === 1) throw new ApiException('Network error: Unable to connect to server', 0)
      session.hasToken = true
    })
    refetch.mockImplementation(async () => {
      session.user = { id: 'user-1' }
      return { isError: false }
    })

    renderApp()

    // Still "Loading", not the login page, while it waits to try again.
    expect(screen.getByText('Loading...')).toBeInTheDocument()
    expect(await screen.findByText('Protected Content', {}, { timeout: 5000 })).toBeInTheDocument()
    expect(loginMutateAsync).toHaveBeenCalledTimes(2)
    expect(screen.queryByText('Login Page')).not.toBeInTheDocument()
  })

  it('falls back to the login page when the user cannot be loaded after login', async () => {
    configureDevLogin()
    loginMutateAsync.mockImplementation(async () => {
      session.hasToken = true
    })
    refetch.mockResolvedValue({ isError: true })

    renderApp()

    expect(await screen.findByText('Login Page')).toBeInTheDocument()
    expect(loginMutateAsync).toHaveBeenCalledTimes(1)
  })

  it('does not sign in when a session already exists', () => {
    configureDevLogin()
    session.hasToken = true
    session.user = { id: 'user-1' }

    renderApp()

    expect(screen.getByText('Protected Content')).toBeInTheDocument()
    expect(loginMutateAsync).not.toHaveBeenCalled()
  })

  it('stays logged out after a deliberate logout', async () => {
    configureDevLogin()
    session.hasToken = true
    session.user = { id: 'user-1' }

    renderApp()
    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))

    expect(await screen.findByText('Login Page')).toBeInTheDocument()
    await waitFor(() => expect(logoutMutateAsync).toHaveBeenCalledTimes(1))
    expect(loginMutateAsync).not.toHaveBeenCalled()
  })

  it('does nothing when no dev login is configured', () => {
    renderApp()

    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(loginMutateAsync).not.toHaveBeenCalled()
  })
})

describe('devLoginCredentials', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('returns the pair when both variables are set', () => {
    configureDevLogin()
    expect(devLoginCredentials()).toEqual({ email: 'dev@example.test', password: 'dev-password' })
  })

  it('returns null when either variable is missing', () => {
    vi.stubEnv('VITE_DEV_LOGIN_EMAIL', 'dev@example.test')
    expect(devLoginCredentials()).toBeNull()
  })

  it('returns null outside the dev server, whatever the variables say', () => {
    configureDevLogin()
    vi.stubEnv('DEV', false)
    expect(devLoginCredentials()).toBeNull()
  })
})
