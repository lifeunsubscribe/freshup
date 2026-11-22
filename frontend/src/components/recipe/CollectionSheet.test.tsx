import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent } from '@testing-library/react'
import CollectionSheet from './CollectionSheet'
import { renderWithProviders } from '../../test/renderWithProviders'
import type { Collection, RecipeListResponse } from '../../api/types'

let collections: Collection[] = []
const contents: Record<string, RecipeListResponse[]> = {}
const createMutate = vi.fn()
const addMutate = vi.fn()
const removeMutate = vi.fn()

vi.mock('../../api/hooks/useCollections', () => ({
  useCollections: () => ({ data: collections, isLoading: false, isError: false }),
  useCollectionRecipes: (id: string) => ({ data: contents[id] }),
  useCreateCollection: () => ({ mutate: createMutate, isPending: false, isError: false }),
  useAddToCollection: () => ({ mutate: addMutate, isPending: false, isError: false }),
  useRemoveFromCollection: () => ({ mutate: removeMutate, isPending: false, isError: false }),
}))

const collection = (id: string, name: string): Collection => ({
  id, name, description: null, cover_image: null, sort_order: 0, created_at: '2026-11-21T00:00:00',
})
const recipe = (id: string) =>
  ({ id, name: id, source_type: 'manual', created_at: '', tags: [], cook_time_minutes: null,
     prep_time_minutes: null, base_servings: 2 }) as RecipeListResponse

function renderSheet() {
  return renderWithProviders(
    <CollectionSheet open onClose={vi.fn()} recipeId="r1" recipeName="Fried Rice" />
  )
}

describe('CollectionSheet', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    collections = [collection('c1', 'Weeknights'), collection('c2', 'For guests')]
    contents.c1 = [recipe('r1')]
    contents.c2 = []
  })

  it('shows which collections already hold the recipe', () => {
    renderSheet()

    expect(screen.getByRole('button', { name: /Weeknights/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /For guests/ })).toHaveAttribute('aria-pressed', 'false')
  })

  it('adds to a collection, and takes it out of one that holds it', () => {
    renderSheet()

    fireEvent.click(screen.getByRole('button', { name: /For guests/ }))
    fireEvent.click(screen.getByRole('button', { name: /Weeknights/ }))

    expect(addMutate).toHaveBeenCalledWith({ collectionId: 'c2', recipeId: 'r1' })
    expect(removeMutate).toHaveBeenCalledWith({ collectionId: 'c1', recipeId: 'r1' })
  })

  it('starts a new collection with the recipe in it', () => {
    createMutate.mockImplementation((_name, options) => options.onSuccess(collection('c3', 'To try')))
    renderSheet()

    fireEvent.change(screen.getByLabelText('New collection name'), { target: { value: 'To try' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create' }))

    expect(createMutate).toHaveBeenCalledWith('To try', expect.anything())
    expect(addMutate).toHaveBeenCalledWith({ collectionId: 'c3', recipeId: 'r1' })
  })
})
