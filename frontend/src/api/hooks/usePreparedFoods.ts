/**
 * Prepared foods hooks using React Query.
 *
 * Provides queries and mutations for prepared food operations:
 * - list: Get paginated prepared foods with filters
 * - get: Get single prepared food by ID
 * - create: Add new prepared food
 * - update: Update existing prepared food
 * - delete: Remove prepared food
 * - consume: Decrement servings
 * - freeze: Move item to freezer
 * - thaw: Move item to fridge
 * - transfer: Move to different storage location
 */

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query';
import { apiClient } from '../client';
import type {
  PreparedFoodCreate,
  PreparedFoodUpdate,
  PreparedFoodResponse,
  PreparedFoodListResponse,
  PreparedFoodConsumptionResponse,
  TransferRequest,
  ConsumptionRequest,
} from '../types';

// Query keys for cache management
export const preparedFoodsKeys = {
  all: ['prepared-foods'] as const,
  lists: () => [...preparedFoodsKeys.all, 'list'] as const,
  list: (filters: PreparedFoodListFilters) =>
    [...preparedFoodsKeys.lists(), filters] as const,
  details: () => [...preparedFoodsKeys.all, 'detail'] as const,
  detail: (id: string) => [...preparedFoodsKeys.details(), id] as const,
};

export interface PreparedFoodListFilters {
  limit?: number;
  offset?: number;
  type?: string;
  storage_location?: string;
  shareability?: string;
  expiring_soon?: boolean;
  expiring_within_days?: number;
  search?: string;
}

/**
 * List prepared foods with filters and pagination
 */
export function usePreparedFoodList(
  filters: PreparedFoodListFilters = {},
  options?: Omit<
    UseQueryOptions<PreparedFoodListResponse[]>,
    'queryKey' | 'queryFn'
  >
) {
  const params = new URLSearchParams();
  if (filters.limit !== undefined) params.append('limit', String(filters.limit));
  if (filters.offset !== undefined) params.append('offset', String(filters.offset));
  if (filters.type) params.append('type', filters.type);
  if (filters.storage_location)
    params.append('storage_location', filters.storage_location);
  if (filters.shareability) params.append('shareability', filters.shareability);
  if (filters.expiring_soon !== undefined)
    params.append('expiring_soon', String(filters.expiring_soon));
  if (filters.expiring_within_days !== undefined)
    params.append('expiring_within_days', String(filters.expiring_within_days));
  if (filters.search) params.append('search', filters.search);

  const queryString = params.toString();

  return useQuery({
    queryKey: preparedFoodsKeys.list(filters),
    queryFn: async () => {
      return apiClient<PreparedFoodListResponse[]>(
        `/prepared-foods${queryString ? `?${queryString}` : ''}`,
        { method: 'GET' }
      );
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
    ...options,
  });
}

/**
 * Get single prepared food by ID
 */
export function usePreparedFood(
  id: string,
  options?: Omit<UseQueryOptions<PreparedFoodResponse>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: preparedFoodsKeys.detail(id),
    queryFn: async () => {
      return apiClient<PreparedFoodResponse>(`/prepared-foods/${id}`, {
        method: 'GET',
      });
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
    ...options,
  });
}

/**
 * Create new prepared food
 */
export function useCreatePreparedFood() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: Omit<PreparedFoodCreate, 'prepared_by'>) => {
      return apiClient<PreparedFoodResponse>('/prepared-foods', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      // Invalidate list queries to refetch with new item
      queryClient.invalidateQueries({ queryKey: preparedFoodsKeys.lists() });
    },
  });
}

/**
 * Update prepared food
 */
export function useUpdatePreparedFood() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data: PreparedFoodUpdate;
    }) => {
      return apiClient<PreparedFoodResponse>(`/prepared-foods/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },
    onSuccess: (_, variables) => {
      // Invalidate detail query for this item
      queryClient.invalidateQueries({
        queryKey: preparedFoodsKeys.detail(variables.id),
      });
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: preparedFoodsKeys.lists() });
    },
  });
}

/**
 * Delete prepared food
 */
export function useDeletePreparedFood() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient<void>(`/prepared-foods/${id}`, {
        method: 'DELETE',
      });
    },
    onSuccess: (_, id) => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: preparedFoodsKeys.detail(id) });
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: preparedFoodsKeys.lists() });
    },
  });
}

/**
 * Consume prepared food (decrement servings)
 */
export function useConsumePreparedFood() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      id,
      data,
    }: {
      id: string;
      data?: ConsumptionRequest;
    }) => {
      return apiClient<PreparedFoodConsumptionResponse>(
        `/prepared-foods/${id}/consume`,
        {
          method: 'POST',
          body: JSON.stringify(data || {}),
        }
      );
    },
    onSuccess: (result, variables) => {
      if (result.deleted) {
        // Item was deleted, remove from cache
        queryClient.removeQueries({
          queryKey: preparedFoodsKeys.detail(variables.id),
        });
      } else {
        // Item still exists, invalidate detail query
        queryClient.invalidateQueries({
          queryKey: preparedFoodsKeys.detail(variables.id),
        });
      }
      // Invalidate list queries
      queryClient.invalidateQueries({ queryKey: preparedFoodsKeys.lists() });
    },
  });
}

/**
 * Freeze prepared food (move to freezer)
 */
export function useFreezePreparedFood() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient<PreparedFoodResponse>(`/prepared-foods/${id}/freeze`, {
        method: 'POST',
      });
    },
    onSuccess: (_, id) => {
      // Invalidate detail and list queries
      queryClient.invalidateQueries({ queryKey: preparedFoodsKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: preparedFoodsKeys.lists() });
    },
  });
}

/**
 * Thaw prepared food (move to fridge)
 */
export function useThawPreparedFood() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient<PreparedFoodResponse>(`/prepared-foods/${id}/thaw`, {
        method: 'POST',
      });
    },
    onSuccess: (_, id) => {
      // Invalidate detail and list queries
      queryClient.invalidateQueries({ queryKey: preparedFoodsKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: preparedFoodsKeys.lists() });
    },
  });
}

/**
 * Transfer prepared food to different storage location
 */
export function useTransferPreparedFood() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: TransferRequest }) => {
      return apiClient<PreparedFoodResponse>(`/prepared-foods/${id}/transfer`, {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: (_, variables) => {
      // Invalidate detail and list queries
      queryClient.invalidateQueries({
        queryKey: preparedFoodsKeys.detail(variables.id),
      });
      queryClient.invalidateQueries({ queryKey: preparedFoodsKeys.lists() });
    },
  });
}
