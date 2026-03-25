import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import GreetingHeader from '../GreetingHeader'
import { useCurrentUser } from '../../../api'

// Mock the API hook
vi.mock('../../../api', () => ({
  useCurrentUser: vi.fn(),
}))

describe('GreetingHeader', () => {
  const mockUser = {
    id: 'user-1',
    username: 'testuser',
    display_name: 'Test User',
  }

  beforeEach(() => {
    vi.clearAllMocks()
    // Reset to a known date/time for consistent testing
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('basic rendering', () => {
    it('renders greeting header with user display name', () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)

      expect(screen.getByText(/Good morning, Test User/i)).toBeInTheDocument()
    })

    it('renders current date in readable format', () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)

      expect(screen.getByText('Tuesday, March 25')).toBeInTheDocument()
    })

    it('renders olive period after greeting', () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const { container } = render(<GreetingHeader />)
      const period = container.querySelector('.text-olive')

      expect(period).toBeInTheDocument()
      expect(period?.textContent).toBe('.')
    })
  })

  describe('time-based greetings', () => {
    it('displays "Good morning" between 5:00 and 11:59', () => {
      vi.setSystemTime(new Date('2026-03-25T08:30:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)

      expect(screen.getByText(/Good morning/i)).toBeInTheDocument()
    })

    it('displays "Good afternoon" between 12:00 and 16:59', () => {
      vi.setSystemTime(new Date('2026-03-25T14:30:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)

      expect(screen.getByText(/Good afternoon/i)).toBeInTheDocument()
    })

    it('displays "Good evening" between 17:00 and 4:59', () => {
      vi.setSystemTime(new Date('2026-03-25T20:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)

      expect(screen.getByText(/Good evening/i)).toBeInTheDocument()
    })

    it('displays "Good evening" in early morning (before 5:00)', () => {
      vi.setSystemTime(new Date('2026-03-25T02:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)

      expect(screen.getByText(/Good evening/i)).toBeInTheDocument()
    })

    it('transitions from morning to afternoon at noon boundary', () => {
      vi.setSystemTime(new Date('2026-03-25T11:59:59'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)
      expect(screen.getByText(/Good morning/i)).toBeInTheDocument()

      // Simulate time passing to noon
      vi.setSystemTime(new Date('2026-03-25T12:00:00'))
      vi.advanceTimersByTime(60000) // Advance by 1 minute to trigger interval

      waitFor(() => {
        expect(screen.getByText(/Good afternoon/i)).toBeInTheDocument()
      })
    })
  })

  describe('user display name handling', () => {
    it('displays username when display_name is not available', () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: { id: 'user-1', username: 'testuser' },
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)

      expect(screen.getByText(/Good morning, testuser/i)).toBeInTheDocument()
    })

    it('displays "there" when user data is not available', () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: null,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)

      expect(screen.getByText(/Good morning, there/i)).toBeInTheDocument()
    })

    it('displays "..." while loading user data', () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)

      expect(screen.getByText(/Good morning, \.\.\./i)).toBeInTheDocument()
    })

    it('displays "there" when there is an error loading user data', () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: new Error('Network error'),
      } as any)

      render(<GreetingHeader />)

      expect(screen.getByText(/Good morning, there/i)).toBeInTheDocument()
    })
  })

  describe('automatic refresh functionality', () => {
    it('updates greeting after 1 minute interval', async () => {
      // Start at 11:59 AM (morning)
      vi.setSystemTime(new Date('2026-03-25T11:59:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)
      expect(screen.getByText(/Good morning/i)).toBeInTheDocument()

      // Advance time to 12:00 PM (afternoon)
      vi.setSystemTime(new Date('2026-03-25T12:00:00'))
      vi.advanceTimersByTime(60000) // Trigger 1-minute interval

      await waitFor(() => {
        expect(screen.getByText(/Good afternoon/i)).toBeInTheDocument()
      })
    })

    it('updates date after midnight', async () => {
      // Start at 11:59 PM on March 25
      vi.setSystemTime(new Date('2026-03-25T23:59:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)
      expect(screen.getByText('Tuesday, March 25')).toBeInTheDocument()

      // Advance time to 12:00 AM on March 26
      vi.setSystemTime(new Date('2026-03-26T00:00:00'))
      vi.advanceTimersByTime(60000) // Trigger 1-minute interval

      await waitFor(() => {
        expect(screen.getByText('Wednesday, March 26')).toBeInTheDocument()
      })
    })

    it('updates on visibility change when app regains focus', async () => {
      // Start at morning
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)
      expect(screen.getByText(/Good morning/i)).toBeInTheDocument()

      // Simulate time passing while app is in background
      vi.setSystemTime(new Date('2026-03-25T14:00:00'))

      // Simulate visibility change event
      Object.defineProperty(document, 'visibilityState', {
        writable: true,
        configurable: true,
        value: 'visible',
      })
      document.dispatchEvent(new Event('visibilitychange'))

      await waitFor(() => {
        expect(screen.getByText(/Good afternoon/i)).toBeInTheDocument()
      })
    })

    it('does not update on visibility change when app becomes hidden', async () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<GreetingHeader />)
      expect(screen.getByText(/Good morning/i)).toBeInTheDocument()

      // Simulate time passing
      vi.setSystemTime(new Date('2026-03-25T14:00:00'))

      // Simulate app becoming hidden (should not trigger update)
      Object.defineProperty(document, 'visibilityState', {
        writable: true,
        configurable: true,
        value: 'hidden',
      })
      document.dispatchEvent(new Event('visibilitychange'))

      // Should still show morning greeting
      expect(screen.getByText(/Good morning/i)).toBeInTheDocument()
    })
  })

  describe('cleanup on unmount', () => {
    it('clears interval timer on unmount', () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const clearIntervalSpy = vi.spyOn(global, 'clearInterval')
      const { unmount } = render(<GreetingHeader />)

      unmount()

      expect(clearIntervalSpy).toHaveBeenCalled()
    })

    it('removes visibility change listener on unmount', () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const removeEventListenerSpy = vi.spyOn(document, 'removeEventListener')
      const { unmount } = render(<GreetingHeader />)

      unmount()

      expect(removeEventListenerSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function))
    })
  })

  describe('styling', () => {
    it('applies correct text styles to greeting', () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const { container } = render(<GreetingHeader />)
      const heading = container.querySelector('h1')

      expect(heading).toHaveClass('text-[22px]', 'font-medium', 'text-text-primary')
    })

    it('applies correct text styles to date', () => {
      vi.setSystemTime(new Date('2026-03-25T10:00:00'))
      vi.mocked(useCurrentUser).mockReturnValue({
        data: mockUser,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const { container } = render(<GreetingHeader />)
      const date = container.querySelector('p')

      expect(date).toHaveClass('text-sm', 'text-text-secondary', 'mt-1')
    })
  })
})
