/**
 * Inventory hooks using React Query.
 *
 * Provides queries and mutations for inventory CRUD operations:
 * - list: Get paginated inventory items with filters
 * - get: Get single inventory item by ID
 * - create: Add new inventory item
 * - update: Update existing inventory item
 * - delete: Remove inventory item
 * - consume: Decrement quantity
 * - freeze: Move item to freezer
 * - thaw: Move item from freezer
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query';
import { apiClient } from '../client';
import type {
  InventoryItemCreate,
  InventoryItemUpdate,
  InventoryItemResponse,
  InventoryItemListResponse,
  LowStockAlertItem,
  ConsumptionRequest,
  ConsumptionResponse,
  ThawRequest,
  SetPreferredStoreRequest,
  AddAvailableStoreRequest,
  UpdateShareabilityRequest,
} from '../types';

// Query keys for cache management
export const inventoryKeys = {
  all: ['inventory'] as const,
  lists: () => [...inventoryKeys.all, 'list'] as const,
  list: (filters: InventoryListFilters) =>
    [...inventoryKeys.lists(), filters] as const,
  details: () => [...inventoryKeys.all, 'detail'] as const,
  detail: (id: string) => [...inventoryKeys.details(), id] as const,
  lowStock: () => [...inventoryKeys.all, 'low-stock'] as const,
};

export interface InventoryListFilters {
  limit?: number;
  offset?: number;
  category?: string;
  storage_location?: string;
  shareability?: string;
  is_staple?: boolean;
  expiring_soon?: boolean;
  expiring_within_days?: number;
  search?: string;
}

/**
 * List inventory items with filters and pagination
 */
export function useInventoryList(
  filters: InventoryListFilters = {},
  options?: Omit<
    UseQueryOptions<InventoryItemListResponse[]>,
    'queryKey' | 'queryFn'
  >
) {
  const params = new URLSearchParams();
  if (filters.limit !== undefined) params.append('limit', String(filters.limit));
  if (filters.offset !== undefined)
    params.append('offset', String(filters.offset));
  if (filters.category) params.append('category', filters.category);
  if (filters.storage_location)
    params.append('storage_location', filters.storage_location);
  if (filters.shareability)
    params.append('shareability', filters.shareability);
  if (filters.is_staple !== undefined)
    params.append('is_staple', String(filters.is_staple));
  if (filters.expiring_soon !== undefined)
    params.append('expiring_soon', String(filters.expiring_soon));
  if (filters.expiring_within_days !== undefined)
    params.append('expiring_within_days', String(filters.expiring_within_days));
  if (filters.search) params.append('search', filters.search);

  const queryString = params.toString();

  return useQuery({
    queryKey: inventoryKeys.list(filters),
    queryFn: async () => {
      return apiClient<InventoryItemListResponse[]>(
        `/inventory${queryString ? `?${queryString}` : ''}`,
        { method: 'GET' }
      );
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
    ...options,
  });
}

/**
 * Get single inventory item by ID
 */
export function useInventoryItem(
  id: string,
  options?: Omit<UseQueryOptions<InventoryItemResponse>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: inventoryKeys.detail(id),
    queryFn: async () => {
      return apiClient<InventoryItemResponse>(`/inventory/${id}`, {
        method: 'GET',
      });
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Get low stock alerts
 */
export function useLowStockAlerts(
  options?: Omit<UseQueryOptions<LowStockAlertItem[]>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: inventoryKeys.lowStock(),
    queryFn: async () => {
      return apiClient<LowStockAlertItem[]>('/inventory/alerts/low-stock', {
        method: 'GET',
      });
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Create new inventory item
 */
export function useCreateInventoryItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: Omit<InventoryItemCreate, 'added_by'>) => {
      return apiClient<InventoryItemResponse>('/inventory', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      // Invalidate list queries to refetch with new item
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lowStock() });
    },
  });
}

/**
 * Update inventory item
 */
export function useUpdateInventoryItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: InventoryItemUpdate;
    }) => {
      return apiClient<InventoryItemResponse>(`/inventory/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },
    onSuccess: (_, variables) => {
      // Invalidate detail query for this item
      queryClient.invalidateQueries({
        queryKey: inventoryKeys.detail(variables.id),
      });
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lowStock() });
    },
  });
}

/**
 * Delete inventory item
 */
export function useDeleteInventoryItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient<void>(`/inventory/${id}`, {
        method: 'DELETE',
      });
    },
    onSuccess: (_, id) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: inventoryKeys.detail(id) });
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lowStock() });
    },
  });
}

/**
 * Consume inventory item (decrement quantity)
 */
export function useConsumeInventoryItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data?: ConsumptionRequest;
    }) => {
      return apiClient<ConsumptionResponse>(`/inventory/${id}/consume`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
      });
    },
    onSuccess: (result, variables) => {
      if (result.deleted) {
        // Item was deleted, remove from cache
        queryClient.removeQueries({
          queryKey: inventoryKeys.detail(variables.id),
        });
      } else {
        // Item still exists, invalidate detail query
        queryClient.invalidateQueries({
          queryKey: inventoryKeys.detail(variables.id),
        });
      }
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lowStock() });
    },
  });
}

/**
 * Freeze inventory item (move to freezer)
 */
export function useFreezeInventoryItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient<InventoryItemResponse>(`/inventory/${id}/freeze`, {
        method: 'POST',
      });
    },
    onSuccess: (_, id) => {
      // Invalidate detail and list queries
      queryClient.invalidateQueries({ queryKey: inventoryKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
    },
  });
}

/**
 * Thaw inventory item (move from freezer)
 */
export function useThawInventoryItem() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data?: ThawRequest }) => {
      return apiClient<InventoryItemResponse>(`/inventory/${id}/thaw`, {
        method: 'POST',
        body: JSON.stringify(data || {}),
      });
    },
    onSuccess: (_, variables) => {
      // Invalidate detail and list queries
      queryClient.invalidateQueries({
        queryKey: inventoryKeys.detail(variables.id),
      });
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
    },
  });
}

/**
 * Set preferred store for inventory item
 */
export function useSetPreferredStore() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: SetPreferredStoreRequest;
    }) => {
      return apiClient<InventoryItemResponse>(
        `/inventory/${id}/preferred-store`,
        {
          method: 'PUT',
          body: JSON.stringify(data),
        }
      );
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: inventoryKeys.detail(variables.id),
      });
    },
  });
}

/**
 * Clear preferred store for inventory item
 */
export function useClearPreferredStore() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient<InventoryItemResponse>(
        `/inventory/${id}/preferred-store`,
        {
          method: 'DELETE',
        }
      );
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: inventoryKeys.detail(id) });
    },
  });
}

/**
 * Add available store for inventory item
 */
export function useAddAvailableStore() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: AddAvailableStoreRequest;
    }) => {
      return apiClient<InventoryItemResponse>(
        `/inventory/${id}/available-stores`,
        {
          method: 'POST',
          body: JSON.stringify(data),
        }
      );
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: inventoryKeys.detail(variables.id),
      });
    },
  });
}

/**
 * Remove available store from inventory item
 */
export function useRemoveAvailableStore() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, storeId }: { id: string; storeId: string }) => {
      return apiClient<InventoryItemResponse>(
        `/inventory/${id}/available-stores/${storeId}`,
        {
          method: 'DELETE',
        }
      );
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: inventoryKeys.detail(variables.id),
      });
    },
  });
}

/**
 * Update shareability status for inventory item
 */
export function useUpdateShareability() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: UpdateShareabilityRequest;
    }) => {
      return apiClient<InventoryItemResponse>(
        `/inventory/${id}/shareability`,
        {
          method: 'PUT',
          body: JSON.stringify(data),
        }
      );
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: inventoryKeys.detail(variables.id),
      });
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
    },
  });
}
