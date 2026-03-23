/**
 * Authentication hooks using React Query.
 *
 * Provides mutations and queries for user authentication operations:
 * - login: Authenticate user and store JWT token
 * - register: Create new user account
 * - logout: Clear authentication token
 * - getCurrentUser: Fetch authenticated user profile
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  apiClient,
  setAuthToken,
  clearAuthToken,
  getAuthToken,
} from '../client';
import type {
  LoginRequest,
  TokenResponse,
  UserResponse,
  UserCreate,
  UserUpdate,
  PasswordChangeRequest,
  SwitchUserRequest,
} from '../types';

// Query keys for cache management
export const authKeys = {
  all: ['auth'] as const,
  currentUser: () => [...authKeys.all, 'current-user'] as const,
};

/**
 * Login mutation - authenticates user and stores JWT token
 */
export function useLogin() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (credentials: LoginRequest) => {
      const response = await apiClient<TokenResponse>('/auth/login', {
        method: 'POST',
        body: JSON.stringify(credentials),
        requiresAuth: false,
      });
      return response;
    },
    onSuccess: (data) => {
      // Store token in localStorage
      setAuthToken(data.access_token);
      // Invalidate current user query to trigger refetch
      queryClient.invalidateQueries({ queryKey: authKeys.currentUser() });
    },
  });
}

/**
 * Register mutation - creates new user account
 */
export function useRegister() {
  return useMutation({
    mutationFn: async (userData: UserCreate) => {
      return apiClient<UserResponse>('/auth/register', {
        method: 'POST',
        body: JSON.stringify(userData),
        requiresAuth: false,
      });
    },
  });
}

/**
 * Logout mutation - clears authentication token
 */
export function useLogout() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      // Clear token from localStorage
      clearAuthToken();
      // No API call needed - JWT is stateless
      return Promise.resolve();
    },
    onSuccess: () => {
      // Clear all queries from cache
      queryClient.clear();
    },
  });
}

/**
 * Get current user query - fetches authenticated user profile
 */
export function useCurrentUser() {
  return useQuery({
    queryKey: authKeys.currentUser(),
    queryFn: async () => {
      return apiClient<UserResponse>('/auth/me', {
        method: 'GET',
      });
    },
    enabled: !!getAuthToken(), // Only run query if token exists
    staleTime: 5 * 60 * 1000, // Consider data fresh for 5 minutes
  });
}

/**
 * Update current user profile mutation
 */
export function useUpdateProfile() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (userData: UserUpdate) => {
      return apiClient<UserResponse>('/auth/me', {
        method: 'PUT',
        body: JSON.stringify(userData),
      });
    },
    onSuccess: () => {
      // Invalidate current user query to show updated data
      queryClient.invalidateQueries({ queryKey: authKeys.currentUser() });
    },
  });
}

/**
 * Change password mutation
 */
export function useChangePassword() {
  return useMutation({
    mutationFn: async (passwordData: PasswordChangeRequest) => {
      return apiClient<{ message: string }>('/auth/change-password', {
        method: 'POST',
        body: JSON.stringify(passwordData),
      });
    },
  });
}

/**
 * Switch user mutation - for shared device household scenarios
 */
export function useSwitchUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (switchData: SwitchUserRequest) => {
      return apiClient<TokenResponse>('/auth/switch-user', {
        method: 'POST',
        body: JSON.stringify(switchData),
      });
    },
    onSuccess: (data) => {
      // Store new token in localStorage
      setAuthToken(data.access_token);
      // Invalidate all queries to refetch data for new user
      queryClient.invalidateQueries();
    },
  });
}
