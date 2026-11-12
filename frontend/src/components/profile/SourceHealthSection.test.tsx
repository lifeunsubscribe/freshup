import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SourceHealthSection from './SourceHealthSection'
import { useAuth } from '../../contexts/AuthContext'
import { useSourceHealth } from '../../api/hooks/useSourceHealth'
import type { SourceStatus } from '../../api/types'

vi.mock('../../contexts/AuthContext')
vi.mock('../../api/hooks/useSourceHealth')

const coordinator = {
  id: '1',
  name: 'Sarah',
  email: 'sarah@example.com',
  role: 'coordinator',
  dietary_profile: [],
  allergies: [],
  disliked_ingredients: [],
  favorite_ingredients: [],
  failed_login_attempts: 0,
  lockout_until: null,
  lockout_count: 0,
}

const member = { ...coordinator, id: '2', role: 'member' }

const healthyStatus: SourceStatus = {
  source_type: 'hellofresh',
  status: 'healthy',
  checked_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
  failing_since: null,
  detail: null,
  import_mode: 'link',
}

const failingStatus: SourceStatus = {
  source_type: 'kitchen_sanctuary',
  status: 'failing',
  checked_at: new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString(),
  failing_since: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(), // 3 days ago
  detail: 'The test recipe page returned a 403 error.',
  import_mode: 'saved_page',
}

const failingLinkMode: SourceStatus = {
  source_type: 'hellofresh',
  status: 'failing',
  checked_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  failing_since: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
  detail: 'Ingredient list came back empty.',
  import_mode: 'link',
}

const neverCheckedStatus: SourceStatus = {
  source_type: 'hellofresh',
  status: 'never_checked',
  checked_at: null,
  failing_since: null,
  detail: null,
  import_mode: null,
}

const renderSection = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <SourceHealthSection />
    </QueryClientProvider>,
  )
}

describe('SourceHealthSection', () => {
  beforeEach(() => {
    vi.mocked(useSourceHealth).mockReturnValue({
      data: [],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSourceHealth>)
  })

  it('renders nothing for a member', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: member,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    const { container } = renderSection()
    expect(container.firstChild).toBeNull()
  })

  it('renders nothing when currentUser is null', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: undefined,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    const { container } = renderSection()
    expect(container.firstChild).toBeNull()
  })

  it('renders section heading for a coordinator', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: coordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })

    renderSection()
    expect(screen.getByText('Recipe sources.')).toBeInTheDocument()
    expect(document.getElementById('recipe-sources')).toBeInTheDocument()
  })

  it('renders healthy row with olive dot and checked-at text', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: coordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })
    vi.mocked(useSourceHealth).mockReturnValue({
      data: [healthyStatus],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSourceHealth>)

    renderSection()

    expect(screen.getByText('HelloFresh')).toBeInTheDocument()
    expect(screen.getByText(/Checked .+ ago/)).toBeInTheDocument()

    const dot = screen.getByText('HelloFresh').parentElement?.previousElementSibling
    expect(dot).toHaveClass('bg-olive')
  })

  it('renders failing row with terracotta dot and failing-since text', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: coordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })
    vi.mocked(useSourceHealth).mockReturnValue({
      data: [failingStatus],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSourceHealth>)

    renderSection()

    expect(screen.getByText('Kitchen Sanctuary')).toBeInTheDocument()
    expect(screen.getByText(/Failing since .+ ago/)).toBeInTheDocument()

    const dot = screen.getByText('Kitchen Sanctuary').parentElement?.previousElementSibling
    expect(dot).toHaveClass('bg-terra')
  })

  it('renders never_checked row with muted dot and "Not checked yet"', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: coordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })
    vi.mocked(useSourceHealth).mockReturnValue({
      data: [neverCheckedStatus],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSourceHealth>)

    renderSection()

    expect(screen.getByText('HelloFresh')).toBeInTheDocument()
    expect(screen.getByText('Not checked yet')).toBeInTheDocument()

    const dot = screen.getByText('HelloFresh').parentElement?.previousElementSibling
    expect(dot).toHaveClass('bg-text-muted')
  })

  it('renders loading rows with "Checking…" text', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: coordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })
    vi.mocked(useSourceHealth).mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as ReturnType<typeof useSourceHealth>)

    renderSection()

    const checkingItems = screen.getAllByText('Checking…')
    expect(checkingItems.length).toBeGreaterThanOrEqual(1)
  })

  it('failing row opens on click and shows detail and saved_page still-works line', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: coordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })
    vi.mocked(useSourceHealth).mockReturnValue({
      data: [failingStatus],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSourceHealth>)

    renderSection()

    // disclosure closed initially — detail not visible
    expect(screen.queryByText('The test recipe page returned a 403 error.')).not.toBeInTheDocument()

    // click to open
    fireEvent.click(screen.getByRole('button', { expanded: false }))

    expect(screen.getByText('The test recipe page returned a 403 error.')).toBeInTheDocument()
    expect(
      screen.getByText(
        'Saved pages are the normal way in for this source; the check could not read one.',
      ),
    ).toBeInTheDocument()
  })

  it('failing row with import_mode=link shows link still-works line', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: coordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })
    vi.mocked(useSourceHealth).mockReturnValue({
      data: [failingLinkMode],
      isLoading: false,
      isError: false,
    } as ReturnType<typeof useSourceHealth>)

    renderSection()

    fireEvent.click(screen.getByRole('button', { expanded: false }))

    expect(screen.getByText('Pasting a saved page still works.')).toBeInTheDocument()
  })

  it('renders error line and no rows on query error', () => {
    vi.mocked(useAuth).mockReturnValue({
      currentUser: coordinator,
      isAuthenticated: true,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      switchUser: vi.fn(),
    })
    vi.mocked(useSourceHealth).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as ReturnType<typeof useSourceHealth>)

    renderSection()

    expect(screen.getByText('Could not read source status.')).toBeInTheDocument()
    // no source rows
    expect(screen.queryByText('HelloFresh')).not.toBeInTheDocument()
    expect(screen.queryByText('Kitchen Sanctuary')).not.toBeInTheDocument()
  })
})
