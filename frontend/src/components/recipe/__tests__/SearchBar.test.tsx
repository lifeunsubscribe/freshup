import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SearchBar from '../SearchBar'

describe('SearchBar', () => {
  const mockOnChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  describe('basic rendering', () => {
    it('renders search input with default placeholder', () => {
      render(<SearchBar value="" onChange={mockOnChange} />)
      expect(screen.getByPlaceholderText('Search recipes...')).toBeInTheDocument()
    })

    it('renders search input with custom placeholder', () => {
      render(<SearchBar value="" onChange={mockOnChange} placeholder="Find a recipe" />)
      expect(screen.getByPlaceholderText('Find a recipe')).toBeInTheDocument()
    })

    it('renders with initial value', () => {
      render(<SearchBar value="pasta" onChange={mockOnChange} />)
      const input = screen.getByPlaceholderText('Search recipes...') as HTMLInputElement
      expect(input.value).toBe('pasta')
    })

    it('renders search icon', () => {
      const { container } = render(<SearchBar value="" onChange={mockOnChange} />)
      const searchIcon = container.querySelector('svg')
      expect(searchIcon).toBeInTheDocument()
    })
  })

  describe('input interaction', () => {
    it('updates local value when typing', async () => {
      const user = userEvent.setup({ delay: null })
      render(<SearchBar value="" onChange={mockOnChange} />)
      const input = screen.getByPlaceholderText('Search recipes...')

      await user.type(input, 'curry')

      expect(input).toHaveValue('curry')
    })

    it('syncs local value with prop value when changed externally', () => {
      const { rerender } = render(<SearchBar value="pasta" onChange={mockOnChange} />)
      const input = screen.getByPlaceholderText('Search recipes...') as HTMLInputElement
      expect(input.value).toBe('pasta')

      // Parent clears the value
      rerender(<SearchBar value="" onChange={mockOnChange} />)
      expect(input.value).toBe('')
    })
  })

  describe('debounced onChange', () => {
    it('calls onChange after debounce delay (default 300ms)', async () => {
      const user = userEvent.setup({ delay: null })
      render(<SearchBar value="" onChange={mockOnChange} />)
      const input = screen.getByPlaceholderText('Search recipes...')

      await user.type(input, 'taco')

      // Should not call immediately
      expect(mockOnChange).not.toHaveBeenCalled()

      // Fast-forward 300ms
      vi.advanceTimersByTime(300)

      expect(mockOnChange).toHaveBeenCalledTimes(1)
      expect(mockOnChange).toHaveBeenCalledWith('taco')
    })

    it('respects custom debounce delay', async () => {
      const user = userEvent.setup({ delay: null })
      render(<SearchBar value="" onChange={mockOnChange} debounceMs={500} />)
      const input = screen.getByPlaceholderText('Search recipes...')

      await user.type(input, 'burger')

      // Should not call after 300ms (default delay)
      vi.advanceTimersByTime(300)
      expect(mockOnChange).not.toHaveBeenCalled()

      // Should call after 500ms (custom delay)
      vi.advanceTimersByTime(200)
      expect(mockOnChange).toHaveBeenCalledTimes(1)
      expect(mockOnChange).toHaveBeenCalledWith('burger')
    })

    it('debounces multiple rapid keystrokes', async () => {
      const user = userEvent.setup({ delay: null })
      render(<SearchBar value="" onChange={mockOnChange} />)
      const input = screen.getByPlaceholderText('Search recipes...')

      await user.type(input, 'chicken')

      // Fast-forward 299ms (just before debounce)
      vi.advanceTimersByTime(299)
      expect(mockOnChange).not.toHaveBeenCalled()

      // Type one more character - should reset timer
      await user.type(input, ' ')

      // Fast-forward 299ms again
      vi.advanceTimersByTime(299)
      expect(mockOnChange).not.toHaveBeenCalled()

      // Fast-forward final 1ms to complete debounce
      vi.advanceTimersByTime(1)
      expect(mockOnChange).toHaveBeenCalledTimes(1)
      expect(mockOnChange).toHaveBeenCalledWith('chicken ')
    })

    it('does not call onChange if value did not change', async () => {
      render(<SearchBar value="pizza" onChange={mockOnChange} />)

      // Fast-forward past debounce delay
      vi.advanceTimersByTime(300)

      // Should not call onChange since value matches prop
      expect(mockOnChange).not.toHaveBeenCalled()
    })
  })

  describe('clear button', () => {
    it('does not show clear button when input is empty', () => {
      render(<SearchBar value="" onChange={mockOnChange} />)
      expect(screen.queryByLabelText('Clear search')).not.toBeInTheDocument()
    })

    it('shows clear button when input has value', async () => {
      const user = userEvent.setup({ delay: null })
      render(<SearchBar value="" onChange={mockOnChange} />)
      const input = screen.getByPlaceholderText('Search recipes...')

      await user.type(input, 'salad')

      expect(screen.getByLabelText('Clear search')).toBeInTheDocument()
    })

    it('clears input when clear button is clicked', async () => {
      const user = userEvent.setup()
      render(<SearchBar value="pasta" onChange={mockOnChange} />)
      const input = screen.getByPlaceholderText('Search recipes...') as HTMLInputElement
      const clearButton = screen.getByLabelText('Clear search')

      await user.click(clearButton)

      expect(input.value).toBe('')
      expect(mockOnChange).toHaveBeenCalledWith('')
    })

    it('calls onChange immediately when clear button is clicked (no debounce)', async () => {
      const user = userEvent.setup()
      render(<SearchBar value="soup" onChange={mockOnChange} />)
      const clearButton = screen.getByLabelText('Clear search')

      await user.click(clearButton)

      // Should call immediately without waiting for debounce
      expect(mockOnChange).toHaveBeenCalledTimes(1)
      expect(mockOnChange).toHaveBeenCalledWith('')
    })

    it('hides clear button after clearing', async () => {
      const user = userEvent.setup()
      render(<SearchBar value="noodles" onChange={mockOnChange} />)
      const clearButton = screen.getByLabelText('Clear search')

      await user.click(clearButton)

      await waitFor(() => {
        expect(screen.queryByLabelText('Clear search')).not.toBeInTheDocument()
      })
    })
  })

  describe('accessibility', () => {
    it('input is keyboard accessible', async () => {
      const user = userEvent.setup({ delay: null })
      render(<SearchBar value="" onChange={mockOnChange} />)
      const input = screen.getByPlaceholderText('Search recipes...')

      await user.tab()
      expect(input).toHaveFocus()
    })

    it('clear button has proper aria-label', () => {
      render(<SearchBar value="test" onChange={mockOnChange} />)
      const clearButton = screen.getByLabelText('Clear search')
      expect(clearButton).toHaveAttribute('aria-label', 'Clear search')
    })
  })

  describe('styling', () => {
    it('applies focus styles when input is focused', async () => {
      const user = userEvent.setup()
      render(<SearchBar value="" onChange={mockOnChange} />)
      const input = screen.getByPlaceholderText('Search recipes...')

      await user.click(input)

      expect(input).toHaveClass('focus:ring-2')
      expect(input).toHaveClass('focus:ring-olive')
    })

    it('applies correct padding for icons (left and right)', () => {
      render(<SearchBar value="test" onChange={mockOnChange} />)
      const input = screen.getByPlaceholderText('Search recipes...')

      expect(input).toHaveClass('pl-10') // Left padding for search icon
      expect(input).toHaveClass('pr-10') // Right padding for clear button
    })
  })
})
