/**
 * Authentication context for FreshUp.
 *
 * Provides authentication state and operations throughout the app:
 * - currentUser: The authenticated user's profile
 * - isAuthenticated: Boolean indicating if user is logged in
 * - isLoading: Boolean indicating if auth state is being determined
 * - login: Function to authenticate with email/password
 * - logout: Function to clear authentication and redirect to login
 * - switchUser: Function to switch to another household member (shared device)
 */

import { createContext, useContext, ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCurrentUser, useLogin, useLogout, useSwitchUser } from '../api/hooks/useAuth';
import { isAuthenticated as checkIsAuthenticated } from '../api/client';
import type { LoginRequest, UserResponse, SwitchUserRequest } from '../api/types';

interface AuthContextType {
  currentUser: UserResponse | undefined;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  switchUser: (request: SwitchUserRequest) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const navigate = useNavigate();

  // React Query hooks for auth operations
  const { data: currentUser, isLoading: isLoadingUser, isError: isUserError, refetch } = useCurrentUser();
  const loginMutation = useLogin();
  const logoutMutation = useLogout();
  const switchUserMutation = useSwitchUser();

  // Determine if user is authenticated
  // User is authenticated only if they have a valid token AND current user data
  // If user data fails to load (e.g., expired token), isAuthenticated will be false
  const isAuthenticated = checkIsAuthenticated() && !!currentUser;

  // Loading state: only show loading on initial auth check
  // Don't show loading for mutations (login/logout/switch)
  // If there's an error loading user data, stop showing loading state
  const isLoading = isLoadingUser && !isUserError;

  /**
   * Login with email and password
   * On success, redirects to home page
   */
  const login = async (credentials: LoginRequest): Promise<void> => {
    await loginMutation.mutateAsync(credentials);
    // Refetch current user to populate context
    const result = await refetch();
    if (result.isError) {
      throw new Error('Failed to fetch user data after login');
    }
    // Redirect to home page
    navigate('/');
  };

  /**
   * Logout and clear authentication
   * Redirects to login page
   */
  const logout = async (): Promise<void> => {
    await logoutMutation.mutateAsync();
    // Redirect to login page
    navigate('/login');
  };

  /**
   * Switch to another household member's session
   * Used on shared devices (iPad kitchen terminal)
   * Only available to coordinator users (enforced by backend)
   */
  const switchUser = async (request: SwitchUserRequest): Promise<void> => {
    await switchUserMutation.mutateAsync(request);
    // Refetch current user to show new user's profile
    const result = await refetch();
    if (result.isError) {
      throw new Error('Failed to fetch user data after switching users');
    }
    // Stay on current page (user switcher is typically in header/nav)
  };

  const value: AuthContextType = {
    currentUser,
    isAuthenticated,
    isLoading,
    login,
    logout,
    switchUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook to access auth context
 * Must be used within AuthProvider
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
