/**
 * Substitution preference hooks using React Query.
 *
 * Provides mutations and queries for managing user substitution preferences:
 * - list: Fetch all substitution preferences for current user
 * - create: Add new substitution preference
 * - update: Modify existing substitution preference
 * - delete: Remove substitution preference
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../client';
import type {
  SubstitutionPreferenceCreate,
  SubstitutionPreferenceUpdate,
  SubstitutionPreferenceResponse,
} from '../types';

// Query keys for cache management
export const substitutionKeys = {
  all: ['substitutions'] as const,
  list: () => [...substitutionKeys.all, 'list'] as const,
  detail: (id: string) => [...substitutionKeys.all, 'detail', id] as const,
};

/**
 * List all substitution preferences for current user
 */
export function useSubstitutionList() {
  return useQuery({
    queryKey: substitutionKeys.list(),
    queryFn: async () => {
      return apiClient<SubstitutionPreferenceResponse[]>('/users/me/substitutions', {
        method: 'GET',
      });
    },
  });
}

/**
 * Create new substitution preference mutation
 */
export function useCreateSubstitution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: SubstitutionPreferenceCreate) => {
      return apiClient<SubstitutionPreferenceResponse>('/users/me/substitutions', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      // Invalidate list to show new preference
      queryClient.invalidateQueries({ queryKey: substitutionKeys.list() });
    },
  });
}

/**
 * Update substitution preference mutation
 */
export function useUpdateSubstitution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: SubstitutionPreferenceUpdate }) => {
      return apiClient<SubstitutionPreferenceResponse>(`/users/me/substitutions/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      });
    },
    onSuccess: () => {
      // Invalidate list to show updated preference
      queryClient.invalidateQueries({ queryKey: substitutionKeys.list() });
    },
  });
}

/**
 * Delete substitution preference mutation
 */
export function useDeleteSubstitution() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: string) => {
      return apiClient<void>(`/users/me/substitutions/${id}`, {
        method: 'DELETE',
      });
    },
    onSuccess: () => {
      // Invalidate list to remove deleted preference
      queryClient.invalidateQueries({ queryKey: substitutionKeys.list() });
    },
  });
}
