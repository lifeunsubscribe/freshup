import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import ExpiringSection from './ExpiringSection'
import type { InventoryItemListResponse } from '../../api/types'

// Create a wrapper with QueryClient for InventoryRow (which uses mutations)
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('ExpiringSection', () => {
  const mockItems: InventoryItemListResponse[] = [
    {
      id: '1',
      name: 'Milk',
      quantity: 1,
      unit: 'qt',
      category: 'dairy',
      storage_location: 'fridge',
      date_added: '2024-01-01',
      expiration_date: '2024-01-05',
      is_staple: false,
      shareability: 'shared',
    },
    {
      id: '2',
      name: 'Yogurt',
      quantity: 2,
      unit: 'cups',
      category: 'dairy',
      storage_location: 'fridge',
      date_added: '2024-01-01',
      expiration_date: '2024-01-03',
      is_staple: false,
      shareability: 'shared',
    },
  ]

  it('renders section header', () => {
    render(<ExpiringSection items={[]} />, { wrapper: createWrapper() })
    expect(screen.getByText('Expiring Soon')).toBeInTheDocument()
  })

  it('displays empty state when no items', () => {
    render(<ExpiringSection items={[]} />, { wrapper: createWrapper() })
    expect(screen.getByText('Nothing expiring soon')).toBeInTheDocument()
  })

  it('renders inventory items when provided', () => {
    render(<ExpiringSection items={mockItems} />, { wrapper: createWrapper() })
    expect(screen.getByText('Milk')).toBeInTheDocument()
    expect(screen.getByText('Yogurt')).toBeInTheDocument()
  })

  it('sorts items by expiration date (soonest first)', () => {
    render(<ExpiringSection items={mockItems} />, { wrapper: createWrapper() })

    const items = screen.getAllByText(/Milk|Yogurt/)
    // Yogurt expires on 01-03, Milk expires on 01-05
    expect(items[0]).toHaveTextContent('Yogurt')
    expect(items[1]).toHaveTextContent('Milk')
  })

  it('handles items without expiration date', () => {
    const itemsWithNull: InventoryItemListResponse[] = [
      {
        ...mockItems[0],
        expiration_date: null,
      },
      mockItems[1],
    ]

    render(<ExpiringSection items={itemsWithNull} />, { wrapper: createWrapper() })
    expect(screen.getByText('Yogurt')).toBeInTheDocument()
  })

  it('applies correct styling classes', () => {
    const { container } = render(<ExpiringSection items={[]} />, {
      wrapper: createWrapper(),
    })

    const card = container.querySelector('.bg-cream-dark')
    expect(card).toBeInTheDocument()
    expect(card?.className).toContain('rounded-card')
    expect(card?.className).toContain('border')
    expect(card?.className).toContain('border-warm-border')
  })
})
