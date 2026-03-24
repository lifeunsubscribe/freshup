import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import LowStockSection from './LowStockSection'
import type { LowStockAlertItem } from '../../api/types'

describe('LowStockSection', () => {
  const mockItems: LowStockAlertItem[] = [
    {
      id: '1',
      name: 'Rice',
      quantity: 1,
      unit: 'lb',
      minimum_threshold: 5,
      deficit: 4,
    },
    {
      id: '2',
      name: 'Flour',
      quantity: 0.5,
      unit: 'lb',
      minimum_threshold: 2,
      deficit: 1.5,
    },
  ]

  it('renders section header', () => {
    render(<LowStockSection items={[]} />)
    expect(screen.getByText('Low Stock Alerts')).toBeInTheDocument()
  })

  it('displays empty state when no items', () => {
    render(<LowStockSection items={[]} />)
    expect(screen.getByText('Stock levels healthy')).toBeInTheDocument()
  })

  it('renders low stock items when provided', () => {
    render(<LowStockSection items={mockItems} />)
    expect(screen.getByText('Rice')).toBeInTheDocument()
    expect(screen.getByText('Flour')).toBeInTheDocument()
  })

  it('displays quantity and threshold for each item', () => {
    render(<LowStockSection items={mockItems} />)
    expect(screen.getByText('1 / 5 lb')).toBeInTheDocument()
    expect(screen.getByText('0.5 / 2 lb')).toBeInTheDocument()
  })

  it('displays deficit message for each item', () => {
    render(<LowStockSection items={mockItems} />)
    expect(screen.getByText('Need 4 lb more to reach threshold')).toBeInTheDocument()
    expect(screen.getByText('Need 1.5 lb more to reach threshold')).toBeInTheDocument()
  })

  it('renders progress bar for each item', () => {
    const { container } = render(<LowStockSection items={mockItems} />)
    const progressBars = container.querySelectorAll('.bg-terra')
    expect(progressBars).toHaveLength(2)
  })

  it('calculates correct progress bar width', () => {
    const { container } = render(<LowStockSection items={[mockItems[0]]} />)
    const progressBar = container.querySelector('.bg-terra') as HTMLElement

    // Rice: 1 / 5 = 20%
    expect(progressBar?.style.width).toBe('20%')
  })

  it('caps progress bar at 100% for items at or above threshold', () => {
    const itemAtThreshold: LowStockAlertItem = {
      id: '3',
      name: 'Sugar',
      quantity: 5,
      unit: 'lb',
      minimum_threshold: 5,
      deficit: 0,
    }

    const { container } = render(<LowStockSection items={[itemAtThreshold]} />)
    const progressBar = container.querySelector('.bg-terra') as HTMLElement

    expect(progressBar?.style.width).toBe('100%')
  })

  it('applies correct styling classes', () => {
    const { container } = render(<LowStockSection items={[]} />)

    const card = container.querySelector('.bg-cream-dark')
    expect(card).toBeInTheDocument()
    expect(card?.className).toContain('rounded-card')
    expect(card?.className).toContain('border')
    expect(card?.className).toContain('border-warm-border')
  })
})
