import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../client';
import type { SourceStatus } from '../types';

export const sourceHealthKeys = {
  all: ['sourceHealth'] as const,
  status: () => [...sourceHealthKeys.all, 'status'] as const,
};

// staleTime 5 min — health checks run daily; no value in re-fetching on window focus.
export function useSourceHealth() {
  return useQuery({
    queryKey: sourceHealthKeys.status(),
    queryFn: () => apiClient<SourceStatus[]>('/sources/health', { method: 'GET' }),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

export function failingSources(statuses: SourceStatus[]): SourceStatus[] {
  return statuses.filter(s => s.status === 'failing');
}
