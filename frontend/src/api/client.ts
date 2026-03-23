/**
 * Base API client with authentication and error handling.
 *
 * Provides a fetch wrapper that automatically attaches JWT tokens
 * and handles errors consistently across all API calls.
 */

const TOKEN_KEY = 'auth_token';

export interface ApiError {
  message: string;
  status: number;
  detail?: string;
}

export class ApiException extends Error {
  status: number;
  detail?: string;

  constructor(message: string, status: number, detail?: string) {
    super(message);
    this.name = 'ApiException';
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions extends RequestInit {
  requiresAuth?: boolean;
}

/**
 * Get the base API URL from environment variables
 */
export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_URL || 'http://localhost:8000';
}

/**
 * Store JWT token in localStorage
 */
export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

/**
 * Retrieve JWT token from localStorage
 */
export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Remove JWT token from localStorage
 */
export function clearAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * Decode base64url string (JWT uses base64url, not standard base64)
 */
function decodeBase64Url(base64url: string): string {
  // Convert base64url to standard base64
  let base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');

  // Add padding if necessary
  const padding = base64.length % 4;
  if (padding === 2) {
    base64 += '==';
  } else if (padding === 3) {
    base64 += '=';
  }

  return atob(base64);
}

/**
 * Check if user is authenticated (has valid token)
 */
export function isAuthenticated(): boolean {
  const token = getAuthToken();
  if (!token) {
    return false;
  }

  try {
    // JWT tokens are base64url encoded and have 3 parts: header.payload.signature
    const parts = token.split('.');
    if (parts.length !== 3) {
      return false;
    }

    // Decode the payload (second part) using base64url decoding
    const payload = JSON.parse(decodeBase64Url(parts[1]));

    // Check if token has expiration claim
    if (!payload.exp) {
      // If no expiration, treat as valid (though this shouldn't happen with proper JWTs)
      return true;
    }

    // JWT exp is in seconds, Date.now() is in milliseconds
    const currentTime = Math.floor(Date.now() / 1000);

    // Token is valid if current time is before expiration
    return currentTime < payload.exp;
  } catch (error) {
    // If token parsing fails, consider it invalid
    return false;
  }
}

/**
 * Base fetch wrapper with authentication and error handling
 */
export async function apiClient<T = unknown>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { requiresAuth = true, ...fetchOptions } = options;

  const url = `${getApiBaseUrl()}${endpoint}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  // Merge any custom headers from fetchOptions
  if (fetchOptions.headers) {
    const customHeaders = new Headers(fetchOptions.headers);
    customHeaders.forEach((value, key) => {
      headers[key] = value;
    });
  }

  // Attach Authorization header if token exists and auth is required
  if (requiresAuth) {
    const token = getAuthToken();
    if (!token) {
      throw new ApiException(
        'Authentication required',
        401,
        'No authentication token found. Please log in.'
      );
    }
    headers['Authorization'] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      headers,
    });

    // Handle 204 No Content (no response body)
    if (response.status === 204) {
      return undefined as T;
    }

    // Parse response body
    let data: unknown;
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    // Handle error responses
    if (!response.ok) {
      // Clear token on 401 Unauthorized - indicates token is invalid/expired
      if (response.status === 401) {
        clearAuthToken();
      }

      const errorData = data as { detail?: string };
      const message = errorData?.detail || response.statusText || 'An error occurred';
      throw new ApiException(message, response.status, errorData?.detail);
    }

    return data as T;
  } catch (error) {
    // Re-throw ApiException as-is
    if (error instanceof ApiException) {
      throw error;
    }

    // Handle network errors
    if (error instanceof TypeError) {
      throw new ApiException(
        'Network error: Unable to connect to server',
        0,
        'Check your internet connection and try again'
      );
    }

    // Handle other errors
    throw new ApiException(
      'An unexpected error occurred',
      500,
      error instanceof Error ? error.message : String(error)
    );
  }
}
