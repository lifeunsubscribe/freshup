import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import InventoryRow from './InventoryRow'
import type { InventoryItemResponse } from '../../api/types'
import { StorageLocation } from '../../api/types'

// Mock the API hooks
vi.mock('../../api', () => ({
  useConsumeInventoryItem: vi.fn(),
  useFreezeInventoryItem: vi.fn(),
  useUpdateInventoryItem: vi.fn(),
}))

import {
  useConsumeInventoryItem,
  useFreezeInventoryItem,
  useUpdateInventoryItem,
} from '../../api'

describe('InventoryRow', () => {
  let queryClient: QueryClient
  let consumeMutate: ReturnType<typeof vi.fn>
  let freezeMutate: ReturnType<typeof vi.fn>
  let updateMutate: ReturnType<typeof vi.fn>

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    consumeMutate = vi.fn()
    freezeMutate = vi.fn()
    updateMutate = vi.fn()

    vi.mocked(useConsumeInventoryItem).mockReturnValue({
      mutate: consumeMutate,
      isPending: false,
      isError: false,
    } as any)

    vi.mocked(useFreezeInventoryItem).mockReturnValue({
      mutate: freezeMutate,
      isPending: false,
      isError: false,
    } as any)

    vi.mocked(useUpdateInventoryItem).mockReturnValue({
      mutate: updateMutate,
      isPending: false,
      isError: false,
    } as any)
  })

  const renderWithProviders = (ui: React.ReactElement) => {
    return render(
      <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
    )
  }

  const createMockItem = (
    overrides?: Partial<InventoryItemResponse>
  ): InventoryItemResponse => ({
    id: 'item-1',
    name: 'Milk',
    quantity: 2,
    unit: 'gallon',
    category: 'dairy',
    storage_location: StorageLocation.FRIDGE,
    added_by: 'user-1',
    date_added: '2026-03-20T10:00:00Z',
    expiration_date: null,
    frozen_date: null,
    is_staple: false,
    minimum_threshold: null,
    shareability: 'shared',
    reserved_note: null,
    reserved_for: null,
    price: null,
    brand: null,
    preferred_store: null,
    preferred_store_rel: null,
    available_at_stores: [],
    vegan_friendly: false,
    ...overrides,
  })

  describe('Visual States', () => {
    it('renders item name in 14px primary text', () => {
      const item = createMockItem({ name: 'Olive oil' })
      const { container } = renderWithProviders(<InventoryRow item={item} />)

      const itemName = screen.getByText('Olive oil')
      expect(itemName).toBeInTheDocument()
      expect(itemName.className).toContain('text-[14px]')
      expect(itemName.className).toContain('text-text-primary')
    })

    it('renders quantity right-aligned in secondary text', () => {
      const item = createMockItem({ quantity: 2.5, unit: 'lb' })
      renderWithProviders(<InventoryRow item={item} />)

      const quantity = screen.getByText('2.5 lb')
      expect(quantity).toBeInTheDocument()
      expect(quantity.className).toContain('text-text-secondary')
    })

    it('renders storage badge', () => {
      const item = createMockItem({ storage_location: StorageLocation.FRIDGE })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.getByText('Fridge')).toBeInTheDocument()
    })
  })

  describe('Expiry Badge', () => {
    it('shows "today" badge for items expiring today', () => {
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: today.toISOString(),
      })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.getByText('today')).toBeInTheDocument()
    })

    it('shows "tomorrow" badge for items expiring tomorrow', () => {
      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)
      tomorrow.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: tomorrow.toISOString(),
      })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.getByText('tomorrow')).toBeInTheDocument()
    })

    it('shows "3d" badge for items expiring in 3 days', () => {
      const threeDays = new Date()
      threeDays.setDate(threeDays.getDate() + 3)
      threeDays.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: threeDays.toISOString(),
      })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.getByText('3d')).toBeInTheDocument()
    })

    it('does not show badge for items expiring in more than 7 days', () => {
      const tenDays = new Date()
      tenDays.setDate(tenDays.getDate() + 10)
      tenDays.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: tenDays.toISOString(),
      })
      renderWithProviders(<InventoryRow item={item} />)

      // No expiry badge should be shown
      expect(screen.queryByText(/\dd/)).not.toBeInTheDocument()
      expect(screen.queryByText('today')).not.toBeInTheDocument()
      expect(screen.queryByText('tomorrow')).not.toBeInTheDocument()
    })

    it('shows "expired" for items past expiration', () => {
      const yesterday = new Date()
      yesterday.setDate(yesterday.getDate() - 1)
      yesterday.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: yesterday.toISOString(),
      })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.getByText('expired')).toBeInTheDocument()
    })

    it('does not show badge when no expiration date', () => {
      const item = createMockItem({ expiration_date: null })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.queryByText(/today|tomorrow|\dd|expired/)).not.toBeInTheDocument()
    })
  })

  describe('Low Stock Badge', () => {
    it('shows "low" badge when quantity is below minimum threshold', () => {
      const item = createMockItem({
        quantity: 1,
        minimum_threshold: 3,
      })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.getByText('low')).toBeInTheDocument()
    })

    it('does not show "low" badge when quantity is at or above threshold', () => {
      const item = createMockItem({
        quantity: 3,
        minimum_threshold: 3,
      })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.queryByText('low')).not.toBeInTheDocument()
    })

    it('does not show "low" badge when minimum_threshold is not set', () => {
      const item = createMockItem({
        quantity: 1,
        minimum_threshold: null,
      })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.queryByText('low')).not.toBeInTheDocument()
    })
  })

  describe('Quick Actions', () => {
    it('shows quick actions for items expiring within 3 days', () => {
      const tomorrow = new Date()
      tomorrow.setDate(tomorrow.getDate() + 1)
      tomorrow.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: tomorrow.toISOString(),
      })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.getByRole('button', { name: /Ate it/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Freeze/i })).toBeInTheDocument()
    })

    it('does not show quick actions for items expiring in more than 3 days', () => {
      const fiveDays = new Date()
      fiveDays.setDate(fiveDays.getDate() + 5)
      fiveDays.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: fiveDays.toISOString(),
      })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.queryByRole('button', { name: /Ate it/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Freeze/i })).not.toBeInTheDocument()
    })

    it('calls consume endpoint when "Ate it" is clicked', async () => {
      const user = userEvent.setup()
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: today.toISOString(),
        quantity: 2,
        unit: 'gallon',
      })
      renderWithProviders(<InventoryRow item={item} />)

      const ateItButton = screen.getByRole('button', { name: /Ate it/i })
      await user.click(ateItButton)

      expect(consumeMutate).toHaveBeenCalledWith({
        amount: 2,
        delete_when_empty: true,
      })
    })

    it('calls freeze endpoint when "Freeze" is clicked', async () => {
      const user = userEvent.setup()
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: today.toISOString(),
      })
      renderWithProviders(<InventoryRow item={item} />)

      const freezeButton = screen.getByRole('button', { name: /Freeze/i })
      await user.click(freezeButton)

      expect(freezeMutate).toHaveBeenCalled()
    })

    it('disables "Freeze" button when item is already in freezer', () => {
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: today.toISOString(),
        storage_location: StorageLocation.FREEZER,
      })
      renderWithProviders(<InventoryRow item={item} />)

      const freezeButton = screen.getByRole('button', { name: /Freeze/i })
      expect(freezeButton).toBeDisabled()
    })

    it('disables quick action buttons when mutations are pending', () => {
      vi.mocked(useConsumeInventoryItem).mockReturnValue({
        mutate: consumeMutate,
        isPending: true,
        isError: false,
      } as any)

      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: today.toISOString(),
      })
      renderWithProviders(<InventoryRow item={item} />)

      const ateItButton = screen.getByRole('button', { name: /Ate it/i })
      const freezeButton = screen.getByRole('button', { name: /Freeze/i })

      expect(ateItButton).toBeDisabled()
      expect(freezeButton).toBeDisabled()
    })
  })

  describe('StorageBadge Cycling', () => {
    it('calls update endpoint when storage badge is clicked', async () => {
      const user = userEvent.setup()
      const item = createMockItem({ storage_location: StorageLocation.PANTRY })
      renderWithProviders(<InventoryRow item={item} />)

      const storageBadge = screen.getByRole('button', {
        name: /Change storage from Pantry/i,
      })
      await user.click(storageBadge)

      expect(updateMutate).toHaveBeenCalledWith({
        storage_location: StorageLocation.FRIDGE,
      })
    })

    it('cycles through storage locations in correct order', async () => {
      const user = userEvent.setup()
      const item = createMockItem({ storage_location: StorageLocation.FRIDGE })
      renderWithProviders(<InventoryRow item={item} />)

      const storageBadge = screen.getByRole('button', {
        name: /Change storage from Fridge/i,
      })
      await user.click(storageBadge)

      // Fridge → Freezer
      expect(updateMutate).toHaveBeenCalledWith({
        storage_location: StorageLocation.FREEZER,
      })
    })

    it('disables storage badge when mutation is pending', () => {
      vi.mocked(useUpdateInventoryItem).mockReturnValue({
        mutate: updateMutate,
        isPending: true,
        isError: false,
      } as any)

      const item = createMockItem({ storage_location: StorageLocation.PANTRY })
      renderWithProviders(<InventoryRow item={item} />)

      const storageBadge = screen.getByRole('button', {
        name: /Change storage from Pantry/i,
      })
      expect(storageBadge).toBeDisabled()
    })
  })

  describe('Error Handling', () => {
    it('displays error banner when consume mutation fails', () => {
      vi.mocked(useConsumeInventoryItem).mockReturnValue({
        mutate: consumeMutate,
        isPending: false,
        isError: true,
      } as any)

      const item = createMockItem()
      renderWithProviders(<InventoryRow item={item} />)

      const errorBanner = screen.getByRole('alert')
      expect(errorBanner).toBeInTheDocument()
      expect(errorBanner).toHaveTextContent('Failed to consume item. Please try again.')
    })

    it('displays error banner when freeze mutation fails', () => {
      vi.mocked(useFreezeInventoryItem).mockReturnValue({
        mutate: freezeMutate,
        isPending: false,
        isError: true,
      } as any)

      const item = createMockItem()
      renderWithProviders(<InventoryRow item={item} />)

      const errorBanner = screen.getByRole('alert')
      expect(errorBanner).toBeInTheDocument()
      expect(errorBanner).toHaveTextContent('Failed to freeze item. Please try again.')
    })

    it('displays error banner when update mutation fails', () => {
      vi.mocked(useUpdateInventoryItem).mockReturnValue({
        mutate: updateMutate,
        isPending: false,
        isError: true,
      } as any)

      const item = createMockItem()
      renderWithProviders(<InventoryRow item={item} />)

      const errorBanner = screen.getByRole('alert')
      expect(errorBanner).toBeInTheDocument()
      expect(errorBanner).toHaveTextContent('Failed to update storage. Please try again.')
    })

    it('auto-dismisses error message after 5 seconds', async () => {
      vi.useFakeTimers()

      vi.mocked(useConsumeInventoryItem).mockReturnValue({
        mutate: consumeMutate,
        isPending: false,
        isError: true,
      } as any)

      const item = createMockItem()
      renderWithProviders(<InventoryRow item={item} />)

      // Error should be visible initially
      expect(screen.getByRole('alert')).toBeInTheDocument()

      // Fast-forward 5 seconds
      vi.advanceTimersByTime(5000)

      // Error should be dismissed
      await waitFor(() => {
        expect(screen.queryByRole('alert')).not.toBeInTheDocument()
      })

      vi.useRealTimers()
    })
  })

  describe('Accessibility', () => {
    it('has minimum 44px height for mobile usability', () => {
      const item = createMockItem()
      const { container } = renderWithProviders(<InventoryRow item={item} />)

      const itemContainer = container.querySelector('.min-h-\\[44px\\]')
      expect(itemContainer).toBeInTheDocument()
    })

    it('storage badge has accessible label', () => {
      const item = createMockItem({ storage_location: StorageLocation.FRIDGE })
      renderWithProviders(<InventoryRow item={item} />)

      const storageBadge = screen.getByRole('button', {
        name: /Change storage from Fridge/i,
      })
      expect(storageBadge).toBeInTheDocument()
    })
  })

  describe('Combined States', () => {
    it('shows both expiry and low stock badges together', () => {
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const item = createMockItem({
        expiration_date: today.toISOString(),
        quantity: 1,
        minimum_threshold: 3,
      })
      renderWithProviders(<InventoryRow item={item} />)

      expect(screen.getByText('today')).toBeInTheDocument()
      expect(screen.getByText('low')).toBeInTheDocument()
    })

    it('shows all elements for expiring low-stock item', () => {
      const today = new Date()
      today.setHours(0, 0, 0, 0)
      const item = createMockItem({
        name: 'Cheese',
        quantity: 0.5,
        unit: 'lb',
        minimum_threshold: 2,
        expiration_date: today.toISOString(),
        storage_location: StorageLocation.FRIDGE,
      })
      renderWithProviders(<InventoryRow item={item} />)

      // Item name
      expect(screen.getByText('Cheese')).toBeInTheDocument()
      // Quantity
      expect(screen.getByText('0.5 lb')).toBeInTheDocument()
      // Expiry badge
      expect(screen.getByText('today')).toBeInTheDocument()
      // Low stock badge
      expect(screen.getByText('low')).toBeInTheDocument()
      // Storage badge
      expect(screen.getByText('Fridge')).toBeInTheDocument()
      // Quick actions
      expect(screen.getByRole('button', { name: /Ate it/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Freeze/i })).toBeInTheDocument()
    })
  })
})
