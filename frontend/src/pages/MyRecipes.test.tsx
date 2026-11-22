import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, within } from '@testing-library/react'
import MyRecipes from './MyRecipes'
import { renderWithProviders } from '../test/renderWithProviders'
import type { Collection, RecipeListResponse } from '../api/types'

let saved: RecipeListResponse[] = []
let variations: RecipeListResponse[] = []
let collections: Collection[] = []
const collectionRecipes: Record<string, RecipeListResponse[]> = {}
const createMutate = vi.fn()

vi.mock('../api/hooks/useRecipes', () => ({
  useRecipeList: (filters: { bookmarked?: boolean; variations?: boolean }) => ({
    data: filters.variations ? variations : saved,
    isLoading: false,
    isError: false,
  }),
}))

vi.mock('../api/hooks/useCollections', () => ({
  useCollections: () => ({ data: collections, isLoading: false }),
  useCollectionRecipes: (id: string) => ({ data: collectionRecipes[id] ?? [] }),
  useCreateCollection: () => ({ mutate: createMutate, isPending: false }),
}))

vi.mock('../components/recipe/ConnectedRecipeCard', () => ({
  default: ({ recipe }: { recipe: RecipeListResponse }) => <div>{recipe.name}</div>,
}))

function recipe(id: string, name: string, extra: Partial<RecipeListResponse> = {}): RecipeListResponse {
  return {
    id,
    name,
    source_type: 'manual',
    created_at: '2026-11-21T00:00:00',
    tags: [],
    cook_time_minutes: null,
    prep_time_minutes: null,
    base_servings: 2,
    ...extra,
  }
}

function collection(id: string, name: string): Collection {
  return { id, name, description: null, cover_image: null, sort_order: 0, created_at: '2026-11-21T00:00:00' }
}

describe('My recipes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    saved = []
    variations = []
    collections = []
  })

  it('lists saved recipes', () => {
    saved = [recipe('r1', 'Fried Rice'), recipe('r2', 'Tofu Bowl')]

    renderWithProviders(<MyRecipes />)

    const section = within(screen.getByRole('region', { name: 'Saved' }))
    expect(section.getByText('Fried Rice')).toBeInTheDocument()
    expect(section.getByText('Tofu Bowl')).toBeInTheDocument()
  })

  it('says how to save something when nothing is saved', () => {
    renderWithProviders(<MyRecipes />)

    expect(screen.getByText(/Nothing saved yet/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Browse recipes' })).toHaveAttribute('href', '/recipes')
  })

  it('shows My variations only once there is one', () => {
    const { unmount } = renderWithProviders(<MyRecipes />)
    expect(screen.queryByRole('region', { name: 'My variations' })).not.toBeInTheDocument()
    unmount()

    variations = [recipe('v1', 'Fried Rice (my version)', { variation_of: 'r1' })]
    renderWithProviders(<MyRecipes />)

    expect(
      within(screen.getByRole('region', { name: 'My variations' })).getByText('Fried Rice (my version)')
    ).toBeInTheDocument()
  })

  it('lists collections with their size, linking to each', () => {
    collections = [collection('c1', 'Weeknights'), collection('c2', 'For guests')]
    collectionRecipes.c1 = [recipe('r1', 'Fried Rice'), recipe('r2', 'Tofu Bowl')]
    collectionRecipes.c2 = []

    renderWithProviders(<MyRecipes />)

    const weeknights = screen.getByRole('link', { name: /Weeknights/ })
    expect(weeknights).toHaveAttribute('href', '/my-recipes/collections/c1')
    expect(weeknights).toHaveTextContent('2 recipes')
    expect(screen.getByRole('link', { name: /For guests/ })).toHaveTextContent('0 recipes')
  })

  it('starts a new collection', () => {
    renderWithProviders(<MyRecipes />)

    fireEvent.click(screen.getByRole('button', { name: 'New collection' }))
    fireEvent.change(screen.getByLabelText('New collection name'), { target: { value: '  Weeknights ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create' }))

    expect(createMutate).toHaveBeenCalledWith('Weeknights', expect.anything())
  })
})
