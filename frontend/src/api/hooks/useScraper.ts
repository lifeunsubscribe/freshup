import { useMutation, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { apiClient, ApiException, getAuthToken, getApiBaseUrl } from '../client';
import type { ImportUrlRequest, ImportHtmlRequest, ImportResult } from '../types';
import { recipeKeys } from './useRecipes';

// Only invalidate for status=success or status=duplicate — an error response
// means nothing was persisted, so a refetch would be wasted.
function invalidateRecipeListsOnImport(queryClient: QueryClient, result: ImportResult): void {
  if (result.status !== 'error') {
    queryClient.invalidateQueries({ queryKey: recipeKeys.lists() });
  }
}

/**
 * Submit a URL for scraping. On success (or duplicate), invalidates the recipe
 * list so the library reflects the new import.
 */
export function useImportUrl() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ url }: ImportUrlRequest) => {
      return apiClient<ImportResult>('/scraper/import-url', {
        method: 'POST',
        body: JSON.stringify({ url }),
      });
    },
    onSuccess: (result) => invalidateRecipeListsOnImport(queryClient, result),
  });
}

/**
 * Submit a saved page (pasted HTML or uploaded file) for import.
 *
 * Pasted text sends `application/json`; a file upload sends `multipart/form-data`.
 * The apiClient always sets Content-Type: application/json, so the file path
 * uses a direct fetch() call to let the browser set the correct multipart
 * boundary in the Content-Type header.
 */
export function useImportHtml() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (request: ImportHtmlRequest) => {
      if ('html' in request) {
        return apiClient<ImportResult>('/scraper/import-html', {
          method: 'POST',
          body: JSON.stringify({ html: request.html, source_url: request.source_url }),
        });
      }

      // File upload: bypass apiClient so the browser can set Content-Type with boundary.
      const token = getAuthToken();
      const fd = new FormData();
      fd.append('file', request.file);
      fd.append('source_url', request.source_url);

      const response = await fetch(`${getApiBaseUrl()}/scraper/import-html`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token ?? ''}` },
        body: fd,
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({})) as { detail?: string };
        const message = data?.detail ?? response.statusText ?? 'An error occurred';
        throw new ApiException(message, response.status, data?.detail);
      }

      return response.json() as Promise<ImportResult>;
    },
    onSuccess: (result) => invalidateRecipeListsOnImport(queryClient, result),
  });
}
