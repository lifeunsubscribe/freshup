import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PageTitle from './PageTitle'

describe('PageTitle', () => {
  it('renders children text correctly', () => {
    render(<PageTitle>Pantry</PageTitle>)
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Pantry.')
  })

  it('appends olive period suffix to the text', () => {
    render(<PageTitle>My Page</PageTitle>)
    const heading = screen.getByRole('heading', { level: 1 })

    // Check that the period is present
    expect(heading).toHaveTextContent('My Page.')

    // Check that the period has the olive color class
    const periodSpan = heading.querySelector('span.text-olive')
    expect(periodSpan).toBeTruthy()
    expect(periodSpan).toHaveTextContent('.')
  })

  it('renders as h1 element', () => {
    render(<PageTitle>Test Title</PageTitle>)
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading.tagName).toBe('H1')
  })

  it('applies correct typography classes', () => {
    render(<PageTitle>Test</PageTitle>)
    const heading = screen.getByRole('heading', { level: 1 })

    // Should have 22px font size
    expect(heading.className).toContain('text-[22px]')
    // Should have font-medium (500 weight)
    expect(heading.className).toContain('font-medium')
    // Should have primary text color
    expect(heading.className).toContain('text-text-primary')
    // Should have tight leading
    expect(heading.className).toContain('leading-tight')
  })

  it('renders complex children with nested elements', () => {
    render(
      <PageTitle>
        <span>Complex</span> Title
      </PageTitle>
    )
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent('Complex Title.')
  })

  it('renders empty children with just the period', () => {
    render(<PageTitle></PageTitle>)
    const heading = screen.getByRole('heading', { level: 1 })
    expect(heading).toHaveTextContent('.')
  })
})
