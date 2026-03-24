import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import CategoryGroup from './CategoryGroup'
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

describe('CategoryGroup', () => {
  const mockItems: InventoryItemListResponse[] = [
    {
      id: '1',
      name: 'Tomato',
      quantity: 3,
      unit: 'count',
      category: 'produce',
      storage_location: 'fridge',
      date_added: '2024-01-01',
      expiration_date: '2024-01-10',
      is_staple: false,
      shareability: 'shared',
    },
    {
      id: '2',
      name: 'Lettuce',
      quantity: 1,
      unit: 'head',
      category: 'produce',
      storage_location: 'fridge',
      date_added: '2024-01-02',
      expiration_date: '2024-01-08',
      is_staple: false,
      shareability: 'shared',
    },
  ]

  it('renders formatted category name', () => {
    render(<CategoryGroup category="produce" items={mockItems} />, {
      wrapper: createWrapper(),
    })
    expect(screen.getByText('Produce')).toBeInTheDocument()
  })

  it('formats category name with underscores', () => {
    render(<CategoryGroup category="dairy_products" items={mockItems} />, {
      wrapper: createWrapper(),
    })
    expect(screen.getByText('Dairy Products')).toBeInTheDocument()
  })

  it('displays item count', () => {
    render(<CategoryGroup category="produce" items={mockItems} />, {
      wrapper: createWrapper(),
    })
    expect(screen.getByText('(2 items)')).toBeInTheDocument()
  })

  it('displays singular "item" for single item', () => {
    render(<CategoryGroup category="produce" items={[mockItems[0]]} />, {
      wrapper: createWrapper(),
    })
    expect(screen.getByText('(1 item)')).toBeInTheDocument()
  })

  it('starts expanded by default', () => {
    render(<CategoryGroup category="produce" items={mockItems} />, {
      wrapper: createWrapper(),
    })
    expect(screen.getByText('Tomato')).toBeInTheDocument()
    expect(screen.getByText('Lettuce')).toBeInTheDocument()
  })

  it('collapses when header is clicked', () => {
    render(<CategoryGroup category="produce" items={mockItems} />, {
      wrapper: createWrapper(),
    })

    const header = screen.getByRole('button')
    fireEvent.click(header)

    expect(screen.queryByText('Tomato')).not.toBeInTheDocument()
    expect(screen.queryByText('Lettuce')).not.toBeInTheDocument()
  })

  it('expands when header is clicked again', () => {
    render(<CategoryGroup category="produce" items={mockItems} />, {
      wrapper: createWrapper(),
    })

    const header = screen.getByRole('button')

    // Collapse
    fireEvent.click(header)
    expect(screen.queryByText('Tomato')).not.toBeInTheDocument()

    // Expand
    fireEvent.click(header)
    expect(screen.getByText('Tomato')).toBeInTheDocument()
    expect(screen.getByText('Lettuce')).toBeInTheDocument()
  })

  it('renders chevron icon', () => {
    const { container } = render(
      <CategoryGroup category="produce" items={mockItems} />,
      { wrapper: createWrapper() }
    )

    const chevron = container.querySelector('svg')
    expect(chevron).toBeInTheDocument()
  })

  it('rotates chevron when collapsed', () => {
    const { container } = render(
      <CategoryGroup category="produce" items={mockItems} />,
      { wrapper: createWrapper() }
    )

    const chevron = container.querySelector('svg')

    // Initially expanded, chevron should have rotate-180
    expect(chevron?.className).toContain('rotate-180')

    // Collapse
    const header = screen.getByRole('button')
    fireEvent.click(header)

    // After collapse, chevron should not have rotate-180
    expect(chevron?.className).not.toContain('rotate-180')
  })

  it('renders header as button element', () => {
    render(<CategoryGroup category="produce" items={mockItems} />, {
      wrapper: createWrapper(),
    })

    const header = screen.getByRole('button')
    expect(header.tagName).toBe('BUTTON')
    expect(header).toHaveAttribute('type', 'button')
  })

  it('applies correct styling classes', () => {
    const { container } = render(
      <CategoryGroup category="produce" items={mockItems} />,
      { wrapper: createWrapper() }
    )

    const card = container.querySelector('.bg-cream-dark')
    expect(card).toBeInTheDocument()
    expect(card?.className).toContain('rounded-card')
    expect(card?.className).toContain('border')
    expect(card?.className).toContain('border-warm-border')
  })

  it('renders all items as InventoryRow components', () => {
    render(<CategoryGroup category="produce" items={mockItems} />, {
      wrapper: createWrapper(),
    })

    mockItems.forEach((item) => {
      expect(screen.getByText(item.name)).toBeInTheDocument()
    })
  })
})
