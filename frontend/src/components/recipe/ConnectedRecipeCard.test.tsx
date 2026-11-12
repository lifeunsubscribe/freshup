import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'

import ConnectedRecipeCard from './ConnectedRecipeCard'
import { relationKeys } from '../../api/hooks/useRecipeEngagement'
import { recipeKeys } from '../../api/hooks/useRecipes'
import { apiClient } from '../../api/client'

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>('../../api/client')
  return { ...actual, apiClient: vi.fn() }
})

const mockApiClient = vi.mocked(apiClient)

const RECIPE_ID = 'recipe-connected-test'

const mockRecipe = {
  id: RECIPE_ID,
  name: 'Connected Test Recipe',
  source_type: 'manual',
  cook_time_minutes: 20,
  prep_time_minutes: 5,
  tags: [],
}

function makeRelation(overrides: Record<string, unknown> = {}) {
  return {
    id: 'rel-1',
    user_id: 'user-1',
    recipe_id: RECIPE_ID,
    rating: null,
    is_bookmarked: false,
    is_liked: false,
    rating_photos: null,
    rating_comment: null,
    menu_id: null,
    ...overrides,
  }
}

let queryClient: QueryClient

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  )
}

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  mockApiClient.mockReset()
})

describe('ConnectedRecipeCard', () => {
  describe('bookmark toggle', () => {
    it('reflects bookmarked state from relations map', () => {
      queryClient.setQueryData(
        relationKeys.mine,
        new Map([[RECIPE_ID, makeRelation({ is_bookmarked: true })]])
      )
      render(<ConnectedRecipeCard recipe={mockRecipe} />, { wrapper: Wrapper })
      expect(screen.getAllByText('Saved').length).toBeGreaterThanOrEqual(1)
    })

    it('reflects un-bookmarked state from relations map', () => {
      queryClient.setQueryData(
        relationKeys.mine,
        new Map([[RECIPE_ID, makeRelation({ is_bookmarked: false })]])
      )
      render(<ConnectedRecipeCard recipe={mockRecipe} />, { wrapper: Wrapper })
      expect(screen.getByText('Not saved yet')).toBeInTheDocument()
    })

    it('falls back to recipe.is_bookmarked when relations map has no entry', () => {
      queryClient.setQueryData(relationKeys.mine, new Map())
      render(
        <ConnectedRecipeCard recipe={{ ...mockRecipe, is_bookmarked: true }} />,
        { wrapper: Wrapper }
      )
      expect(screen.getAllByText('Saved').length).toBeGreaterThanOrEqual(1)
    })

    it('relation is_bookmarked:false wins over recipe.is_bookmarked:true', () => {
      queryClient.setQueryData(
        relationKeys.mine,
        new Map([[RECIPE_ID, makeRelation({ is_bookmarked: false })]])
      )
      render(
        <ConnectedRecipeCard recipe={{ ...mockRecipe, is_bookmarked: true }} />,
        { wrapper: Wrapper }
      )
      expect(screen.getByText('Not saved yet')).toBeInTheDocument()
    })

    it('flips to saved optimistically and invalidates recipeKeys.lists()', async () => {
      const user = userEvent.setup()
      queryClient.setQueryData(
        relationKeys.mine,
        new Map([[RECIPE_ID, makeRelation({ is_bookmarked: false })]])
      )
      // Seed a list entry so its invalidation state is observable
      queryClient.setQueryData(recipeKeys.lists(), [])
      mockApiClient.mockResolvedValueOnce(makeRelation({ is_bookmarked: true }))

      render(<ConnectedRecipeCard recipe={mockRecipe} />, { wrapper: Wrapper })
      expect(screen.getByText('Not saved yet')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Bookmark recipe' }))

      // Optimistic update flips the saved-state treatment immediately
      await waitFor(() =>
        expect(screen.getAllByText('Saved').length).toBeGreaterThanOrEqual(1)
      )

      // After the mutation settles, recipeKeys.lists() must be invalidated
      await waitFor(() =>
        expect(queryClient.getQueryState(recipeKeys.lists())?.isInvalidated).toBe(true)
      )
    })
  })
})
