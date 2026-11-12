import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SourceFailingAlert from './SourceFailingAlert'
import type { SourceStatus } from '../../api/types'

function renderAlert(props: React.ComponentProps<typeof SourceFailingAlert>) {
  return render(
    <MemoryRouter>
      <SourceFailingAlert {...props} />
    </MemoryRouter>,
  )
}

const healthy: SourceStatus = {
  source_type: 'hellofresh',
  status: 'healthy',
  checked_at: new Date().toISOString(),
  failing_since: null,
  detail: null,
  import_mode: 'link',
}

const failingHF: SourceStatus = {
  source_type: 'hellofresh',
  status: 'failing',
  checked_at: new Date().toISOString(),
  // 2 days ago — should render a weekday name
  failing_since: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
  detail: null,
  import_mode: 'link',
}

const failingKS: SourceStatus = {
  source_type: 'kitchen_sanctuary',
  status: 'failing',
  checked_at: new Date().toISOString(),
  failing_since: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString(),
  detail: null,
  import_mode: 'saved_page',
}

const failingNoDate: SourceStatus = {
  source_type: 'hellofresh',
  status: 'failing',
  checked_at: new Date().toISOString(),
  failing_since: null,
  detail: null,
  import_mode: 'link',
}

describe('SourceFailingAlert', () => {
  describe('renders nothing when', () => {
    it('statuses is undefined (not yet loaded)', () => {
      const { container } = renderAlert({ statuses: undefined, isLoading: true, isError: false, isCoordinator: false })
      expect(container.firstChild).toBeNull()
    })

    it('isLoading is true', () => {
      const { container } = renderAlert({ statuses: [], isLoading: true, isError: false, isCoordinator: false })
      expect(container.firstChild).toBeNull()
    })

    it('isError is true', () => {
      const { container } = renderAlert({ statuses: undefined, isLoading: false, isError: true, isCoordinator: false })
      expect(container.firstChild).toBeNull()
    })

    it('all sources are healthy', () => {
      const { container } = renderAlert({ statuses: [healthy], isLoading: false, isError: false, isCoordinator: false })
      expect(container.firstChild).toBeNull()
    })

    it('statuses array is empty', () => {
      const { container } = renderAlert({ statuses: [], isLoading: false, isError: false, isCoordinator: false })
      expect(container.firstChild).toBeNull()
    })
  })

  describe('single failing source', () => {
    it('renders with source display name', () => {
      renderAlert({ statuses: [failingHF], isLoading: false, isError: false, isCoordinator: false })
      expect(screen.getByText(/HelloFresh imports have been failing/i)).toBeInTheDocument()
    })

    it('includes "since" with a weekday when failing_since is within last 7 days', () => {
      renderAlert({ statuses: [failingHF], isLoading: false, isError: false, isCoordinator: false })
      expect(screen.getByText(/imports have been failing since/i)).toBeInTheDocument()
    })

    it('omits "since" when failing_since is null', () => {
      renderAlert({ statuses: [failingNoDate], isLoading: false, isError: false, isCoordinator: false })
      const text = screen.getByText(/HelloFresh imports have been failing/i).textContent
      expect(text).not.toMatch(/since/)
    })

    it('shows the saved-page reassurance sentence', () => {
      renderAlert({ statuses: [failingHF], isLoading: false, isError: false, isCoordinator: false })
      expect(screen.getByText(/the saved page still works in the meantime/i)).toBeInTheDocument()
    })

    it('uses Kitchen Sanctuary display name', () => {
      renderAlert({ statuses: [failingKS], isLoading: false, isError: false, isCoordinator: false })
      expect(screen.getByText(/Kitchen Sanctuary imports have been failing/i)).toBeInTheDocument()
    })
  })

  describe('two failing sources', () => {
    it('renders both display names joined with "and"', () => {
      renderAlert({ statuses: [failingHF, failingKS], isLoading: false, isError: false, isCoordinator: false })
      expect(screen.getByText(/HelloFresh and Kitchen Sanctuary imports have been failing/i)).toBeInTheDocument()
    })

    it('does not include "since" in multi-source sentence', () => {
      renderAlert({ statuses: [failingHF, failingKS], isLoading: false, isError: false, isCoordinator: false })
      const text = screen.getByText(/imports have been failing/i).textContent
      expect(text).not.toMatch(/since/)
    })

    it('still shows the saved-page reassurance sentence', () => {
      renderAlert({ statuses: [failingHF, failingKS], isLoading: false, isError: false, isCoordinator: false })
      expect(screen.getByText(/the saved page still works in the meantime/i)).toBeInTheDocument()
    })
  })

  describe('coordinator vs member', () => {
    it('coordinator sees the "See what the check found" link to /profile#recipe-sources', () => {
      renderAlert({ statuses: [failingHF], isLoading: false, isError: false, isCoordinator: true })
      const link = screen.getByRole('link', { name: /see what the check found/i })
      expect(link).toBeInTheDocument()
      expect(link).toHaveAttribute('href', '/profile#recipe-sources')
    })

    it('member does not see the coordinator link', () => {
      renderAlert({ statuses: [failingHF], isLoading: false, isError: false, isCoordinator: false })
      expect(screen.queryByRole('link', { name: /see what the check found/i })).not.toBeInTheDocument()
    })
  })
})
