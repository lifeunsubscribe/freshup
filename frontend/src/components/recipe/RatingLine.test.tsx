import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RatingLine from './RatingLine'

describe('RatingLine', () => {
  describe('never-cooked state (hasCooked=false, rating=null)', () => {
    it('shows the gate message', () => {
      render(<RatingLine hasCooked={false} rating={null} onRate={vi.fn()} />)
      expect(screen.getByText(/ratings open up after the first cook/i)).toBeInTheDocument()
    })

    it('renders no star buttons', () => {
      render(<RatingLine hasCooked={false} rating={null} onRate={vi.fn()} />)
      expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
    })
  })

  describe('cooked but not rated (hasCooked=true, rating=null)', () => {
    it('shows the prompt sentence', () => {
      render(<RatingLine hasCooked={true} rating={null} onRate={vi.fn()} />)
      expect(screen.getByText(/you've cooked this\. rate it\?/i)).toBeInTheDocument()
    })

    it('renders five star buttons', () => {
      render(<RatingLine hasCooked={true} rating={null} onRate={vi.fn()} />)
      const group = screen.getByRole('radiogroup', { name: /rating/i })
      const buttons = group.querySelectorAll('button')
      expect(buttons).toHaveLength(5)
    })

    it('calls onRate with the clicked star value', async () => {
      const onRate = vi.fn()
      render(<RatingLine hasCooked={true} rating={null} onRate={onRate} />)
      const buttons = screen.getByRole('radiogroup').querySelectorAll('button')
      await userEvent.click(buttons[2]) // 3rd button = star 3
      expect(onRate).toHaveBeenCalledWith(3)
    })
  })

  describe('rated state (rating != null)', () => {
    it('shows the user\'s rating as stars', () => {
      render(<RatingLine hasCooked={true} rating={4} onRate={vi.fn()} />)
      expect(screen.getByText(/your rating/i)).toBeInTheDocument()
      // 4 filled stars and 1 empty
      expect(screen.getByLabelText('4 of 5 stars')).toBeInTheDocument()
    })

    it('shows a "change" button', () => {
      render(<RatingLine hasCooked={true} rating={4} onRate={vi.fn()} />)
      expect(screen.getByRole('button', { name: /change/i })).toBeInTheDocument()
    })

    it('shows the star picker when "change" is clicked', async () => {
      render(<RatingLine hasCooked={true} rating={4} onRate={vi.fn()} />)
      await userEvent.click(screen.getByRole('button', { name: /change/i }))
      expect(screen.getByRole('radiogroup')).toBeInTheDocument()
    })

    it('calls onRate with the new value after changing', async () => {
      const onRate = vi.fn()
      render(<RatingLine hasCooked={true} rating={4} onRate={onRate} />)
      await userEvent.click(screen.getByRole('button', { name: /change/i }))
      const buttons = screen.getByRole('radiogroup').querySelectorAll('button')
      await userEvent.click(buttons[4]) // star 5
      expect(onRate).toHaveBeenCalledWith(5)
    })
  })
})
