import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../client';
import type { Theme } from '../types';

export const themeKeys = {
  all: ['themes'] as const,
};

/**
 * Recipe themes (cuisine, main ingredient, dish type, diet, meal type, source)
 * with their values and the lists behind each value.
 *
 * Database-only on the server, so it is cheap; 5 min stale time keeps card
 * counts reasonably fresh as collection rows fill in.
 */
export function useThemes(options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: themeKeys.all,
    queryFn: () => apiClient<Theme[]>('/themes', { method: 'GET' }),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
    ...options,
  });
}
