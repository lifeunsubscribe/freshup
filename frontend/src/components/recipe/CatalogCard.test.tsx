import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import CatalogCard from './CatalogCard'
import { useOpenCard } from '../../api/hooks/useCatalog'
import type { CardResponse } from '../../api/types'

vi.mock('../../api/hooks/useCatalog', () => ({
  useOpenCard: vi.fn(),
}))

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

const renderCard = (props: Partial<React.ComponentProps<typeof CatalogCard>> = {}) => {
  const defaults: React.ComponentProps<typeof CatalogCard> = {
    card: baseCard,
    collectionSlug: 'test-collection',
    ...props,
  }
  return render(
    <BrowserRouter>
      <CatalogCard {...defaults} />
    </BrowserRouter>
  )
}

const baseCard: CardResponse = {
  id: 'card-123',
  name: 'Lemon Herb Chicken',
  headline: 'Fresh and zesty',
  image_url: 'https://example.com/chicken.jpg',
  prep_time_minutes: 20,
  rating: 4.3,
  rating_count: 128,
  recipe_url: 'https://hellofresh.com/recipes/lemon-herb-chicken',
  recipe_id: null,
  is_persisted: false,
}

const mockMutate = vi.fn()
const mockReset = vi.fn()

function setMutationState(overrides: {
  isPending?: boolean
  isError?: boolean
  error?: Error | null
  mutate?: typeof mockMutate
  reset?: typeof mockReset
}) {
  vi.mocked(useOpenCard).mockReturnValue({
    mutate: overrides.mutate ?? mockMutate,
    isPending: overrides.isPending ?? false,
    isError: overrides.isError ?? false,
    error: overrides.error ?? null,
    reset: overrides.reset ?? mockReset,
  } as unknown as ReturnType<typeof useOpenCard>)
}

beforeEach(() => {
  mockNavigate.mockClear()
  mockMutate.mockClear()
  mockReset.mockClear()
  setMutationState({})
})

describe('CatalogCard', () => {
  describe('saved state display', () => {
    it('persisted card shows "Saved" pill on the photo', () => {
      renderCard({ card: { ...baseCard, is_persisted: true } })
      // The pill inside the image overlay area
      const pills = screen.getAllByText('Saved')
      expect(pills.length).toBeGreaterThanOrEqual(1)
    })

    it('persisted card does not show "Not saved yet"', () => {
      renderCard({ card: { ...baseCard, is_persisted: true } })
      expect(screen.queryByText('Not saved yet')).not.toBeInTheDocument()
    })

    it('unpersisted card shows "Not saved yet"', () => {
      renderCard({ card: { ...baseCard, is_persisted: false } })
      expect(screen.getByText('Not saved yet')).toBeInTheDocument()
    })

    it('unpersisted card has no "Saved" pill', () => {
      renderCard({ card: { ...baseCard, is_persisted: false } })
      expect(screen.queryByText('Saved')).not.toBeInTheDocument()
    })

    it('isNew adds "New" marker', () => {
      renderCard({ card: { ...baseCard, is_persisted: false }, isNew: true })
      expect(screen.getByText('New')).toBeInTheDocument()
    })

    it('isNew is not shown when false', () => {
      renderCard({ card: { ...baseCard, is_persisted: false }, isNew: false })
      expect(screen.queryByText('New')).not.toBeInTheDocument()
    })
  })

  describe('direct navigation when recipe_id is set', () => {
    it('navigates to /recipes/{recipe_id} on tap without calling the open endpoint', async () => {
      const user = userEvent.setup()
      renderCard({ card: { ...baseCard, recipe_id: 'existing-recipe-999' } })
      const card = screen.getByRole('button', { name: 'Lemon Herb Chicken' })
      await user.click(card)
      expect(mockNavigate).toHaveBeenCalledWith('/recipes/existing-recipe-999')
      expect(mockMutate).not.toHaveBeenCalled()
    })
  })

  describe('open flow when no recipe_id', () => {
    it('calls the open endpoint with cardId and collectionSlug on tap', async () => {
      const user = userEvent.setup()
      renderCard({ card: { ...baseCard, recipe_id: null }, collectionSlug: 'my-collection' })
      const card = screen.getByRole('button', { name: 'Lemon Herb Chicken' })
      await user.click(card)
      expect(mockMutate).toHaveBeenCalledWith(
        { cardId: 'card-123', source: 'hellofresh_web', collectionSlug: 'my-collection' },
        expect.objectContaining({ onSuccess: expect.any(Function) })
      )
    })

    it('shows "Opening…" overlay while pending', () => {
      setMutationState({ isPending: true })
      renderCard({ card: { ...baseCard, recipe_id: null } })
      expect(screen.getByText('Opening…')).toBeInTheDocument()
    })

    it('card is aria-disabled while pending', () => {
      setMutationState({ isPending: true })
      renderCard()
      const card = screen.getByRole('button', { name: 'Lemon Herb Chicken' })
      expect(card).toHaveAttribute('aria-disabled', 'true')
    })

    it('navigates to returned recipe id on success', async () => {
      const user = userEvent.setup()
      setMutationState({
        mutate: vi.fn().mockImplementation((_vars: unknown, callbacks: { onSuccess?: (r: { id: string }) => void }) => {
          callbacks?.onSuccess?.({ id: 'returned-recipe-456' } as never)
        }),
      })
      renderCard({ card: { ...baseCard, recipe_id: null } })
      const card = screen.getByRole('button', { name: 'Lemon Herb Chicken' })
      await user.click(card)
      expect(mockNavigate).toHaveBeenCalledWith('/recipes/returned-recipe-456')
    })

    it('does not navigate while pending', async () => {
      setMutationState({ isPending: true })
      renderCard({ card: { ...baseCard, recipe_id: null } })
      const card = screen.getByRole('button', { name: 'Lemon Herb Chicken' })
      fireEvent.click(card)
      expect(mockNavigate).not.toHaveBeenCalled()
      expect(mockMutate).not.toHaveBeenCalled()
    })
  })

  describe('open failure handling', () => {
    it('shows error message on failure', () => {
      setMutationState({ isError: true, error: new Error('Server error') })
      renderCard({ card: { ...baseCard, recipe_id: null } })
      expect(screen.getByText(/Server error/)).toBeInTheDocument()
    })

    it('shows fallback message when error has no message', () => {
      setMutationState({ isError: true, error: null })
      renderCard({ card: { ...baseCard, recipe_id: null } })
      expect(screen.getByText(/Could not open recipe/)).toBeInTheDocument()
    })

    it('shows "Try again" control on failure', () => {
      setMutationState({ isError: true, error: new Error('timeout') })
      renderCard({ card: { ...baseCard, recipe_id: null } })
      expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    })

    it('card is not disabled on error', () => {
      setMutationState({ isError: true, error: new Error('timeout') })
      renderCard({ card: { ...baseCard, recipe_id: null } })
      const card = screen.getByRole('button', { name: 'Lemon Herb Chicken' })
      expect(card).toHaveAttribute('aria-disabled', 'false')
    })

    it('"Try again" calls reset and retries the open', async () => {
      const user = userEvent.setup()
      const localReset = vi.fn()
      const localMutate = vi.fn()
      setMutationState({ isError: true, error: new Error('oops'), reset: localReset, mutate: localMutate })
      renderCard({ card: { ...baseCard, recipe_id: null } })
      await user.click(screen.getByRole('button', { name: 'Try again' }))
      expect(localReset).toHaveBeenCalled()
      expect(localMutate).toHaveBeenCalledWith(
        expect.objectContaining({ cardId: 'card-123' }),
        expect.any(Object)
      )
    })

    it('"Try again" does not also trigger the outer card handler', async () => {
      const user = userEvent.setup()
      const localReset = vi.fn()
      const localMutate = vi.fn()
      setMutationState({ isError: true, error: new Error('oops'), reset: localReset, mutate: localMutate })
      renderCard({ card: { ...baseCard, recipe_id: null } })
      await user.click(screen.getByRole('button', { name: 'Try again' }))
      // mutate called exactly once from handleRetry, not again from handleTap propagation
      expect(localMutate).toHaveBeenCalledTimes(1)
    })
  })

  describe('image fallback', () => {
    it('shows "No image" when image_url is null', () => {
      renderCard({ card: { ...baseCard, image_url: null } })
      expect(screen.getByText('No image')).toBeInTheDocument()
    })

    it('shows "No image" after image load error', () => {
      renderCard({ card: { ...baseCard, image_url: 'https://example.com/broken.jpg' } })
      const img = screen.getByAltText('Lemon Herb Chicken')
      fireEvent.error(img)
      expect(screen.getByText('No image')).toBeInTheDocument()
    })

    it('renders the image when image_url is set', () => {
      renderCard()
      expect(screen.getByAltText('Lemon Herb Chicken')).toHaveAttribute(
        'src',
        'https://example.com/chicken.jpg'
      )
    })
  })

  describe('content rendering', () => {
    it('renders the recipe name', () => {
      renderCard()
      expect(screen.getByRole('heading', { name: 'Lemon Herb Chicken' })).toBeInTheDocument()
    })

    it('renders the headline as a muted line', () => {
      renderCard()
      expect(screen.getByText('Fresh and zesty')).toBeInTheDocument()
    })

    it('omits headline when absent', () => {
      renderCard({ card: { ...baseCard, headline: null } })
      expect(screen.queryByText('Fresh and zesty')).not.toBeInTheDocument()
    })

    it('shows prep time as "N min"', () => {
      renderCard()
      expect(screen.getByText('20 min')).toBeInTheDocument()
    })

    it('omits prep time when null', () => {
      renderCard({ card: { ...baseCard, prep_time_minutes: null } })
      expect(screen.queryByText(/min/)).not.toBeInTheDocument()
    })

    it('shows rating as one decimal with count in parens', () => {
      renderCard()
      expect(screen.getByText('4.3 (128)')).toBeInTheDocument()
    })

    it('omits rating when rating is null', () => {
      renderCard({ card: { ...baseCard, rating: null } })
      expect(screen.queryByText(/\(\d+\)/)).not.toBeInTheDocument()
    })

    it('omits rating when rating_count is null', () => {
      renderCard({ card: { ...baseCard, rating_count: null } })
      expect(screen.queryByText(/\(\d+\)/)).not.toBeInTheDocument()
    })
  })

  describe('accessibility', () => {
    it('card has aria-label equal to recipe name', () => {
      renderCard()
      expect(screen.getByRole('button', { name: 'Lemon Herb Chicken' })).toBeInTheDocument()
    })

    it('activates on Enter key', async () => {
      const user = userEvent.setup()
      renderCard({ card: { ...baseCard, recipe_id: 'kb-recipe-1' } })
      screen.getByRole('button', { name: 'Lemon Herb Chicken' }).focus()
      await user.keyboard('{Enter}')
      expect(mockNavigate).toHaveBeenCalledWith('/recipes/kb-recipe-1')
    })

    it('activates on Space key', async () => {
      const user = userEvent.setup()
      renderCard({ card: { ...baseCard, recipe_id: 'kb-recipe-2' } })
      screen.getByRole('button', { name: 'Lemon Herb Chicken' }).focus()
      await user.keyboard(' ')
      expect(mockNavigate).toHaveBeenCalledWith('/recipes/kb-recipe-2')
    })
  })
})
