import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '../client'
import type { FeedbackKind, FeedbackResponse } from '../types'

export const feedbackKeys = {
  all: ['feedback'] as const,
}

/** Send a note to the developer. `page` is where in the app it was sent from. */
export function useSendFeedback() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (note: { message: string; page?: string; kind?: FeedbackKind }) =>
      apiClient<FeedbackResponse>('/feedback', { method: 'POST', body: JSON.stringify(note) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: feedbackKeys.all })
    },
  })
}

/** Every stored note, newest first. The API allows this for coordinators only. */
export function useFeedbackList() {
  return useQuery({
    queryKey: feedbackKeys.all,
    queryFn: () => apiClient<FeedbackResponse[]>('/feedback', { method: 'GET' }),
  })
}
