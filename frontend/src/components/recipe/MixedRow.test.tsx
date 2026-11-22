import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import MixedRow from './MixedRow'
import type { RecommendedItem } from '../../api/types'

vi.mock('../../api/hooks/useCatalog', () => ({
  useOpenCard: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    reset: vi.fn(),
  })),
}))

vi.mock('../../api/hooks/useRecipeEngagement', () => ({
  useMyRecipeRelations: () => ({ data: new Map() }),
  useToggleBookmark: () => ({ mutate: vi.fn() }),
  useToggleLike: () => ({ mutate: vi.fn() }),
}))

const renderRow = (items: RecommendedItem[]) =>
  render(
    <BrowserRouter>
      <MixedRow title="For you" items={items} />
    </BrowserRouter>
  )

const makeCard = (id: string): RecommendedItem => ({
  kind: 'card',
  card: {
    id,
    name: `Card ${id}`,
    source_type: 'hellofresh_web',
    headline: null,
    image_url: null,
    prep_time_minutes: null,
    rating: null,
    rating_count: null,
    recipe_url: `https://hellofresh.com/${id}`,
    recipe_id: null,
    is_persisted: false,
    tags: [],
  },
})

const makeRecipe = (id: string): RecommendedItem => ({
  kind: 'recipe',
  recipe: {
    id,
    name: `Recipe ${id}`,
    source_type: 'manual',
    created_at: '2026-01-01',
    tags: [],
    cook_time_minutes: 20,
    prep_time_minutes: 5,
    base_servings: 2,
  },
})

beforeEach(() => {
  vi.clearAllMocks()
})

describe('MixedRow', () => {
  it('renders nothing when items is empty', () => {
    const { container } = renderRow([])
    expect(container.firstChild).toBeNull()
  })

  it('renders a CatalogCard for a card item', () => {
    renderRow([makeCard('c1')])
    expect(screen.getByRole('region', { name: 'For you' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Card c1' })).toBeInTheDocument()
  })

  it('renders a ConnectedRecipeCard for a recipe item', () => {
    renderRow([makeRecipe('r1')])
    expect(screen.getByRole('region', { name: 'For you' })).toBeInTheDocument()
    // ConnectedRecipeCard renders a link to the recipe
    expect(screen.getByRole('link', { name: /Recipe r1/ })).toBeInTheDocument()
  })

  it('renders mixed card and recipe items together', () => {
    renderRow([makeCard('c1'), makeRecipe('r1')])
    expect(screen.getByRole('button', { name: 'Card c1' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Recipe r1/ })).toBeInTheDocument()
  })

  it('renders the section heading', () => {
    renderRow([makeCard('c1')])
    expect(screen.getByRole('heading', { name: 'For you.' })).toBeInTheDocument()
  })

  it('renders an optional subtitle', () => {
    render(
      <BrowserRouter>
        <MixedRow title="For you" subtitle="Based on your taste" items={[makeCard('c1')]} />
      </BrowserRouter>
    )
    expect(screen.getByText('Based on your taste')).toBeInTheDocument()
  })

  it('wraps each item in a 184px container', () => {
    const { container } = renderRow([makeCard('c1'), makeRecipe('r1')])
    const listitems = container.querySelectorAll('[role="listitem"]')
    expect(listitems).toHaveLength(2)
    listitems.forEach((el) => expect(el.classList).toContain('w-[184px]'))
  })
})
