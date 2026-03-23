import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import CategoryLabel from './CategoryLabel'

describe('CategoryLabel', () => {
  it('renders children text correctly', () => {
    render(<CategoryLabel>Produce</CategoryLabel>)
    expect(screen.getByText('PRODUCE')).toBeInTheDocument()
  })

  it('transforms text to uppercase', () => {
    render(<CategoryLabel>dairy products</CategoryLabel>)
    expect(screen.getByText('DAIRY PRODUCTS')).toBeInTheDocument()
  })

  it('renders as span element', () => {
    render(<CategoryLabel>Test</CategoryLabel>)
    const label = screen.getByText('TEST')
    expect(label.tagName).toBe('SPAN')
  })

  it('applies correct typography classes', () => {
    render(<CategoryLabel>Category</CategoryLabel>)
    const label = screen.getByText('CATEGORY')

    // Should have 12px font size (text-xs)
    expect(label.className).toContain('text-xs')
    // Should have uppercase
    expect(label.className).toContain('uppercase')
    // Should have 0.06em letter spacing
    expect(label.className).toContain('tracking-[0.06em]')
    // Should have tertiary text color for subtle appearance
    expect(label.className).toContain('text-text-tertiary')
    // Should have font-medium
    expect(label.className).toContain('font-medium')
  })

  it('renders complex children with nested elements', () => {
    render(
      <CategoryLabel>
        <span>Complex</span> Label
      </CategoryLabel>
    )
    // The text should still be uppercased by CSS
    const label = screen.getByText(/COMPLEX LABEL/i)
    expect(label).toBeInTheDocument()
  })

  it('renders empty children', () => {
    const { container } = render(<CategoryLabel></CategoryLabel>)
    const span = container.querySelector('span')
    expect(span).toBeInTheDocument()
    expect(span).toHaveTextContent('')
  })

  it('preserves already uppercase text', () => {
    render(<CategoryLabel>FROZEN</CategoryLabel>)
    expect(screen.getByText('FROZEN')).toBeInTheDocument()
  })

  it('handles mixed case text', () => {
    render(<CategoryLabel>FrEsH fOoD</CategoryLabel>)
    expect(screen.getByText('FRESH FOOD')).toBeInTheDocument()
  })
})
