/**
 * Recipe engagement hooks: bookmark and like.
 *
 * These wrap the dedicated toggle endpoints rather than POST /recipes/{id}/rate.
 * /rate is a whole-relation upsert — it writes every field of its request body
 * onto the row — so driving a bookmark button through it would clear the user's
 * like and rating. The toggles change one field each.
 *
 * Both are optimistic: a quick-action button on a card has to feel instant, and
 * the operations are idempotent, so a failed request rolls back cleanly.
 *
 * Bookmarking or liking also persists a browse-cache recipe server-side, which
 * is why the recipe queries are invalidated on settle — is_persisted changes.
 */

import { useMutation, useQuery, useQueryClient, type UseQueryOptions } from '@tanstack/react-query'
import { apiClient, ApiException } from '../client'
import type { BookmarkCreate, UserRecipeRelationResponse } from '../types'
import { recipeKeys } from './useRecipes'

/**
 * The relation a recipe has when the user has never engaged with it.
 *
 * GET /my-rating answers 404 rather than an empty body in that case, so the
 * query normalizes it to this. Callers get a shape, not a special case.
 */
export const EMPTY_RELATION: Omit<UserRecipeRelationResponse, 'id' | 'user_id' | 'recipe_id'> = {
  rating: null,
  is_bookmarked: false,
  is_liked: false,
  rating_photos: null,
  rating_comment: null,
  menu_id: null,
}

export type RecipeRelation = UserRecipeRelationResponse | typeof EMPTY_RELATION

export const relationKeys = {
  mine: ['recipes', 'my-relations'] as const,
}

/**
 * Every relation the current user holds, indexed by recipe_id.
 *
 * One request serves a whole grid of cards. Without it each card would fetch
 * its own relation and a 20-card browse page would fire 20 requests.
 */
export function useMyRecipeRelations(
  options?: Omit<UseQueryOptions<Map<string, UserRecipeRelationResponse>>, 'queryKey' | 'queryFn'>
) {
  return useQuery<Map<string, UserRecipeRelationResponse>>({
    queryKey: relationKeys.mine,
    queryFn: async () => {
      const relations = await apiClient<UserRecipeRelationResponse[]>(
        '/recipes/my-relations',
        { method: 'GET' }
      )
      return new Map(relations.map((r) => [r.recipe_id, r]))
    },
    staleTime: 60 * 1000,
    ...options,
  })
}

/**
 * Current user's relation to a recipe, with "never engaged" normalized to a
 * neutral relation instead of an error.
 */
export function useMyRecipeRelation(
  recipeId: string,
  options?: Omit<UseQueryOptions<RecipeRelation>, 'queryKey' | 'queryFn'>
) {
  return useQuery<RecipeRelation>({
    queryKey: recipeKeys.myRating(recipeId),
    queryFn: async () => {
      try {
        return await apiClient<UserRecipeRelationResponse>(`/recipes/${recipeId}/my-rating`, {
          method: 'GET',
        })
      } catch (error) {
        // No relation row yet — the user simply has not engaged with this recipe.
        if (error instanceof ApiException && error.status === 404) {
          return { ...EMPTY_RELATION }
        }
        throw error
      }
    },
    staleTime: 5 * 60 * 1000,
    ...options,
  })
}

interface ToggleVariables {
  recipeId: string
  /** Desired end state, not a flip — makes repeated taps idempotent. */
  next: boolean
  menuId?: string | null
}

/**
 * Shared optimistic-toggle machinery for the bookmark and like buttons.
 *
 * `field` is the single relation field this toggle owns; everything else in the
 * cached relation is carried through untouched, mirroring the server.
 */
function useRelationToggle(
  path: 'bookmark' | 'like',
  field: 'is_bookmarked' | 'is_liked'
) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ recipeId, next, menuId }: ToggleVariables) => {
      const body: BookmarkCreate | undefined =
        path === 'bookmark' && next && menuId ? { menu_id: menuId } : undefined

      return apiClient<UserRecipeRelationResponse>(`/recipes/${recipeId}/${path}`, {
        method: next ? 'POST' : 'DELETE',
        ...(body ? { body: JSON.stringify(body) } : {}),
      })
    },

    onMutate: async ({ recipeId, next }) => {
      const detailKey = recipeKeys.myRating(recipeId)
      // Stop in-flight refetches from overwriting the optimistic values.
      await queryClient.cancelQueries({ queryKey: detailKey })
      await queryClient.cancelQueries({ queryKey: relationKeys.mine })

      const previousDetail = queryClient.getQueryData<RecipeRelation>(detailKey)
      queryClient.setQueryData<RecipeRelation>(detailKey, {
        ...(previousDetail ?? EMPTY_RELATION),
        [field]: next,
      } as RecipeRelation)

      // The grid reads from the bulk map, so it has to move in step or a card's
      // button would snap back until the refetch lands.
      const previousMap = queryClient.getQueryData<Map<string, UserRecipeRelationResponse>>(
        relationKeys.mine
      )
      if (previousMap) {
        const optimistic = new Map(previousMap)
        const existing = optimistic.get(recipeId)
        optimistic.set(recipeId, {
          ...(existing ?? { ...EMPTY_RELATION, id: '', user_id: '', recipe_id: recipeId }),
          [field]: next,
        } as UserRecipeRelationResponse)
        queryClient.setQueryData(relationKeys.mine, optimistic)
      }

      return { previousDetail, previousMap, detailKey }
    },

    onError: (_error, _variables, context) => {
      if (context?.detailKey) {
        queryClient.setQueryData(context.detailKey, context.previousDetail)
      }
      if (context?.previousMap) {
        queryClient.setQueryData(relationKeys.mine, context.previousMap)
      }
    },

    onSettled: (_data, _error, { recipeId }) => {
      queryClient.invalidateQueries({ queryKey: recipeKeys.myRating(recipeId) })
      queryClient.invalidateQueries({ queryKey: recipeKeys.ratings(recipeId) })
      queryClient.invalidateQueries({ queryKey: relationKeys.mine })
      // Engaging can flip is_persisted on the recipe itself.
      queryClient.invalidateQueries({ queryKey: recipeKeys.detail(recipeId) })
      queryClient.invalidateQueries({ queryKey: recipeKeys.lists() })
    },
  })
}

/**
 * Toggle "save for later" on a recipe. Private to the user.
 *
 * `mutate({ recipeId, next: true })` bookmarks, `next: false` clears it.
 * Pass `menuId` to file the bookmark under a menu at the same time.
 */
export function useToggleBookmark() {
  return useRelationToggle('bookmark', 'is_bookmarked')
}

/** Toggle "I endorse this" on a recipe. Visible to the household. */
export function useToggleLike() {
  return useRelationToggle('like', 'is_liked')
}
