/**
 * Recipe hooks using React Query.
 *
 * Provides queries and mutations for recipe CRUD operations:
 * - list: Get paginated recipes with filters
 * - get: Get single recipe by ID
 * - create: Add new recipe
 * - createAdHoc: Create recipe from inventory items
 * - update: Update existing recipe
 * - delete: Remove recipe
 * - rate: Rate/favorite recipe
 * - Ingredient management: add, update, delete ingredients
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query';
import { apiClient } from '../client';
import type {
  RecipeCreate,
  RecipeUpdate,
  RecipeResponse,
  RecipeListResponse,
  AdHocRecipeCreate,
  RecipeIngredientCreate,
  RecipeIngredientUpdate,
  RecipeIngredientResponse,
  UserRecipeRatingCreate,
  UserRecipeRatingResponse,
  RecipeAggregateRatingsResponse,
} from '../types';

// Query keys for cache management
export const recipeKeys = {
  all: ['recipes'] as const,
  lists: () => [...recipeKeys.all, 'list'] as const,
  list: (filters: RecipeListFilters) => [...recipeKeys.lists(), filters] as const,
  details: () => [...recipeKeys.all, 'detail'] as const,
  detail: (id: string) => [...recipeKeys.details(), id] as const,
  ratings: (id: string) => [...recipeKeys.all, 'ratings', id] as const,
  myRating: (id: string) => [...recipeKeys.all, 'my-rating', id] as const,
};

export interface RecipeListFilters {
  limit?: number;
  offset?: number;
  source_type?: string;
  tag?: string;
  max_cook_time?: number;
  max_prep_time?: number;
  search?: string;
  has_variation?: boolean;
}

/**
 * List recipes with filters and pagination
 */
export function useRecipeList(
  filters: RecipeListFilters = {},
  options?: Omit<UseQueryOptions<RecipeListResponse[]>, 'queryKey' | 'queryFn'>
) {
  const params = new URLSearchParams();
  if (filters.limit !== undefined) params.append('limit', String(filters.limit));
  if (filters.offset !== undefined) params.append('offset', String(filters.offset));
  if (filters.source_type) params.append('source_type', filters.source_type);
  if (filters.tag) params.append('tag', filters.tag);
  if (filters.max_cook_time !== undefined)
    params.append('max_cook_time', String(filters.max_cook_time));
  if (filters.max_prep_time !== undefined)
    params.append('max_prep_time', String(filters.max_prep_time));
  if (filters.search) params.append('search', filters.search);
  if (filters.has_variation !== undefined)
    params.append('has_variation', String(filters.has_variation));

  const queryString = params.toString();

  return useQuery({
    queryKey: recipeKeys.list(filters),
    queryFn: async () => {
      return apiClient<RecipeListResponse[]>(
        `/recipes${queryString ? `?${queryString}` : ''}`,
        { method: 'GET' }
      );
    },
    staleTime: 10 * 60 * 1000, // 10 minutes - recipes change infrequently
    ...options,
  });
}

/**
 * Get single recipe by ID
 */
export function useRecipe(
  id: string,
  options?: Omit<UseQueryOptions<RecipeResponse>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: recipeKeys.detail(id),
    queryFn: async () => {
      return apiClient<RecipeResponse>(`/recipes/${id}`, {
        method: 'GET',
      });
    },
    staleTime: 10 * 60 * 1000, // 10 minutes
    ...options,
  });
}

/**
 * Create new recipe
 */
export function useCreateRecipe() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: Omit<RecipeCreate, 'created_by'>) => {
      return apiClient<RecipeResponse>('/recipes', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      // Invalidate list queries to refetch with new recipe
      queryClient.invalidateQueries({ queryKey: recipeKeys.lists() });
    },
  });
}

/**
 * Create ad-hoc recipe from inventory items
 */
export function useCreateAdHocRecipe() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: AdHocRecipeCreate) => {
      return apiClient<RecipeResponse>('/recipes/ad-hoc', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      // Invalidate recipe lists
      queryClient.invalidateQueries({ queryKey: recipeKeys.lists() });
      // If inventory was decremented, invalidate inventory queries
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
    },
  });
}

/**
 * Update recipe
 */
export function useUpdateRecipe() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: RecipeUpdate }) => {
      return apiClient<RecipeResponse>(`/recipes/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },
    onSuccess: (_, variables) => {
      // Invalidate detail query for this recipe
      queryClient.invalidateQueries({ queryKey: recipeKeys.detail(variables.id) });
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: recipeKeys.lists() });
    },
  });
}

/**
 * Delete recipe
 */
export function useDeleteRecipe() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient<void>(`/recipes/${id}`, {
        method: 'DELETE',
      });
    },
    onSuccess: (_, id) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: recipeKeys.detail(id) });
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: recipeKeys.lists() });
    },
  });
}

/**
 * Add ingredient to recipe
 */
export function useAddRecipeIngredient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      recipeId,
      data,
    }: {
      recipeId: string;
      data: RecipeIngredientCreate;
    }) => {
      return apiClient<RecipeIngredientResponse>(
        `/recipes/${recipeId}/ingredients`,
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      );
    },
    onSuccess: (_, variables) => {
      // Invalidate recipe detail to show new ingredient
      queryClient.invalidateQueries({
        queryKey: recipeKeys.detail(variables.recipeId),
      });
    },
  });
}

/**
 * Update recipe ingredient
 */
export function useUpdateRecipeIngredient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      recipeId,
      ingredientId,
      data,
    }: {
      recipeId: string;
      ingredientId: string;
      data: RecipeIngredientUpdate;
    }) => {
      return apiClient<RecipeIngredientResponse>(
        `/recipes/${recipeId}/ingredients/${ingredientId}`,
        {
          method: 'PUT',
          body: JSON.stringify(data),
        }
      );
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: recipeKeys.detail(variables.recipeId),
      });
    },
  });
}

/**
 * Delete recipe ingredient
 */
export function useDeleteRecipeIngredient() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      recipeId,
      ingredientId,
    }: {
      recipeId: string;
      ingredientId: string;
    }) => {
      return apiClient<void>(`/recipes/${recipeId}/ingredients/${ingredientId}`, {
        method: 'DELETE',
      });
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: recipeKeys.detail(variables.recipeId),
      });
    },
  });
}

/**
 * Rate recipe (upsert - create or update)
 */
export function useRateRecipe() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      recipeId,
      data,
    }: {
      recipeId: string;
      data: UserRecipeRatingCreate;
    }) => {
      return apiClient<UserRecipeRatingResponse>(`/recipes/${recipeId}/rate`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: (_, variables) => {
      // Invalidate rating queries
      queryClient.invalidateQueries({
        queryKey: recipeKeys.myRating(variables.recipeId),
      });
      queryClient.invalidateQueries({
        queryKey: recipeKeys.ratings(variables.recipeId),
      });
    },
  });
}

/**
 * Get current user's rating for a recipe
 */
export function useMyRecipeRating(
  recipeId: string,
  options?: Omit<UseQueryOptions<UserRecipeRatingResponse>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: recipeKeys.myRating(recipeId),
    queryFn: async () => {
      return apiClient<UserRecipeRatingResponse>(`/recipes/${recipeId}/my-rating`, {
        method: 'GET',
      });
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Delete current user's rating for a recipe
 */
export function useDeleteMyRecipeRating() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (recipeId: string) => {
      return apiClient<void>(`/recipes/${recipeId}/my-rating`, {
        method: 'DELETE',
      });
    },
    onSuccess: (_, recipeId) => {
      // Invalidate rating queries
      queryClient.invalidateQueries({ queryKey: recipeKeys.myRating(recipeId) });
      queryClient.invalidateQueries({ queryKey: recipeKeys.ratings(recipeId) });
    },
  });
}

/**
 * Get aggregate ratings for a recipe
 */
export function useRecipeAggregateRatings(
  recipeId: string,
  options?: Omit<
    UseQueryOptions<RecipeAggregateRatingsResponse>,
    'queryKey' | 'queryFn'
  >
) {
  return useQuery({
    queryKey: recipeKeys.ratings(recipeId),
    queryFn: async () => {
      return apiClient<RecipeAggregateRatingsResponse>(
        `/recipes/${recipeId}/ratings`,
        {
          method: 'GET',
        }
      );
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}
