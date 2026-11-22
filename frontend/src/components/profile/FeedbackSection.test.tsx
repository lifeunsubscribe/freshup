import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import FeedbackSection from './FeedbackSection'
import { UserRole } from '../../api/types'

let role: string = UserRole.COORDINATOR
vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({ currentUser: { name: 'Sarah', role } }),
}))

const useFeedbackList = vi.fn()
vi.mock('../../api/hooks/useFeedback', () => ({
  useFeedbackList: () => useFeedbackList(),
}))

describe('FeedbackSection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    role = UserRole.COORDINATOR
  })

  it('lists each note with who sent it and from which page', () => {
    useFeedbackList.mockReturnValue({
      data: [
        { id: '1', message: 'Swap is hard to find', page: '/plan', created_at: '2026-11-21T12:00:00', user_name: 'Alex' },
        { id: '2', message: 'Love the carousels', page: null, created_at: '2026-11-20T09:00:00', user_name: 'Sarah' },
      ],
      isLoading: false,
      isError: false,
    })

    render(<FeedbackSection />)

    const notes = screen.getAllByRole('listitem')
    expect(notes).toHaveLength(2)
    expect(notes[0]).toHaveTextContent('Swap is hard to find')
    expect(notes[0]).toHaveTextContent(/Alex · .* · \/plan/)
    expect(notes[1]).toHaveTextContent('Love the carousels')
  })

  it('says where notes come from when there are none', () => {
    useFeedbackList.mockReturnValue({ data: [], isLoading: false, isError: false })

    render(<FeedbackSection />)

    expect(screen.getByText(/Nothing yet/)).toBeInTheDocument()
  })

  it('says so when the notes cannot be read', () => {
    useFeedbackList.mockReturnValue({ data: undefined, isLoading: false, isError: true })

    render(<FeedbackSection />)

    expect(screen.getByText('Could not read feedback.')).toBeInTheDocument()
  })

  it('is not shown to a member, and does not ask for the notes', () => {
    role = UserRole.MEMBER

    const { container } = render(<FeedbackSection />)

    expect(container).toBeEmptyDOMElement()
    expect(useFeedbackList).not.toHaveBeenCalled()
  })
})
