import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RatingLine from './RatingLine'

function renderLine(props: React.ComponentProps<typeof RatingLine>) {
  return render(<RatingLine {...props} />)
}

describe('RatingLine', () => {
  describe('never-cooked state (cookCount=0, rating=null)', () => {
    it('shows the muted gate sentence', () => {
      renderLine({ cookCount: 0, rating: null, onRate: vi.fn() })
      expect(
        screen.getByText(/ratings open up after the first cook/i)
      ).toBeInTheDocument()
    })

    it('does not render any star buttons', () => {
      renderLine({ cookCount: 0, rating: null, onRate: vi.fn() })
      expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
    })
  })

  describe('cooked-no-rating state (cookCount>0, rating=null)', () => {
    it('renders the "You\'ve cooked this. Rate it?" prompt', () => {
      renderLine({ cookCount: 2, rating: null, onRate: vi.fn() })
      expect(screen.getByText(/you've cooked this\. rate it\?/i)).toBeInTheDocument()
    })

    it('renders five star buttons', () => {
      renderLine({ cookCount: 2, rating: null, onRate: vi.fn() })
      const group = screen.getByRole('radiogroup', { name: /rating, 1 to 5/i })
      expect(group.querySelectorAll('[role="radio"]')).toHaveLength(5)
    })

    it('calls onRate with the tapped star value', async () => {
      const onRate = vi.fn().mockResolvedValue(undefined)
      renderLine({ cookCount: 1, rating: null, onRate })

      await userEvent.click(screen.getByRole('radio', { name: /5 stars/i }))
      await waitFor(() => expect(onRate).toHaveBeenCalledWith(5))
    })
  })

  describe('rated state (rating !== null)', () => {
    it('shows the user\'s rating', () => {
      renderLine({ cookCount: 3, rating: 4, onRate: vi.fn() })
      expect(screen.getByText(/your rating: 4\/5/i)).toBeInTheDocument()
    })

    it('does not show inline stars initially', () => {
      renderLine({ cookCount: 3, rating: 4, onRate: vi.fn() })
      expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
    })

    it('shows stars when "change" is clicked', async () => {
      renderLine({ cookCount: 3, rating: 4, onRate: vi.fn() })
      await userEvent.click(screen.getByRole('button', { name: /change/i }))
      expect(screen.getByRole('radiogroup')).toBeInTheDocument()
    })
  })
})
