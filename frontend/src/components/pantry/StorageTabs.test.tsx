import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import StorageTabs from './StorageTabs'
import { StorageLocation } from '../../api/types'

describe('StorageTabs', () => {
  it('renders all storage tab options', () => {
    const mockOnTabChange = vi.fn()
    render(<StorageTabs activeTab="all" onTabChange={mockOnTabChange} />)

    expect(screen.getByText('All')).toBeInTheDocument()
    expect(screen.getByText('Fridge')).toBeInTheDocument()
    expect(screen.getByText('Freezer')).toBeInTheDocument()
    expect(screen.getByText('Pantry')).toBeInTheDocument()
  })

  it('highlights active tab with olive background', () => {
    const mockOnTabChange = vi.fn()
    render(<StorageTabs activeTab="all" onTabChange={mockOnTabChange} />)

    const allTab = screen.getByText('All')
    expect(allTab.className).toContain('bg-olive')
    expect(allTab.className).toContain('text-cream')
  })

  it('shows inactive tabs with cream background', () => {
    const mockOnTabChange = vi.fn()
    render(<StorageTabs activeTab="all" onTabChange={mockOnTabChange} />)

    const fridgeTab = screen.getByText('Fridge')
    expect(fridgeTab.className).toContain('bg-cream')
    expect(fridgeTab.className).toContain('text-text-primary')
  })

  it('calls onTabChange when tab is clicked', () => {
    const mockOnTabChange = vi.fn()
    render(<StorageTabs activeTab="all" onTabChange={mockOnTabChange} />)

    const fridgeTab = screen.getByText('Fridge')
    fireEvent.click(fridgeTab)

    expect(mockOnTabChange).toHaveBeenCalledWith(StorageLocation.FRIDGE)
  })

  it('highlights fridge tab when active', () => {
    const mockOnTabChange = vi.fn()
    render(
      <StorageTabs activeTab={StorageLocation.FRIDGE} onTabChange={mockOnTabChange} />
    )

    const fridgeTab = screen.getByText('Fridge')
    expect(fridgeTab.className).toContain('bg-olive')
    expect(fridgeTab.className).toContain('text-cream')

    const allTab = screen.getByText('All')
    expect(allTab.className).toContain('bg-cream')
    expect(allTab.className).not.toContain('bg-olive')
  })

  it('renders as button elements', () => {
    const mockOnTabChange = vi.fn()
    render(<StorageTabs activeTab="all" onTabChange={mockOnTabChange} />)

    const allTab = screen.getByText('All')
    expect(allTab.tagName).toBe('BUTTON')
    expect(allTab).toHaveAttribute('type', 'button')
  })

  it('applies correct styling classes', () => {
    const mockOnTabChange = vi.fn()
    render(<StorageTabs activeTab="all" onTabChange={mockOnTabChange} />)

    const allTab = screen.getByText('All')
    expect(allTab.className).toContain('px-4')
    expect(allTab.className).toContain('py-2')
    expect(allTab.className).toContain('text-sm')
    expect(allTab.className).toContain('font-medium')
    expect(allTab.className).toContain('rounded-[8px]')
  })
})
