/**
 * Grocery list hooks using React Query.
 *
 * Provides queries and mutations for grocery list operations:
 * - list: Get paginated grocery items with filters
 * - listByStore: Get items grouped by target store
 * - get: Get single grocery item by ID
 * - create: Add new grocery item
 * - update: Update existing grocery item
 * - delete: Remove grocery item
 * - purchase: Mark item as purchased
 * - unpurchase: Reverse purchase (mark as unpurchased)
 * - bulkPurchase: Mark multiple items as purchased (with optional inventory creation)
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query';
import { apiClient } from '../client';
import type {
  GroceryItemCreate,
  GroceryItemUpdate,
  GroceryItemResponse,
  BulkPurchaseRequest,
  BulkPurchaseResponse,
  StoreGroupedGroceryResponse,
} from '../types';

// Query keys for cache management
export const groceryKeys = {
  all: ['grocery'] as const,
  lists: () => [...groceryKeys.all, 'list'] as const,
  list: (filters: GroceryListFilters) => [...groceryKeys.lists(), filters] as const,
  byStore: (includePurchased: boolean) =>
    [...groceryKeys.all, 'by-store', { includePurchased }] as const,
  details: () => [...groceryKeys.all, 'detail'] as const,
  detail: (id: string) => [...groceryKeys.details(), id] as const,
};

export interface GroceryListFilters {
  limit?: number;
  offset?: number;
  purchased?: boolean;
  search?: string;
}

/**
 * List grocery items with filters and pagination
 */
export function useGroceryList(
  filters: GroceryListFilters = {},
  options?: Omit<UseQueryOptions<GroceryItemResponse[]>, 'queryKey' | 'queryFn'>
) {
  const params = new URLSearchParams();
  if (filters.limit !== undefined) params.append('limit', String(filters.limit));
  if (filters.offset !== undefined) params.append('offset', String(filters.offset));
  if (filters.purchased !== undefined)
    params.append('purchased', String(filters.purchased));
  if (filters.search) params.append('search', filters.search);

  const queryString = params.toString();

  return useQuery({
    queryKey: groceryKeys.list(filters),
    queryFn: async () => {
      return apiClient<GroceryItemResponse[]>(
        `/grocery${queryString ? `?${queryString}` : ''}`,
        { method: 'GET' }
      );
    },
    staleTime: 1 * 60 * 1000, // 1 minute - grocery lists change frequently
    ...options,
  });
}

/**
 * Get grocery items grouped by target store
 */
export function useGroceryListByStore(
  includePurchased: boolean = false,
  options?: Omit<
    UseQueryOptions<StoreGroupedGroceryResponse>,
    'queryKey' | 'queryFn'
  >
) {
  return useQuery({
    queryKey: groceryKeys.byStore(includePurchased),
    queryFn: async () => {
      return apiClient<StoreGroupedGroceryResponse>(
        `/grocery/by-store?include_purchased=${includePurchased}`,
        { method: 'GET' }
      );
    },
    staleTime: 1 * 60 * 1000, // 1 minute
    ...options,
  });
}

/**
 * Get single grocery item by ID
 */
export function useGroceryItem(
  id: string,
  options?: Omit<UseQueryOptions<GroceryItemResponse>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: groceryKeys.detail(id),
    queryFn: async () => {
      return apiClient<GroceryItemResponse>(`/grocery/${id}`, {
        method: 'GET',
      });
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
    ...options,
  });
}

/**
 * Create new grocery item
 */
export function useCreateGroceryItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: Omit<GroceryItemCreate, 'added_by'>) => {
      return apiClient<GroceryItemResponse>('/grocery', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      // Invalidate list queries to refetch with new item
      queryClient.invalidateQueries({ queryKey: groceryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: groceryKeys.all });
    },
  });
}

/**
 * Update grocery item
 */
export function useUpdateGroceryItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: GroceryItemUpdate }) => {
      return apiClient<GroceryItemResponse>(`/grocery/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },
    onSuccess: (_, variables) => {
      // Invalidate detail query for this item
      queryClient.invalidateQueries({ queryKey: groceryKeys.detail(variables.id) });
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: groceryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: groceryKeys.all });
    },
  });
}

/**
 * Delete grocery item
 */
export function useDeleteGroceryItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient<void>(`/grocery/${id}`, {
        method: 'DELETE',
      });
    },
    onSuccess: (_, id) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: groceryKeys.detail(id) });
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: groceryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: groceryKeys.all });
    },
  });
}

/**
 * Mark grocery item as purchased
 * Implements optimistic updates for responsive UI
 */
export function usePurchaseGroceryItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient<GroceryItemResponse>(`/grocery/${id}/purchase`, {
        method: 'PUT',
      });
    },
    // Optimistic update: immediately update UI before server responds
    onMutate: async (id) => {
      // Cancel any outgoing refetches to avoid overwriting our optimistic update
      await queryClient.cancelQueries({ queryKey: groceryKeys.detail(id) });

      // Snapshot the previous value
      const previousItem = queryClient.getQueryData<GroceryItemResponse>(
        groceryKeys.detail(id)
      );

      // Optimistically update to the new value
      if (previousItem) {
        queryClient.setQueryData<GroceryItemResponse>(groceryKeys.detail(id), {
          ...previousItem,
          purchased: true,
        });
      }

      // Return context with the snapshotted value
      return { previousItem };
    },
    // If mutation fails, use the context returned from onMutate to roll back
    onError: (_err, id, context) => {
      if (context?.previousItem) {
        queryClient.setQueryData(groceryKeys.detail(id), context.previousItem);
      }
    },
    // Always refetch after error or success to ensure sync with server
    onSettled: (_, __, id) => {
      queryClient.invalidateQueries({ queryKey: groceryKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: groceryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: groceryKeys.all });
    },
  });
}

/**
 * Mark grocery item as unpurchased (reverse purchase)
 * Implements optimistic updates for responsive UI
 */
export function useUnpurchaseGroceryItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient<GroceryItemResponse>(`/grocery/${id}/unpurchase`, {
        method: 'PUT',
      });
    },
    // Optimistic update: immediately update UI before server responds
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: groceryKeys.detail(id) });

      const previousItem = queryClient.getQueryData<GroceryItemResponse>(
        groceryKeys.detail(id)
      );

      if (previousItem) {
        queryClient.setQueryData<GroceryItemResponse>(groceryKeys.detail(id), {
          ...previousItem,
          purchased: false,
          purchased_by: null,
          purchased_date: null,
        });
      }

      return { previousItem };
    },
    onError: (_err, id, context) => {
      if (context?.previousItem) {
        queryClient.setQueryData(groceryKeys.detail(id), context.previousItem);
      }
    },
    onSettled: (_, __, id) => {
      queryClient.invalidateQueries({ queryKey: groceryKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: groceryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: groceryKeys.all });
    },
  });
}

/**
 * Mark multiple grocery items as purchased in a single transaction
 * Optionally creates inventory items from purchased groceries
 */
export function useBulkPurchaseGroceryItems() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: BulkPurchaseRequest) => {
      return apiClient<BulkPurchaseResponse>('/grocery/bulk-purchase', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      // Invalidate all grocery queries
      queryClient.invalidateQueries({ queryKey: groceryKeys.all });
      // If inventory was created, invalidate inventory queries
      queryClient.invalidateQueries({ queryKey: ['inventory'] });
    },
  });
}
