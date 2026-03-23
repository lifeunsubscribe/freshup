/**
 * User management hooks using React Query.
 *
 * Provides queries for household member operations:
 * - listUsers: Fetch all household members for user switcher
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../client';
import type { UserListResponse } from '../types';

// Query keys for cache management
export const usersKeys = {
  all: ['users'] as const,
  list: () => [...usersKeys.all, 'list'] as const,
};

/**
 * List users query - fetches all household members
 * Used by iPad user switcher and meal plan opt-in flows
 */
export function useUsers() {
  return useQuery({
    queryKey: usersKeys.list(),
    queryFn: async () => {
      return apiClient<UserListResponse[]>('/users', {
        method: 'GET',
      });
    },
    staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
  });
}
