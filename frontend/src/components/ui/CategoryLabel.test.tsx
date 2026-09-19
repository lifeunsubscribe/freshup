import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import CategoryLabel from './CategoryLabel'

/**
 * Note on the uppercase assertions.
 *
 * CategoryLabel uppercases with the CSS `uppercase` class, not by changing the
 * string. jsdom does not apply text-transform to textContent, so the DOM still
 * holds whatever was passed in — `getByText('PRODUCE')` can never match
 * `<CategoryLabel>Produce</CategoryLabel>`. These tests now query the text as
 * authored and assert the class that performs the visual transform.
 */
describe('CategoryLabel', () => {
  it('renders children text correctly', () => {
    render(<CategoryLabel>Produce</CategoryLabel>)
    expect(screen.getByText('Produce')).toBeInTheDocument()
  })

  it('uppercases via CSS rather than rewriting the text', () => {
    render(<CategoryLabel>dairy products</CategoryLabel>)
    const label = screen.getByText('dairy products')
    expect(label).toHaveClass('uppercase')
  })

  it('renders as span element', () => {
    render(<CategoryLabel>Test</CategoryLabel>)
    expect(screen.getByText('Test').tagName).toBe('SPAN')
  })

  it('applies correct typography classes', () => {
    render(<CategoryLabel>Category</CategoryLabel>)
    const label = screen.getByText('Category')

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
    const { container } = render(
      <CategoryLabel>
        <span>Complex</span> Label
      </CategoryLabel>
    )
    // Text spans a nested element and a sibling text node, so assert on the
    // label's combined content rather than a single text node.
    expect(container.querySelector('span')).toHaveTextContent('Complex Label')
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
    const label = screen.getByText('FrEsH fOoD')
    expect(label).toHaveClass('uppercase')
  })
})
