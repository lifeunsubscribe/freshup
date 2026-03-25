import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SectionNav from '../SectionNav'

describe('SectionNav', () => {
  const mockSections = [
    { id: 'favorites', label: 'Your favorites' },
    { id: 'quick-meals', label: 'Quick meals' },
    { id: 'recently-added', label: 'Recently added' },
    { id: 'italian', label: 'Italian' },
    { id: 'mexican', label: 'Mexican' },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('basic rendering', () => {
    it('renders all section buttons', () => {
      render(<SectionNav sections={mockSections} />)

      expect(screen.getByRole('button', { name: 'Your favorites' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Quick meals' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Recently added' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Italian' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Mexican' })).toBeInTheDocument()
    })

    it('renders as a nav element', () => {
      const { container } = render(<SectionNav sections={mockSections} />)
      const nav = container.querySelector('nav')
      expect(nav).toBeInTheDocument()
    })

    it('renders empty nav when sections array is empty', () => {
      const { container } = render(<SectionNav sections={[]} />)
      const nav = container.querySelector('nav')
      expect(nav).toBeInTheDocument()
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })
  })

  describe('section navigation', () => {
    it('scrolls to section when button is clicked', async () => {
      const user = userEvent.setup()

      // Create mock section elements in the DOM
      document.body.innerHTML = `
        <div id="favorites">Favorites Section</div>
        <div id="quick-meals">Quick Meals Section</div>
      `

      const mockScrollTo = vi.fn()
      window.scrollTo = mockScrollTo

      render(<SectionNav sections={mockSections} />)

      const favoritesButton = screen.getByRole('button', { name: 'Your favorites' })
      await user.click(favoritesButton)

      expect(mockScrollTo).toHaveBeenCalledWith({
        top: expect.any(Number),
        behavior: 'smooth',
      })
    })

    it('calculates correct scroll offset (accounting for nav height + padding)', async () => {
      const user = userEvent.setup()

      // Create mock section element
      const mockElement = document.createElement('div')
      mockElement.id = 'favorites'
      document.body.appendChild(mockElement)

      const mockScrollTo = vi.fn()
      window.scrollTo = mockScrollTo

      // Mock getBoundingClientRect to return a known position
      vi.spyOn(mockElement, 'getBoundingClientRect').mockReturnValue({
        top: 500,
        bottom: 600,
        left: 0,
        right: 0,
        width: 0,
        height: 100,
        x: 0,
        y: 500,
        toJSON: () => ({}),
      })

      Object.defineProperty(window, 'scrollY', { value: 0, writable: true })

      render(<SectionNav sections={mockSections} />)

      const favoritesButton = screen.getByRole('button', { name: 'Your favorites' })
      await user.click(favoritesButton)

      // Should scroll to: element position (500) + scrollY (0) - offset (120) = 380
      expect(mockScrollTo).toHaveBeenCalledWith({
        top: 380,
        behavior: 'smooth',
      })

      document.body.removeChild(mockElement)
    })

    it('handles missing section elements gracefully', async () => {
      const user = userEvent.setup()

      const mockScrollTo = vi.fn()
      window.scrollTo = mockScrollTo

      render(<SectionNav sections={mockSections} />)

      const italianButton = screen.getByRole('button', { name: 'Italian' })
      await user.click(italianButton)

      // Should not throw error, and should not call scrollTo
      expect(mockScrollTo).not.toHaveBeenCalled()
    })
  })

  describe('styling', () => {
    it('applies sticky positioning', () => {
      const { container } = render(<SectionNav sections={mockSections} />)
      const nav = container.querySelector('nav')
      expect(nav).toHaveClass('sticky')
      expect(nav).toHaveClass('top-0')
    })

    it('applies z-index for stacking context', () => {
      const { container } = render(<SectionNav sections={mockSections} />)
      const nav = container.querySelector('nav')
      expect(nav).toHaveClass('z-10')
    })

    it('applies background color for contrast', () => {
      const { container } = render(<SectionNav sections={mockSections} />)
      const nav = container.querySelector('nav')
      expect(nav).toHaveClass('bg-cream-light')
    })

    it('applies border bottom for visual separation', () => {
      const { container } = render(<SectionNav sections={mockSections} />)
      const nav = container.querySelector('nav')
      expect(nav).toHaveClass('border-b')
      expect(nav).toHaveClass('border-warm-border')
    })

    it('applies horizontal scroll with hidden scrollbar', () => {
      const { container } = render(<SectionNav sections={mockSections} />)
      const scrollContainer = container.querySelector('.overflow-x-auto')
      expect(scrollContainer).toBeInTheDocument()
      expect(scrollContainer).toHaveClass('scrollbar-hide')
    })

    it('applies whitespace-nowrap to prevent button wrapping', () => {
      render(<SectionNav sections={mockSections} />)
      const button = screen.getByRole('button', { name: 'Your favorites' })
      expect(button).toHaveClass('whitespace-nowrap')
    })
  })

  describe('button interaction', () => {
    it('applies hover styles to buttons', () => {
      render(<SectionNav sections={mockSections} />)
      const button = screen.getByRole('button', { name: 'Quick meals' })

      expect(button).toHaveClass('hover:text-text-primary')
      expect(button).toHaveClass('hover:bg-warm-gray')
    })

    it('buttons are keyboard accessible', async () => {
      const user = userEvent.setup()
      render(<SectionNav sections={mockSections} />)

      await user.tab()
      const firstButton = screen.getByRole('button', { name: 'Your favorites' })
      expect(firstButton).toHaveFocus()

      await user.tab()
      const secondButton = screen.getByRole('button', { name: 'Quick meals' })
      expect(secondButton).toHaveFocus()
    })
  })

  describe('accessibility', () => {
    it('uses semantic nav element', () => {
      const { container } = render(<SectionNav sections={mockSections} />)
      const nav = container.querySelector('nav')
      expect(nav?.tagName).toBe('NAV')
    })

    it('buttons have clear accessible text', () => {
      render(<SectionNav sections={mockSections} />)

      mockSections.forEach((section) => {
        const button = screen.getByRole('button', { name: section.label })
        expect(button.textContent).toBe(section.label)
      })
    })
  })

  describe('responsiveness', () => {
    it('applies flex-shrink-0 to buttons for horizontal scrolling', () => {
      render(<SectionNav sections={mockSections} />)
      const button = screen.getByRole('button', { name: 'Italian' })
      expect(button).toHaveClass('flex-shrink-0')
    })

    it('handles long section labels without breaking layout', () => {
      const longSections = [
        { id: 'very-long', label: 'This is a very long section name that should not wrap' },
      ]
      render(<SectionNav sections={longSections} />)
      const button = screen.getByRole('button', {
        name: 'This is a very long section name that should not wrap',
      })
      expect(button).toHaveClass('whitespace-nowrap')
      expect(button).toHaveClass('flex-shrink-0')
    })
  })

  describe('edge cases', () => {
    it('handles single section', () => {
      const singleSection = [{ id: 'only', label: 'Only Section' }]
      render(<SectionNav sections={singleSection} />)
      expect(screen.getByRole('button', { name: 'Only Section' })).toBeInTheDocument()
    })

    it('handles sections with special characters in labels', () => {
      const specialSections = [
        { id: 'special', label: "Chef's favorites & specials" },
      ]
      render(<SectionNav sections={specialSections} />)
      expect(screen.getByRole('button', { name: "Chef's favorites & specials" })).toBeInTheDocument()
    })

    it('handles sections with duplicate labels but unique ids', () => {
      const duplicateLabelSections = [
        { id: 'italian-1', label: 'Italian' },
        { id: 'italian-2', label: 'Italian' },
      ]
      render(<SectionNav sections={duplicateLabelSections} />)
      const buttons = screen.getAllByRole('button', { name: 'Italian' })
      expect(buttons).toHaveLength(2)
    })
  })
})
