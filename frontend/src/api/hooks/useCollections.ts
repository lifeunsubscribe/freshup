import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../client'
import type { Collection, RecipeListResponse } from '../types'

/**
 * The user's recipe collections. The API calls them menus (/menus); in the
 * app they are collections, listed on My recipes.
 */
export const collectionKeys = {
  all: ['collections'] as const,
  list: () => [...collectionKeys.all, 'list'] as const,
  recipes: (id: string) => [...collectionKeys.all, 'recipes', id] as const,
}

export function useCollections() {
  return useQuery({
    queryKey: collectionKeys.list(),
    queryFn: async () => {
      const response = await apiClient<{ menus: Collection[]; total: number }>('/menus', { method: 'GET' })
      return response.menus
    },
  })
}

export function useCollectionRecipes(id: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: collectionKeys.recipes(id),
    queryFn: async () => {
      const response = await apiClient<{ recipes: RecipeListResponse[]; total: number }>(
        `/menus/${encodeURIComponent(id)}/recipes?limit=100`,
        { method: 'GET' }
      )
      return response.recipes
    },
    enabled,
  })
}

export function useCreateCollection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) =>
      apiClient<Collection>('/menus', { method: 'POST', body: JSON.stringify({ name }) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: collectionKeys.list() })
    },
  })
}

export function useDeleteCollection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiClient<void>(`/menus/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: collectionKeys.all })
    },
  })
}

export function useAddToCollection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ collectionId, recipeId }: { collectionId: string; recipeId: string }) =>
      apiClient<unknown>(`/menus/${encodeURIComponent(collectionId)}/recipes`, {
        method: 'POST',
        body: JSON.stringify({ recipe_id: recipeId }),
      }),
    onSuccess: (_, { collectionId }) => {
      queryClient.invalidateQueries({ queryKey: collectionKeys.recipes(collectionId) })
    },
  })
}

export function useRemoveFromCollection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ collectionId, recipeId }: { collectionId: string; recipeId: string }) =>
      apiClient<void>(
        `/menus/${encodeURIComponent(collectionId)}/recipes/${encodeURIComponent(recipeId)}`,
        { method: 'DELETE' }
      ),
    onSuccess: (_, { collectionId }) => {
      queryClient.invalidateQueries({ queryKey: collectionKeys.recipes(collectionId) })
    },
  })
}
