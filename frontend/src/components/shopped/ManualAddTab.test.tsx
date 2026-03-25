import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { userEvent } from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import ManualAddTab from './ManualAddTab'
import { Category, StorageLocation } from '../../api/types'

// Mock the API hooks
vi.mock('../../api', () => ({
  useCreateInventoryItem: vi.fn(),
}))

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

import { useCreateInventoryItem } from '../../api'

describe('ManualAddTab', () => {
  let queryClient: QueryClient
  let mutateAsync: ReturnType<typeof vi.fn>

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    mutateAsync = vi.fn().mockResolvedValue({})
    mockNavigate.mockClear()

    vi.mocked(useCreateInventoryItem).mockReturnValue({
      mutateAsync,
      isPending: false,
      isError: false,
    } as any)
  })

  const renderWithProviders = (ui: React.ReactElement) => {
    return render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>{ui}</BrowserRouter>
      </QueryClientProvider>
    )
  }

  describe('Form Rendering', () => {
    it('renders all form fields with correct defaults', () => {
      renderWithProviders(<ManualAddTab />)

      expect(screen.getByLabelText(/Item name/)).toHaveValue('')
      expect(screen.getByLabelText(/Quantity/)).toHaveValue(1)
      expect(screen.getByLabelText(/Unit/)).toHaveValue('unit')
      expect(screen.getByLabelText(/Category/)).toHaveValue(Category.OTHER)
      expect(screen.getByLabelText(/Storage location/)).toHaveValue(
        StorageLocation.PANTRY
      )
      expect(screen.getByLabelText(/Store/)).toHaveValue('')
      expect(screen.getByLabelText(/Expiration date/)).toHaveValue('')
    })

    it('renders action buttons', () => {
      renderWithProviders(<ManualAddTab />)

      expect(screen.getByRole('button', { name: /Add another/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Done/ })).toBeInTheDocument()
    })
  })

  describe('Form Validation', () => {
    it('shows validation error when name is empty', async () => {
      const user = userEvent.setup()
      renderWithProviders(<ManualAddTab />)

      const addButton = screen.getByRole('button', { name: /Add another/ })
      await user.click(addButton)

      expect(screen.getByRole('alert')).toHaveTextContent('Item name is required')
      expect(mutateAsync).not.toHaveBeenCalled()
    })

    it('shows validation error when quantity is 0', async () => {
      const user = userEvent.setup()
      renderWithProviders(<ManualAddTab />)

      const nameInput = screen.getByLabelText(/Item name/)
      const quantityInput = screen.getByLabelText(/Quantity/)
      const addButton = screen.getByRole('button', { name: /Add another/ })

      await user.type(nameInput, 'Olive oil')
      await user.clear(quantityInput)
      await user.type(quantityInput, '0')
      await user.click(addButton)

      expect(screen.getByRole('alert')).toHaveTextContent(
        'Quantity must be greater than 0'
      )
      expect(mutateAsync).not.toHaveBeenCalled()
    })

    it('shows validation error when quantity is negative', async () => {
      const user = userEvent.setup()
      renderWithProviders(<ManualAddTab />)

      const nameInput = screen.getByLabelText(/Item name/)
      const quantityInput = screen.getByLabelText(/Quantity/)
      const addButton = screen.getByRole('button', { name: /Add another/ })

      await user.type(nameInput, 'Olive oil')
      await user.clear(quantityInput)
      await user.type(quantityInput, '-1')
      await user.click(addButton)

      expect(screen.getByRole('alert')).toHaveTextContent(
        'Quantity must be greater than 0'
      )
      expect(mutateAsync).not.toHaveBeenCalled()
    })

    it('shows validation error when unit is empty', async () => {
      const user = userEvent.setup()
      renderWithProviders(<ManualAddTab />)

      const nameInput = screen.getByLabelText(/Item name/)
      const unitInput = screen.getByLabelText(/Unit/)
      const addButton = screen.getByRole('button', { name: /Add another/ })

      await user.type(nameInput, 'Olive oil')
      await user.clear(unitInput)
      await user.click(addButton)

      expect(screen.getByRole('alert')).toHaveTextContent('Unit is required')
      expect(mutateAsync).not.toHaveBeenCalled()
    })
  })

  describe('Add Another Functionality', () => {
    it('creates inventory item and clears form when "Add another" is clicked', async () => {
      const user = userEvent.setup()
      renderWithProviders(<ManualAddTab />)

      const nameInput = screen.getByLabelText(/Item name/)
      const quantityInput = screen.getByLabelText(/Quantity/)
      const addButton = screen.getByRole('button', { name: /Add another/ })

      await user.type(nameInput, 'Olive oil')
      await user.clear(quantityInput)
      await user.type(quantityInput, '2')
      await user.click(addButton)

      // API should be called with correct data
      await waitFor(() => {
        expect(mutateAsync).toHaveBeenCalledWith({
          name: 'Olive oil',
          quantity: 2,
          unit: 'unit',
          category: Category.OTHER,
          storage_location: StorageLocation.PANTRY,
          preferred_store: undefined,
          expiration_date: undefined,
        })
      })

      // Form should be cleared
      await waitFor(() => {
        expect(screen.getByLabelText(/Item name/)).toHaveValue('')
        expect(screen.getByLabelText(/Quantity/)).toHaveValue(1)
        expect(screen.getByLabelText(/Unit/)).toHaveValue('unit')
      })

      // Should not navigate
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('shows success message after adding item', async () => {
      const user = userEvent.setup()
      renderWithProviders(<ManualAddTab />)

      const nameInput = screen.getByLabelText(/Item name/)
      const addButton = screen.getByRole('button', { name: /Add another/ })

      await user.type(nameInput, 'Tomatoes')
      await user.click(addButton)

      await waitFor(() => {
        expect(screen.getByText(/Tomatoes added to pantry!/)).toBeInTheDocument()
      })
    })

    it('handles all optional fields', async () => {
      const user = userEvent.setup()
      renderWithProviders(<ManualAddTab />)

      const nameInput = screen.getByLabelText(/Item name/)
      const storeInput = screen.getByLabelText(/Store/)
      const expirationInput = screen.getByLabelText(/Expiration date/)
      const categorySelect = screen.getByLabelText(/Category/)
      const storageSelect = screen.getByLabelText(/Storage location/)
      const addButton = screen.getByRole('button', { name: /Add another/ })

      await user.type(nameInput, 'Milk')
      await user.selectOptions(categorySelect, Category.DAIRY)
      await user.selectOptions(storageSelect, StorageLocation.FRIDGE)
      await user.type(storeInput, 'Whole Foods')
      await user.type(expirationInput, '2026-04-01')
      await user.click(addButton)

      await waitFor(() => {
        expect(mutateAsync).toHaveBeenCalledWith({
          name: 'Milk',
          quantity: 1,
          unit: 'unit',
          category: Category.DAIRY,
          storage_location: StorageLocation.FRIDGE,
          preferred_store: 'Whole Foods',
          expiration_date: '2026-04-01',
        })
      })
    })
  })

  describe('Done Functionality', () => {
    it('creates inventory item and navigates to pantry when "Done" is clicked with data', async () => {
      const user = userEvent.setup()
      renderWithProviders(<ManualAddTab />)

      const nameInput = screen.getByLabelText(/Item name/)
      const doneButton = screen.getByRole('button', { name: /Done/ })

      await user.type(nameInput, 'Flour')
      await user.click(doneButton)

      // API should be called
      await waitFor(() => {
        expect(mutateAsync).toHaveBeenCalledWith(
          expect.objectContaining({
            name: 'Flour',
          })
        )
      })

      // Should navigate to pantry
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/pantry')
      })
    })

    it('navigates to pantry immediately when "Done" is clicked with empty form', async () => {
      const user = userEvent.setup()
      renderWithProviders(<ManualAddTab />)

      const doneButton = screen.getByRole('button', { name: /Done/ })
      await user.click(doneButton)

      // API should not be called
      expect(mutateAsync).not.toHaveBeenCalled()

      // Should navigate immediately
      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/pantry')
      })
    })

    it('does not navigate if submission fails', async () => {
      const user = userEvent.setup()

      // Mock API to reject
      mutateAsync.mockRejectedValueOnce(new Error('API Error'))

      vi.mocked(useCreateInventoryItem).mockReturnValue({
        mutateAsync,
        isPending: false,
        isError: true,
      } as any)

      renderWithProviders(<ManualAddTab />)

      const nameInput = screen.getByLabelText(/Item name/)
      const doneButton = screen.getByRole('button', { name: /Done/ })

      await user.type(nameInput, 'Rice')
      await user.click(doneButton)

      // Should not navigate
      await waitFor(() => {
        expect(mockNavigate).not.toHaveBeenCalled()
      })
    })
  })

  describe('Error Handling', () => {
    it('displays API error message when mutation fails', async () => {
      const user = userEvent.setup()

      // Mock API to reject
      mutateAsync.mockRejectedValueOnce(new Error('API Error'))

      vi.mocked(useCreateInventoryItem).mockReturnValue({
        mutateAsync,
        isPending: false,
        isError: true,
      } as any)

      renderWithProviders(<ManualAddTab />)

      const nameInput = screen.getByLabelText(/Item name/)
      const addButton = screen.getByRole('button', { name: /Add another/ })

      await user.type(nameInput, 'Sugar')
      await user.click(addButton)

      expect(screen.getByText(/Failed to add item. Please try again./)).toBeInTheDocument()
    })
  })

  describe('Pending State', () => {
    it('disables buttons when mutation is pending', () => {
      vi.mocked(useCreateInventoryItem).mockReturnValue({
        mutateAsync,
        isPending: true,
        isError: false,
      } as any)

      renderWithProviders(<ManualAddTab />)

      const addButton = screen.getByRole('button', { name: /Adding.../ })
      const doneButton = screen.getByRole('button', { name: /Done/ })

      expect(addButton).toBeDisabled()
      expect(doneButton).toBeDisabled()
    })
  })

  describe('Form Field Options', () => {
    it('renders all category options', () => {
      renderWithProviders(<ManualAddTab />)

      const categorySelect = screen.getByLabelText(/Category/)
      const options = Array.from(categorySelect.querySelectorAll('option'))

      expect(options).toHaveLength(12) // All Category enum values
      expect(options.map((o) => o.value)).toContain(Category.PRODUCE)
      expect(options.map((o) => o.value)).toContain(Category.DAIRY)
      expect(options.map((o) => o.value)).toContain(Category.PROTEIN)
    })

    it('renders all storage location options', () => {
      renderWithProviders(<ManualAddTab />)

      const storageSelect = screen.getByLabelText(/Storage location/)
      const options = Array.from(storageSelect.querySelectorAll('option'))

      expect(options).toHaveLength(4) // All StorageLocation enum values
      expect(options.map((o) => o.value)).toContain(StorageLocation.PANTRY)
      expect(options.map((o) => o.value)).toContain(StorageLocation.FRIDGE)
      expect(options.map((o) => o.value)).toContain(StorageLocation.FREEZER)
      expect(options.map((o) => o.value)).toContain(StorageLocation.COUNTER)
    })
  })

  describe('Accessibility', () => {
    it('has proper labels for all form fields', () => {
      renderWithProviders(<ManualAddTab />)

      expect(screen.getByLabelText(/Item name/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Quantity/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Unit/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Category/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Storage location/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Store/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Expiration date/)).toBeInTheDocument()
    })

    it('marks required fields with asterisk', () => {
      renderWithProviders(<ManualAddTab />)

      expect(screen.getByLabelText(/Item name \*/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Quantity \*/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Unit \*/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Category \*/)).toBeInTheDocument()
      expect(screen.getByLabelText(/Storage location \*/)).toBeInTheDocument()
    })
  })
})
