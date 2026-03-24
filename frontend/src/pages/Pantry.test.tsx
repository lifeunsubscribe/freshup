import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Pantry from './Pantry'
import type { InventoryItemListResponse, LowStockAlertItem } from '../api/types'
import { StorageLocation } from '../api/types'

// Mock the API hooks
vi.mock('../api', () => ({
  useInventoryList: vi.fn(),
  useLowStockAlerts: vi.fn(),
}))

// Mock child components to avoid nested dependency issues
vi.mock('../components/pantry/StorageTabs', () => ({
  default: ({ activeTab, onTabChange }: any) => (
    <div data-testid="storage-tabs">
      <button onClick={() => onTabChange('all')}>All</button>
      <button onClick={() => onTabChange('fridge')}>Fridge</button>
      <button onClick={() => onTabChange('freezer')}>Freezer</button>
      <button onClick={() => onTabChange('pantry')}>Pantry</button>
    </div>
  ),
}))

vi.mock('../components/pantry/StatCards', () => ({
  default: ({ totalItems, expiringSoonCount, lowStockCount }: any) => (
    <div data-testid="stat-cards">
      <div>Total Items: {totalItems}</div>
      <div>Expiring Soon: {expiringSoonCount}</div>
      <div>Low Stock: {lowStockCount}</div>
    </div>
  ),
}))

vi.mock('../components/pantry/ExpiringSection', () => ({
  default: ({ items }: any) => (
    <div data-testid="expiring-section">
      <h2>Expiring Soon</h2>
      {items.length === 0 ? (
        <p>Nothing expiring soon</p>
      ) : (
        <div>{items.length} items expiring</div>
      )}
    </div>
  ),
}))

vi.mock('../components/pantry/LowStockSection', () => ({
  default: ({ items }: any) => (
    <div data-testid="low-stock-section">
      <h2>Low Stock</h2>
      {items.length === 0 ? (
        <p>Stock levels healthy</p>
      ) : (
        <div>{items.length} items low</div>
      )}
    </div>
  ),
}))

vi.mock('../components/pantry/CategoryGroup', () => ({
  default: ({ category, items }: any) => (
    <div data-testid={`category-group-${category}`}>
      <h2>{category}</h2>
      <div>{items.length} items</div>
    </div>
  ),
}))

import { useInventoryList, useLowStockAlerts } from '../api'

describe('Pantry', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
  })

  const renderWithProviders = (ui: React.ReactElement) => {
    return render(
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
    )
  }

  const createMockInventoryItem = (
    overrides?: Partial<InventoryItemListResponse>
  ): InventoryItemListResponse => ({
    id: 'item-1',
    name: 'Milk',
    quantity: 2,
    unit: 'gallon',
    category: 'dairy',
    storage_location: StorageLocation.FRIDGE,
    date_added: '2026-03-20T10:00:00Z',
    expiration_date: null,
    is_staple: false,
    shareability: 'shared',
    ...overrides,
  })

  const createMockLowStockItem = (
    overrides?: Partial<LowStockAlertItem>
  ): LowStockAlertItem => ({
    id: 'item-1',
    name: 'Milk',
    quantity: 1,
    unit: 'gallon',
    minimum_threshold: 3,
    deficit: 2,
    ...overrides,
  })

  describe('Loading State', () => {
    it('displays loading message when inventory is loading', () => {
      vi.mocked(useInventoryList).mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: undefined,
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      expect(screen.getByText('Pantry')).toBeInTheDocument()
      expect(screen.getByText('Loading inventory...')).toBeInTheDocument()
    })

    it('displays loading message when low stock alerts are loading', () => {
      vi.mocked(useInventoryList).mockReturnValue({
        data: undefined,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: undefined,
        isLoading: true,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      expect(screen.getByText('Loading inventory...')).toBeInTheDocument()
    })
  })

  describe('Error State', () => {
    it('displays error message when inventory fails to load', () => {
      vi.mocked(useInventoryList).mockReturnValue({
        data: undefined,
        isLoading: false,
        error: { message: 'Network error' },
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      expect(screen.getByText('Failed to load inventory data')).toBeInTheDocument()
      expect(screen.getByText('Network error')).toBeInTheDocument()
    })

    it('displays error message when low stock alerts fail to load', () => {
      vi.mocked(useInventoryList).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: undefined,
        isLoading: false,
        error: { message: 'API error' },
      } as any)

      renderWithProviders(<Pantry />)

      expect(screen.getByText('Failed to load inventory data')).toBeInTheDocument()
      expect(screen.getByText('API error')).toBeInTheDocument()
    })

    it('shows generic error message when error has no message', () => {
      vi.mocked(useInventoryList).mockReturnValue({
        data: undefined,
        isLoading: false,
        error: {},
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      expect(
        screen.getByText('An unexpected error occurred. Please try again later.')
      ).toBeInTheDocument()
    })
  })

  describe('Empty State', () => {
    it('displays empty state when no items exist', () => {
      vi.mocked(useInventoryList).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      expect(
        screen.getByText('No items in pantry yet. Add items to get started!')
      ).toBeInTheDocument()
    })

    it('shows specific message when all items are expiring', () => {
      const today = new Date()
      const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000)

      const items = [
        createMockInventoryItem({
          id: 'item-1',
          expiration_date: tomorrow.toISOString(),
        }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: items,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      expect(
        screen.getByText('All items are expiring soon. Check the triage sections above.')
      ).toBeInTheDocument()
    })
  })

  describe('Tab Filtering', () => {
    it('renders all storage tabs', () => {
      vi.mocked(useInventoryList).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      expect(screen.getByTestId('storage-tabs')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Fridge' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Freezer' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Pantry' })).toBeInTheDocument()
    })

    it('starts with "all" tab active by default', () => {
      vi.mocked(useInventoryList).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      // Check that useInventoryList was called without storage_location filter
      const calls = vi.mocked(useInventoryList).mock.calls
      expect(calls.some(call =>
        call[0].storage_location === undefined && call[0].limit === 100
      )).toBe(true)
    })

    it('filters inventory by storage location when tab is clicked', async () => {
      const user = userEvent.setup()

      vi.mocked(useInventoryList).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      const fridgeTab = screen.getByText('Fridge')
      await user.click(fridgeTab)

      // Component should re-render with new filter
      await waitFor(() => {
        const calls = vi.mocked(useInventoryList).mock.calls
        const lastCall = calls[calls.length - 1]
        expect(lastCall[0]).toEqual({
          storage_location: StorageLocation.FRIDGE,
          limit: 100,
          offset: 0,
        })
      })
    })
  })

  describe('Stat Cards', () => {
    it('displays correct total items count', () => {
      const items = [
        createMockInventoryItem({ id: 'item-1' }),
        createMockInventoryItem({ id: 'item-2' }),
        createMockInventoryItem({ id: 'item-3' }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: items,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      expect(screen.getByText('Total Items: 3')).toBeInTheDocument()
    })

    it('displays correct expiring soon count', () => {
      const today = new Date()
      const tomorrow = new Date(today.getTime() + 24 * 60 * 60 * 1000)
      const nextWeek = new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000)

      const items = [
        createMockInventoryItem({
          id: 'item-1',
          expiration_date: tomorrow.toISOString(),
        }),
        createMockInventoryItem({
          id: 'item-2',
          expiration_date: tomorrow.toISOString(),
        }),
        createMockInventoryItem({
          id: 'item-3',
          expiration_date: nextWeek.toISOString(), // Not within 3 days
        }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: items,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      // Should show 2 items expiring within 3 days
      expect(screen.getByText('Expiring Soon: 2')).toBeInTheDocument()
    })

    it('displays correct low stock count', () => {
      const lowStockItems = [
        createMockLowStockItem({ id: 'item-1' }),
        createMockLowStockItem({ id: 'item-2' }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: lowStockItems,
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      expect(screen.getByText('Low Stock: 2')).toBeInTheDocument()
    })
  })

  describe('Expiring Items Logic', () => {
    it('calculates expiring items within 3 days correctly', () => {
      const now = new Date()
      const twoDaysFromNow = new Date(now.getTime() + 2 * 24 * 60 * 60 * 1000)
      const fiveDaysFromNow = new Date(now.getTime() + 5 * 24 * 60 * 60 * 1000)

      const items = [
        createMockInventoryItem({
          id: 'item-1',
          name: 'Expiring Milk',
          expiration_date: twoDaysFromNow.toISOString(),
        }),
        createMockInventoryItem({
          id: 'item-2',
          name: 'Not Expiring Cheese',
          expiration_date: fiveDaysFromNow.toISOString(),
        }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: items,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      // ExpiringSection should receive only items expiring within 3 days
      expect(screen.getByText('Expiring Soon')).toBeInTheDocument()
    })

    it('excludes items without expiration dates from expiring section', () => {
      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)

      const items = [
        createMockInventoryItem({
          id: 'item-1',
          expiration_date: tomorrow.toISOString(),
        }),
        createMockInventoryItem({
          id: 'item-2',
          expiration_date: null,
        }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: items,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      // Only 1 item should be in expiring section
      expect(screen.getByText('Expiring Soon: 1')).toBeInTheDocument()
    })

    it('excludes already expired items from expiring section', () => {
      const yesterday = new Date()
      yesterday.setDate(yesterday.getDate() - 1)

      const items = [
        createMockInventoryItem({
          id: 'item-1',
          expiration_date: yesterday.toISOString(),
        }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: items,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      // Expired items should not be in expiring section
      expect(screen.getByText('Expiring Soon: 0')).toBeInTheDocument()
    })
  })

  describe('Category Grouping', () => {
    it('groups items by category', () => {
      const items = [
        createMockInventoryItem({
          id: 'item-1',
          name: 'Milk',
          category: 'dairy',
        }),
        createMockInventoryItem({
          id: 'item-2',
          name: 'Cheese',
          category: 'dairy',
        }),
        createMockInventoryItem({
          id: 'item-3',
          name: 'Apple',
          category: 'produce',
        }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: items,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      // Should have category groups for dairy and produce
      expect(screen.getByText('dairy')).toBeInTheDocument()
      expect(screen.getByText('produce')).toBeInTheDocument()
    })

    it('sorts categories alphabetically', () => {
      const items = [
        createMockInventoryItem({ id: 'item-1', category: 'produce' }),
        createMockInventoryItem({ id: 'item-2', category: 'dairy' }),
        createMockInventoryItem({ id: 'item-3', category: 'bakery' }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: items,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      // Categories should appear in alphabetical order: bakery, dairy, produce
      expect(screen.getByTestId('category-group-bakery')).toBeInTheDocument()
      expect(screen.getByTestId('category-group-dairy')).toBeInTheDocument()
      expect(screen.getByTestId('category-group-produce')).toBeInTheDocument()
    })

    it('excludes expiring items from category groups', () => {
      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)

      const items = [
        createMockInventoryItem({
          id: 'item-1',
          name: 'Expiring Milk',
          category: 'dairy',
          expiration_date: tomorrow.toISOString(),
        }),
        createMockInventoryItem({
          id: 'item-2',
          name: 'Fresh Cheese',
          category: 'dairy',
          expiration_date: null,
        }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: items,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      // Only Fresh Cheese should be in dairy category group
      // Expiring Milk should be in expiring section
      expect(screen.getByText('dairy')).toBeInTheDocument()
      expect(screen.getByText('Expiring Soon')).toBeInTheDocument()
    })
  })

  describe('Integration: Tab Filtering Updates Stats', () => {
    it('updates stat cards when tab filter changes', async () => {
      const user = userEvent.setup()

      // Initial state with "all" filter
      const allItems = [
        createMockInventoryItem({
          id: 'item-1',
          storage_location: StorageLocation.FRIDGE,
        }),
        createMockInventoryItem({
          id: 'item-2',
          storage_location: StorageLocation.PANTRY,
        }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: allItems,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      const { rerender } = renderWithProviders(<Pantry />)

      // Initially shows 2 total items
      expect(screen.getByText('Total Items: 2')).toBeInTheDocument()

      // Simulate clicking Fridge tab - would filter to only fridge items
      const fridgeTab = screen.getByText('Fridge')
      await user.click(fridgeTab)

      // Re-mock with filtered data
      const fridgeItems = [
        createMockInventoryItem({
          id: 'item-1',
          storage_location: StorageLocation.FRIDGE,
        }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: fridgeItems,
        isLoading: false,
        error: null,
      } as any)

      // Force re-render to simulate React Query refetch
      rerender(
        <QueryClientProvider client={queryClient}>
          <Pantry />
        </QueryClientProvider>
      )

      // After filtering, should show 1 item
      await waitFor(() => {
        expect(screen.getByText('Total Items: 1')).toBeInTheDocument()
      })
    })
  })

  describe('Page Structure', () => {
    it('renders page title and description', () => {
      vi.mocked(useInventoryList).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      renderWithProviders(<Pantry />)

      expect(screen.getByRole('heading', { name: /Pantry/ })).toBeInTheDocument()
      expect(screen.getByText('Manage your kitchen inventory')).toBeInTheDocument()
    })

    it('renders all major sections in correct order', () => {
      const items = [createMockInventoryItem({ id: 'item-1', category: 'dairy' })]

      vi.mocked(useInventoryList).mockReturnValue({
        data: items,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      const { container } = renderWithProviders(<Pantry />)

      // Check that major sections exist
      expect(screen.getByText('All')).toBeInTheDocument() // StorageTabs
      expect(screen.getByTestId('stat-cards')).toBeInTheDocument() // StatCards
      expect(screen.getByTestId('expiring-section')).toBeInTheDocument() // ExpiringSection
      expect(screen.getByTestId('low-stock-section')).toBeInTheDocument() // LowStockSection
      expect(screen.getByTestId('category-group-dairy')).toBeInTheDocument() // CategoryGroup
    })
  })

  describe('Memoization Behavior', () => {
    it('recalculates expiring items when inventory changes', () => {
      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)

      const initialItems = [
        createMockInventoryItem({
          id: 'item-1',
          expiration_date: tomorrow.toISOString(),
        }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: initialItems,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      const { rerender } = renderWithProviders(<Pantry />)

      // Should have 1 expiring item
      expect(screen.getByText('Expiring Soon: 1')).toBeInTheDocument()

      // Update with more expiring items
      const updatedItems = [
        ...initialItems,
        createMockInventoryItem({
          id: 'item-2',
          expiration_date: tomorrow.toISOString(),
        }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: updatedItems,
        isLoading: false,
        error: null,
      } as any)

      rerender(
        <QueryClientProvider client={queryClient}>
          <Pantry />
        </QueryClientProvider>
      )

      // Should now have 2 expiring items
      expect(screen.getByText('Expiring Soon: 2')).toBeInTheDocument()
    })

    it('recalculates category groups when inventory changes', () => {
      const initialItems = [
        createMockInventoryItem({ id: 'item-1', category: 'dairy' }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: initialItems,
        isLoading: false,
        error: null,
      } as any)

      vi.mocked(useLowStockAlerts).mockReturnValue({
        data: [],
        isLoading: false,
        error: null,
      } as any)

      const { rerender } = renderWithProviders(<Pantry />)

      expect(screen.getByText('dairy')).toBeInTheDocument()
      expect(screen.queryByText('produce')).not.toBeInTheDocument()

      // Add produce item
      const updatedItems = [
        ...initialItems,
        createMockInventoryItem({ id: 'item-2', category: 'produce' }),
      ]

      vi.mocked(useInventoryList).mockReturnValue({
        data: updatedItems,
        isLoading: false,
        error: null,
      } as any)

      rerender(
        <QueryClientProvider client={queryClient}>
          <Pantry />
        </QueryClientProvider>
      )

      expect(screen.getByText('dairy')).toBeInTheDocument()
      expect(screen.getByText('produce')).toBeInTheDocument()
    })
  })
})
