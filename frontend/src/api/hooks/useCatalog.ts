import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../client';
import type { CollectionSummary, CollectionDetail, RecipeResponse } from '../types';
import { recipeKeys } from './useRecipes';

export const catalogKeys = {
  all: ['catalog'] as const,
  collections: (source: string) => [...catalogKeys.all, source, 'collections'] as const,
  collection: (source: string, slug: string) => [...catalogKeys.all, source, 'collections', slug] as const,
};

// staleTime 10 min — list changes only on sitemap reseed; endpoint is rate-limited to 5/min.
export function useCollections(source: string) {
  return useQuery({
    queryKey: catalogKeys.collections(source),
    queryFn: () =>
      apiClient<CollectionSummary[]>(`/catalog/${source}/collections`, { method: 'GET' }),
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export interface UseCollectionOptions {
  fresh?: boolean;
  enabled?: boolean;
}

// staleTime 10 min — rate-limited to 10/min. Pass enabled:false until the row is in view;
// this hook does not scroll-gate itself.
export function useCollection(
  source: string,
  slug: string,
  opts: UseCollectionOptions = {}
) {
  const { fresh, enabled = true } = opts;
  const qs = fresh !== undefined ? `?fresh=${fresh}` : '';

  return useQuery({
    queryKey: [...catalogKeys.collection(source, slug), { fresh: fresh ?? null }],
    queryFn: () =>
      apiClient<CollectionDetail>(`/catalog/${source}/collections/${slug}${qs}`, { method: 'GET' }),
    staleTime: 10 * 60 * 1000,
    enabled,
  });
}

export interface OpenCardVariables {
  cardId: string;
  source: string;
  collectionSlug: string;
}

export function useOpenCard() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ cardId }: OpenCardVariables) =>
      apiClient<RecipeResponse>(`/catalog/cards/${cardId}/open`, { method: 'POST' }),
    onSuccess: (recipe, { source, collectionSlug }) => {
      // Seed the detail cache so navigating to the recipe skips a network round-trip.
      queryClient.setQueryData(recipeKeys.detail(recipe.id), recipe);
      // The card's recipe_id and is_persisted changed — the collection row is stale.
      queryClient.invalidateQueries({ queryKey: catalogKeys.collection(source, collectionSlug) });
    },
  });
}
