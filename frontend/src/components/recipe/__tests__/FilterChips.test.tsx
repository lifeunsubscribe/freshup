import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import FilterChips, { type RecipeFilters } from '../FilterChips'

describe('FilterChips', () => {
  const mockOnFilterChange = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('filter dropdowns', () => {
    it('renders all three filter dropdowns', () => {
      render(<FilterChips filters={{}} onFilterChange={mockOnFilterChange} />)

      expect(screen.getByDisplayValue('All sources')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Any time')).toBeInTheDocument()
      expect(screen.getByDisplayValue('All cuisines')).toBeInTheDocument()
    })

    it('renders source type dropdown with all options', () => {
      render(<FilterChips filters={{}} onFilterChange={mockOnFilterChange} />)
      const sourceSelect = screen.getByDisplayValue('All sources') as HTMLSelectElement

      const options = Array.from(sourceSelect.options).map((opt) => opt.text)
      expect(options).toContain('All sources')
      expect(options).toContain('My recipes')
      expect(options).toContain('HelloFresh')
      expect(options).toContain('Ad-hoc')
    })

    it('renders cook time dropdown with all options', () => {
      render(<FilterChips filters={{}} onFilterChange={mockOnFilterChange} />)
      const cookTimeSelect = screen.getByDisplayValue('Any time') as HTMLSelectElement

      const options = Array.from(cookTimeSelect.options).map((opt) => opt.text)
      expect(options).toContain('Any time')
      expect(options).toContain('15 min or less')
      expect(options).toContain('30 min or less')
      expect(options).toContain('45 min or less')
      expect(options).toContain('1 hour or less')
    })

    it('renders cuisine/tag dropdown with all options', () => {
      render(<FilterChips filters={{}} onFilterChange={mockOnFilterChange} />)
      const tagSelect = screen.getByDisplayValue('All cuisines') as HTMLSelectElement

      const options = Array.from(tagSelect.options).map((opt) => opt.text)
      expect(options).toContain('All cuisines')
      expect(options).toContain('Italian')
      expect(options).toContain('Mexican')
      expect(options).toContain('Asian')
      expect(options).toContain('Vegan')
      expect(options).toContain('Vegetarian')
    })
  })

  describe('filter selection', () => {
    it('calls onFilterChange when source type is selected', async () => {
      const user = userEvent.setup()
      render(<FilterChips filters={{}} onFilterChange={mockOnFilterChange} />)
      const sourceSelect = screen.getByDisplayValue('All sources')

      await user.selectOptions(sourceSelect, 'manual')

      expect(mockOnFilterChange).toHaveBeenCalledWith({
        source_type: 'manual',
      })
    })

    it('calls onFilterChange when cook time is selected', async () => {
      const user = userEvent.setup()
      render(<FilterChips filters={{}} onFilterChange={mockOnFilterChange} />)
      const cookTimeSelect = screen.getByDisplayValue('Any time')

      await user.selectOptions(cookTimeSelect, '30')

      expect(mockOnFilterChange).toHaveBeenCalledWith({
        max_cook_time: 30,
      })
    })

    it('calls onFilterChange when tag is selected', async () => {
      const user = userEvent.setup()
      render(<FilterChips filters={{}} onFilterChange={mockOnFilterChange} />)
      const tagSelect = screen.getByDisplayValue('All cuisines')

      await user.selectOptions(tagSelect, 'italian')

      expect(mockOnFilterChange).toHaveBeenCalledWith({
        tag: 'italian',
      })
    })

    it('preserves existing filters when adding new filter', async () => {
      const user = userEvent.setup()
      const existingFilters: RecipeFilters = {
        source_type: 'manual',
        max_cook_time: 30,
      }
      render(<FilterChips filters={existingFilters} onFilterChange={mockOnFilterChange} />)
      const tagSelect = screen.getByDisplayValue('All cuisines')

      await user.selectOptions(tagSelect, 'mexican')

      expect(mockOnFilterChange).toHaveBeenCalledWith({
        source_type: 'manual',
        max_cook_time: 30,
        tag: 'mexican',
      })
    })

    it('removes filter when selecting default option (empty value)', async () => {
      const user = userEvent.setup()
      const existingFilters: RecipeFilters = {
        source_type: 'manual',
      }
      render(<FilterChips filters={existingFilters} onFilterChange={mockOnFilterChange} />)
      const sourceSelect = screen.getByDisplayValue('My recipes')

      await user.selectOptions(sourceSelect, '')

      expect(mockOnFilterChange).toHaveBeenCalledWith({})
    })
  })

  describe('active filter chips', () => {
    it('does not render chips when no filters are active', () => {
      render(<FilterChips filters={{}} onFilterChange={mockOnFilterChange} />)
      expect(screen.queryByText(/Source:/)).not.toBeInTheDocument()
      expect(screen.queryByText(/Cuisine:/)).not.toBeInTheDocument()
      expect(screen.queryByText(/Max/)).not.toBeInTheDocument()
    })

    it('renders chip for source_type filter', () => {
      const filters: RecipeFilters = { source_type: 'manual' }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)
      expect(screen.getByText('Source: My recipes')).toBeInTheDocument()
    })

    it('renders chip for tag filter', () => {
      const filters: RecipeFilters = { tag: 'italian' }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)
      expect(screen.getByText('Cuisine: Italian')).toBeInTheDocument()
    })

    it('renders chip for max_cook_time filter', () => {
      const filters: RecipeFilters = { max_cook_time: 30 }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)
      expect(screen.getByText('Max 30 min or less')).toBeInTheDocument()
    })

    it('renders all chips when multiple filters are active', () => {
      const filters: RecipeFilters = {
        source_type: 'hellofresh_card',
        tag: 'mexican',
        max_cook_time: 45,
      }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      expect(screen.getByText('Source: HelloFresh')).toBeInTheDocument()
      expect(screen.getByText('Cuisine: Mexican')).toBeInTheDocument()
      expect(screen.getByText('Max 45 min or less')).toBeInTheDocument()
    })
  })

  describe('chip removal', () => {
    it('renders remove button for each active chip', () => {
      const filters: RecipeFilters = {
        source_type: 'manual',
        tag: 'italian',
      }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      expect(screen.getByLabelText('Remove Source: My recipes filter')).toBeInTheDocument()
      expect(screen.getByLabelText('Remove Cuisine: Italian filter')).toBeInTheDocument()
    })

    it('removes source_type filter when chip remove button is clicked', async () => {
      const user = userEvent.setup()
      const filters: RecipeFilters = {
        source_type: 'manual',
        tag: 'italian',
      }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      const removeButton = screen.getByLabelText('Remove Source: My recipes filter')
      await user.click(removeButton)

      expect(mockOnFilterChange).toHaveBeenCalledWith({
        tag: 'italian',
      })
    })

    it('removes tag filter when chip remove button is clicked', async () => {
      const user = userEvent.setup()
      const filters: RecipeFilters = {
        source_type: 'manual',
        tag: 'italian',
      }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      const removeButton = screen.getByLabelText('Remove Cuisine: Italian filter')
      await user.click(removeButton)

      expect(mockOnFilterChange).toHaveBeenCalledWith({
        source_type: 'manual',
      })
    })

    it('removes max_cook_time filter when chip remove button is clicked', async () => {
      const user = userEvent.setup()
      const filters: RecipeFilters = {
        max_cook_time: 30,
        tag: 'vegan',
      }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      const removeButton = screen.getByLabelText('Remove Max 30 min or less filter')
      await user.click(removeButton)

      expect(mockOnFilterChange).toHaveBeenCalledWith({
        tag: 'vegan',
      })
    })

    it('removes all filters when last chip is removed', async () => {
      const user = userEvent.setup()
      const filters: RecipeFilters = { tag: 'asian' }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      const removeButton = screen.getByLabelText('Remove Cuisine: Asian filter')
      await user.click(removeButton)

      expect(mockOnFilterChange).toHaveBeenCalledWith({})
    })
  })

  describe('filter dropdown and chip synchronization', () => {
    it('shows selected value in dropdown when filter is active', () => {
      const filters: RecipeFilters = { source_type: 'manual' }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      const sourceSelect = screen.getByDisplayValue('My recipes') as HTMLSelectElement
      expect(sourceSelect.value).toBe('manual')
    })

    it('updates chip when filter is changed via dropdown', async () => {
      const user = userEvent.setup()
      const filters: RecipeFilters = { source_type: 'manual' }
      const { rerender } = render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      const sourceSelect = screen.getByDisplayValue('My recipes')
      await user.selectOptions(sourceSelect, 'hellofresh_card')

      // Simulate parent updating filters prop
      rerender(
        <FilterChips
          filters={{ source_type: 'hellofresh_card' }}
          onFilterChange={mockOnFilterChange}
        />
      )

      expect(screen.getByText('Source: HelloFresh')).toBeInTheDocument()
      expect(screen.queryByText('Source: My recipes')).not.toBeInTheDocument()
    })
  })

  describe('styling', () => {
    it('applies correct chip styling (olive theme)', () => {
      const filters: RecipeFilters = { tag: 'italian' }
      const { container } = render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      const chip = container.querySelector('.bg-olive\\/10')
      expect(chip).toBeInTheDocument()
      expect(chip).toHaveClass('text-olive')
      expect(chip).toHaveClass('border-olive/20')
    })

    it('applies rounded-full styling to filter dropdowns', () => {
      render(<FilterChips filters={{}} onFilterChange={mockOnFilterChange} />)
      const sourceSelect = screen.getByDisplayValue('All sources')
      expect(sourceSelect).toHaveClass('rounded-full')
    })

    it('applies focus ring to dropdowns', () => {
      render(<FilterChips filters={{}} onFilterChange={mockOnFilterChange} />)
      const sourceSelect = screen.getByDisplayValue('All sources')
      expect(sourceSelect).toHaveClass('focus:ring-2')
      expect(sourceSelect).toHaveClass('focus:ring-olive')
    })
  })

  describe('accessibility', () => {
    it('chip remove buttons have descriptive aria-labels', () => {
      const filters: RecipeFilters = {
        source_type: 'manual',
        tag: 'italian',
        max_cook_time: 30,
      }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      expect(screen.getByLabelText('Remove Source: My recipes filter')).toBeInTheDocument()
      expect(screen.getByLabelText('Remove Cuisine: Italian filter')).toBeInTheDocument()
      expect(screen.getByLabelText('Remove Max 30 min or less filter')).toBeInTheDocument()
    })

    it('dropdowns are keyboard accessible', async () => {
      const user = userEvent.setup()
      render(<FilterChips filters={{}} onFilterChange={mockOnFilterChange} />)

      await user.tab()
      const sourceSelect = screen.getByDisplayValue('All sources')
      expect(sourceSelect).toHaveFocus()
    })
  })

  describe('edge cases', () => {
    it('handles unknown source_type gracefully', () => {
      const filters: RecipeFilters = { source_type: 'unknown_source' }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      // Should display the raw value if not found in options
      expect(screen.getByText('Source: unknown_source')).toBeInTheDocument()
    })

    it('handles unknown tag gracefully', () => {
      const filters: RecipeFilters = { tag: 'unknown_cuisine' }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      // Should display the raw value if not found in options
      expect(screen.getByText('Cuisine: unknown_cuisine')).toBeInTheDocument()
    })

    it('handles non-standard cook time values', () => {
      const filters: RecipeFilters = { max_cook_time: 90 }
      render(<FilterChips filters={filters} onFilterChange={mockOnFilterChange} />)

      // Should display the numeric value with "min" suffix
      expect(screen.getByText('Max 90 min')).toBeInTheDocument()
    })
  })
})
