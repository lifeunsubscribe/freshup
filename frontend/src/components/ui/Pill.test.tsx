import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Pill from './Pill'

describe('Pill', () => {
  it('renders children text correctly', () => {
    render(<Pill>Status Badge</Pill>)
    expect(screen.getByText('Status Badge')).toBeInTheDocument()
  })

  it('renders as span element', () => {
    render(<Pill>Test</Pill>)
    const pill = screen.getByText('Test')
    expect(pill.tagName).toBe('SPAN')
  })

  describe('variant styles', () => {
    it('renders default variant with correct styles', () => {
      render(<Pill variant="default">Default</Pill>)
      const pill = screen.getByText('Default')

      // Default: cream background with primary text and border
      expect(pill.className).toContain('bg-cream')
      expect(pill.className).toContain('text-text-primary')
      expect(pill.className).toContain('border')
      expect(pill.className).toContain('border-warm-border')
    })

    it('renders success variant with correct styles', () => {
      render(<Pill variant="success">Success</Pill>)
      const pill = screen.getByText('Success')

      // Success: olive background with cream text
      expect(pill.className).toContain('bg-olive')
      expect(pill.className).toContain('text-cream')
    })

    it('renders warning variant with correct styles', () => {
      render(<Pill variant="warning">Warning</Pill>)
      const pill = screen.getByText('Warning')

      // Warning: mocha background with cream text
      expect(pill.className).toContain('bg-mocha')
      expect(pill.className).toContain('text-cream')
    })

    it('renders alert variant with correct styles', () => {
      render(<Pill variant="alert">Alert</Pill>)
      const pill = screen.getByText('Alert')

      // Alert: terra background with cream text
      expect(pill.className).toContain('bg-terra')
      expect(pill.className).toContain('text-cream')
    })

    it('uses default variant when no variant is specified', () => {
      render(<Pill>No Variant</Pill>)
      const pill = screen.getByText('No Variant')

      // Should use default variant styles
      expect(pill.className).toContain('bg-cream')
      expect(pill.className).toContain('text-text-primary')
    })
  })

  describe('common styles', () => {
    it('applies correct typography and spacing classes', () => {
      render(<Pill>Test</Pill>)
      const pill = screen.getByText('Test')

      // Should have inline-block display
      expect(pill.className).toContain('inline-block')
      // Should have padding: px-3 py-1
      expect(pill.className).toContain('px-3')
      expect(pill.className).toContain('py-1')
      // Should have text-sm
      expect(pill.className).toContain('text-sm')
      // Should have font-medium
      expect(pill.className).toContain('font-medium')
      // Should have 6px border radius
      expect(pill.className).toContain('rounded-[6px]')
    })

    it('applies common styles to all variants', () => {
      const variants = ['default', 'success', 'warning', 'alert'] as const

      variants.forEach((variant) => {
        const { container } = render(<Pill variant={variant}>{variant}</Pill>)
        const pill = screen.getByText(variant)

        expect(pill.className).toContain('inline-block')
        expect(pill.className).toContain('px-3')
        expect(pill.className).toContain('py-1')
        expect(pill.className).toContain('text-sm')
        expect(pill.className).toContain('font-medium')
        expect(pill.className).toContain('rounded-[6px]')

        container.remove()
      })
    })
  })

  it('renders complex children with nested elements', () => {
    render(
      <Pill>
        <span>Complex</span> Content
      </Pill>
    )
    expect(screen.getByText(/Complex Content/i)).toBeInTheDocument()
  })

  it('renders empty children', () => {
    const { container } = render(<Pill></Pill>)
    const span = container.querySelector('span')
    expect(span).toBeInTheDocument()
    expect(span).toHaveTextContent('')
  })

  it('handles numeric children', () => {
    render(<Pill>42</Pill>)
    expect(screen.getByText('42')).toBeInTheDocument()
  })
})
