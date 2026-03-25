import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ServingsControl from './ServingsControl'

describe('ServingsControl', () => {
  const mockOnChange = vi.fn()

  beforeEach(() => {
    mockOnChange.mockClear()
  })

  describe('basic rendering', () => {
    it('renders label "Servings"', () => {
      render(
        <ServingsControl selectedServings={2} onServingsChange={mockOnChange} />
      )
      expect(screen.getByText('Servings')).toBeInTheDocument()
    })

    it('renders three serving options: 2, 4, 6', () => {
      render(
        <ServingsControl selectedServings={2} onServingsChange={mockOnChange} />
      )
      expect(screen.getByLabelText('2 servings')).toBeInTheDocument()
      expect(screen.getByLabelText('4 servings')).toBeInTheDocument()
      expect(screen.getByLabelText('6 servings')).toBeInTheDocument()
    })

    it('highlights selected serving option', () => {
      const { container } = render(
        <ServingsControl selectedServings={4} onServingsChange={mockOnChange} />
      )
      const button4 = screen.getByLabelText('4 servings')
      expect(button4.className).toContain('bg-olive')
      expect(button4.className).toContain('text-cream')
    })

    it('does not highlight non-selected options', () => {
      render(
        <ServingsControl selectedServings={4} onServingsChange={mockOnChange} />
      )
      const button2 = screen.getByLabelText('2 servings')
      const button6 = screen.getByLabelText('6 servings')
      expect(button2.className).not.toContain('bg-olive')
      expect(button6.className).not.toContain('bg-olive')
    })
  })

  describe('base servings functionality', () => {
    it('disables non-base serving options when baseServings is provided', () => {
      render(
        <ServingsControl
          selectedServings={4}
          onServingsChange={mockOnChange}
          baseServings={4}
        />
      )
      const button2 = screen.getByLabelText(/2 servings/)
      const button4 = screen.getByLabelText(/4 servings/)
      const button6 = screen.getByLabelText(/6 servings/)

      expect(button2).toBeDisabled()
      expect(button4).not.toBeDisabled()
      expect(button6).toBeDisabled()
    })

    it('shows lock icon on non-base serving options', () => {
      const { container } = render(
        <ServingsControl
          selectedServings={2}
          onServingsChange={mockOnChange}
          baseServings={2}
        />
      )
      // Lock icons should appear for 4 and 6 servings (non-base options)
      const buttons = container.querySelectorAll('button')
      const button4 = Array.from(buttons).find(btn => btn.textContent?.includes('4'))
      const button6 = Array.from(buttons).find(btn => btn.textContent?.includes('6'))

      expect(button4?.querySelector('svg')).toBeInTheDocument()
      expect(button6?.querySelector('svg')).toBeInTheDocument()
    })

    it('does not show lock icon on base serving option', () => {
      const { container } = render(
        <ServingsControl
          selectedServings={4}
          onServingsChange={mockOnChange}
          baseServings={4}
        />
      )
      const buttons = container.querySelectorAll('button')
      const button4 = Array.from(buttons).find(btn =>
        btn.textContent?.trim() === '4' && !btn.disabled
      )

      // Base option should not have a lock icon
      expect(button4?.querySelector('svg')).not.toBeInTheDocument()
    })

    it('displays Phase 3 message when baseServings is provided', () => {
      render(
        <ServingsControl
          selectedServings={2}
          onServingsChange={mockOnChange}
          baseServings={2}
        />
      )
      expect(screen.getByText('Servings scaling coming in Phase 3')).toBeInTheDocument()
    })

    it('does not display Phase 3 message when baseServings is not provided', () => {
      render(
        <ServingsControl selectedServings={2} onServingsChange={mockOnChange} />
      )
      expect(screen.queryByText('Servings scaling coming in Phase 3')).not.toBeInTheDocument()
    })

    it('applies opacity to non-base options', () => {
      render(
        <ServingsControl
          selectedServings={4}
          onServingsChange={mockOnChange}
          baseServings={4}
        />
      )
      const button2 = screen.getByLabelText(/2 servings/)
      const button6 = screen.getByLabelText(/6 servings/)

      expect(button2.className).toContain('opacity-50')
      expect(button6.className).toContain('opacity-50')
    })
  })

  describe('user interactions', () => {
    it('calls onServingsChange when a button is clicked', async () => {
      const user = userEvent.setup()
      render(
        <ServingsControl selectedServings={2} onServingsChange={mockOnChange} />
      )
      const button4 = screen.getByLabelText('4 servings')
      await user.click(button4)
      expect(mockOnChange).toHaveBeenCalledWith(4)
    })

    it('calls onServingsChange with correct value for each button', async () => {
      const user = userEvent.setup()
      render(
        <ServingsControl selectedServings={2} onServingsChange={mockOnChange} />
      )

      await user.click(screen.getByLabelText('6 servings'))
      expect(mockOnChange).toHaveBeenCalledWith(6)

      mockOnChange.mockClear()
      await user.click(screen.getByLabelText('2 servings'))
      expect(mockOnChange).toHaveBeenCalledWith(2)
    })

    it('does not call onServingsChange when disabled button is clicked', async () => {
      const user = userEvent.setup()
      render(
        <ServingsControl
          selectedServings={4}
          onServingsChange={mockOnChange}
          baseServings={4}
        />
      )
      const button2 = screen.getByLabelText(/2 servings/)
      await user.click(button2)
      expect(mockOnChange).not.toHaveBeenCalled()
    })

    it('updates aria-pressed attribute based on selection', () => {
      const { rerender } = render(
        <ServingsControl selectedServings={2} onServingsChange={mockOnChange} />
      )
      expect(screen.getByLabelText('2 servings')).toHaveAttribute('aria-pressed', 'true')
      expect(screen.getByLabelText('4 servings')).toHaveAttribute('aria-pressed', 'false')

      rerender(
        <ServingsControl selectedServings={4} onServingsChange={mockOnChange} />
      )
      expect(screen.getByLabelText('2 servings')).toHaveAttribute('aria-pressed', 'false')
      expect(screen.getByLabelText('4 servings')).toHaveAttribute('aria-pressed', 'true')
    })
  })

  describe('accessibility', () => {
    it('has proper aria-label for each button', () => {
      render(
        <ServingsControl selectedServings={2} onServingsChange={mockOnChange} />
      )
      expect(screen.getByLabelText('2 servings')).toHaveAttribute('aria-label', '2 servings')
      expect(screen.getByLabelText('4 servings')).toHaveAttribute('aria-label', '4 servings')
      expect(screen.getByLabelText('6 servings')).toHaveAttribute('aria-label', '6 servings')
    })

    it('includes Phase 3 context in aria-label for disabled buttons', () => {
      render(
        <ServingsControl
          selectedServings={4}
          onServingsChange={mockOnChange}
          baseServings={4}
        />
      )
      expect(screen.getByLabelText(/2 servings.*coming in Phase 3/)).toBeInTheDocument()
      expect(screen.getByLabelText(/6 servings.*coming in Phase 3/)).toBeInTheDocument()
    })

    it('has title attribute with tooltip for disabled buttons', () => {
      render(
        <ServingsControl
          selectedServings={4}
          onServingsChange={mockOnChange}
          baseServings={4}
        />
      )
      const button2 = screen.getByLabelText(/2 servings/)
      expect(button2).toHaveAttribute('title', 'Servings scaling coming in Phase 3')
    })
  })

  describe('styling', () => {
    it('applies segmented control styling with borders', () => {
      const { container } = render(
        <ServingsControl selectedServings={2} onServingsChange={mockOnChange} />
      )
      const controlGroup = container.querySelector('.inline-flex.rounded-button')
      expect(controlGroup).toBeInTheDocument()
      expect(controlGroup?.className).toContain('border')
      expect(controlGroup?.className).toContain('overflow-hidden')
    })

    it('applies border-right to all buttons except the last', () => {
      render(
        <ServingsControl selectedServings={2} onServingsChange={mockOnChange} />
      )
      const button2 = screen.getByLabelText('2 servings')
      const button4 = screen.getByLabelText('4 servings')
      const button6 = screen.getByLabelText('6 servings')

      expect(button2.className).toContain('border-r')
      expect(button4.className).toContain('border-r')
      expect(button6.className).not.toContain('border-r')
    })
  })
})
