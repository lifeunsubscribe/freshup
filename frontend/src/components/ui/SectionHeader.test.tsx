import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import SectionHeader from './SectionHeader'

describe('SectionHeader', () => {
  it('renders children text correctly', () => {
    render(<SectionHeader>Fresh Items</SectionHeader>)
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Fresh Items.')
  })

  it('appends olive period suffix to the text', () => {
    render(<SectionHeader>My Section</SectionHeader>)
    const heading = screen.getByRole('heading', { level: 2 })

    // Check that the period is present
    expect(heading).toHaveTextContent('My Section.')

    // Check that the period has the olive color class
    const periodSpan = heading.querySelector('span.text-olive')
    expect(periodSpan).toBeTruthy()
    expect(periodSpan).toHaveTextContent('.')
  })

  it('renders as h2 element', () => {
    render(<SectionHeader>Test Section</SectionHeader>)
    const heading = screen.getByRole('heading', { level: 2 })
    expect(heading.tagName).toBe('H2')
  })

  it('applies correct typography classes', () => {
    render(<SectionHeader>Test</SectionHeader>)
    const heading = screen.getByRole('heading', { level: 2 })

    // Should have 15px font size
    expect(heading.className).toContain('text-[15px]')
    // Should have font-medium (500 weight)
    expect(heading.className).toContain('font-medium')
    // Should have primary text color
    expect(heading.className).toContain('text-text-primary')
    // Should have tight leading
    expect(heading.className).toContain('leading-tight')
  })

  it('renders complex children with nested elements', () => {
    render(
      <SectionHeader>
        <span>Complex</span> Section
      </SectionHeader>
    )
    const heading = screen.getByRole('heading', { level: 2 })
    expect(heading).toHaveTextContent('Complex Section.')
  })

  it('renders empty children with just the period', () => {
    render(<SectionHeader></SectionHeader>)
    const heading = screen.getByRole('heading', { level: 2 })
    expect(heading).toHaveTextContent('.')
  })
})
