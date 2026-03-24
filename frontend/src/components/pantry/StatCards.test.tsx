import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatCards from './StatCards'

describe('StatCards', () => {
  it('renders all three stat cards', () => {
    render(<StatCards totalItems={10} expiringSoonCount={3} lowStockCount={2} />)

    expect(screen.getByText('Total Items')).toBeInTheDocument()
    expect(screen.getByText('Expiring Soon')).toBeInTheDocument()
    expect(screen.getByText('Low Stock')).toBeInTheDocument()
  })

  it('displays correct values for each stat', () => {
    render(<StatCards totalItems={15} expiringSoonCount={4} lowStockCount={3} />)

    expect(screen.getByText('15')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('displays descriptions for each stat', () => {
    render(<StatCards totalItems={10} expiringSoonCount={3} lowStockCount={2} />)

    expect(screen.getByText('in pantry')).toBeInTheDocument()
    expect(screen.getByText('within 3 days')).toBeInTheDocument()
    expect(screen.getByText('staples')).toBeInTheDocument()
  })

  it('renders with zero values', () => {
    render(<StatCards totalItems={0} expiringSoonCount={0} lowStockCount={0} />)

    const zeroValues = screen.getAllByText('0')
    expect(zeroValues).toHaveLength(3)
  })

  it('applies correct styling to card container', () => {
    const { container } = render(
      <StatCards totalItems={10} expiringSoonCount={3} lowStockCount={2} />
    )

    const grid = container.querySelector('.grid')
    expect(grid).toBeInTheDocument()
    expect(grid?.className).toContain('grid-cols-1')
    expect(grid?.className).toContain('sm:grid-cols-3')
  })

  it('applies cream-dark background to cards', () => {
    const { container } = render(
      <StatCards totalItems={10} expiringSoonCount={3} lowStockCount={2} />
    )

    const cards = container.querySelectorAll('.bg-cream-dark')
    expect(cards).toHaveLength(3)
  })

  it('renders large numbers correctly', () => {
    render(<StatCards totalItems={999} expiringSoonCount={50} lowStockCount={25} />)

    expect(screen.getByText('999')).toBeInTheDocument()
    expect(screen.getByText('50')).toBeInTheDocument()
    expect(screen.getByText('25')).toBeInTheDocument()
  })
})
