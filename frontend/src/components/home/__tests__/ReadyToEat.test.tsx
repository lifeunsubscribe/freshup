import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import ReadyToEat from '../ReadyToEat'
import { usePreparedFoodList } from '../../../api'

// Mock the API hook
vi.mock('../../../api', () => ({
  usePreparedFoodList: vi.fn(),
}))

describe('ReadyToEat', () => {
  const mockItems = [
    {
      id: 'pf-1',
      name: 'Chicken Curry',
      type: 'main',
      servings_remaining: 3,
      date_prepared: '2026-03-23',
      shareability: 'shared',
    },
    {
      id: 'pf-2',
      name: 'Pasta Salad',
      type: 'side',
      servings_remaining: 1,
      date_prepared: '2026-03-22',
      shareability: 'reserved',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('basic rendering', () => {
    it('renders section header', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: mockItems,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<ReadyToEat />)

      expect(screen.getByText('Ready to Eat')).toBeInTheDocument()
    })

    it('renders prepared food items when data is available', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: mockItems,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<ReadyToEat />)

      expect(screen.getByText('Chicken Curry')).toBeInTheDocument()
      expect(screen.getByText('Pasta Salad')).toBeInTheDocument()
    })

    it('renders carousel with correct ARIA label', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: mockItems,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<ReadyToEat />)

      expect(screen.getByRole('list', { name: 'Prepared foods carousel' })).toBeInTheDocument()
    })
  })

  describe('loading state', () => {
    it('displays loading message when isLoading is true', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      } as any)

      render(<ReadyToEat />)

      expect(screen.getByText('Loading prepared foods...')).toBeInTheDocument()
    })
  })

  describe('error state', () => {
    it('displays error message when isError is true', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: new Error('Network error'),
      } as any)

      render(<ReadyToEat />)

      expect(screen.getByText(/failed to load prepared foods/i)).toBeInTheDocument()
      expect(screen.getByText(/network error/i)).toBeInTheDocument()
    })

    it('displays generic error message when error is not an Error instance', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: undefined,
        isLoading: false,
        isError: true,
        error: 'Something went wrong',
      } as any)

      render(<ReadyToEat />)

      expect(screen.getByText(/failed to load prepared foods/i)).toBeInTheDocument()
      expect(screen.getByText(/please try again/i)).toBeInTheDocument()
    })
  })

  describe('empty state', () => {
    it('displays empty message when no items are returned', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<ReadyToEat />)

      expect(screen.getByText('No prepared foods ready. Cook something delicious!')).toBeInTheDocument()
    })
  })

  describe('accessibility attributes', () => {
    it('applies role="region" to section element', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: mockItems,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<ReadyToEat />)

      const section = screen.getByRole('region', { name: 'Ready to Eat' })
      expect(section).toBeInTheDocument()
    })

    it('applies aria-roledescription="carousel" to section element', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: mockItems,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const { container } = render(<ReadyToEat />)

      const section = container.querySelector('section')
      expect(section).toHaveAttribute('aria-roledescription', 'carousel')
    })

    it('applies aria-label="Ready to Eat" to section element', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: mockItems,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      const { container } = render(<ReadyToEat />)

      const section = container.querySelector('section')
      expect(section).toHaveAttribute('aria-label', 'Ready to Eat')
    })
  })

  describe('prepared food cards', () => {
    it('displays servings information correctly', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: mockItems,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<ReadyToEat />)

      expect(screen.getByText('3 servings left')).toBeInTheDocument()
      expect(screen.getByText('1 serving left')).toBeInTheDocument()
    })

    it('displays food types as pills', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: mockItems,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<ReadyToEat />)

      expect(screen.getByText('main')).toBeInTheDocument()
      expect(screen.getByText('side')).toBeInTheDocument()
    })

    it('displays shareability status as pills', () => {
      vi.mocked(usePreparedFoodList).mockReturnValue({
        data: mockItems,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      render(<ReadyToEat />)

      expect(screen.getByText('shared')).toBeInTheDocument()
      expect(screen.getByText('reserved')).toBeInTheDocument()
    })
  })
})
