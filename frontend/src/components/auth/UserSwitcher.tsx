/**
 * UserSwitcher component for shared device scenarios.
 *
 * Displays household members and allows quick switching between users.
 * Used on iPad kitchen terminal for "who are you?" selector flow.
 *
 * Features:
 * - Only visible to coordinator users (enforced by backend auth)
 * - Shows all household members
 * - Highlights current user
 * - Handles switch errors gracefully
 */

import { useState } from 'react';
import { useAuth } from '../../contexts/AuthContext';
import { useUsers } from '../../api/hooks/useUsers';
import { ApiException } from '../../api/client';
import { UserRole } from '../../api/types';

export default function UserSwitcher() {
  const { currentUser, switchUser } = useAuth();
  const { data: users, isLoading: isLoadingUsers } = useUsers();

  const [isSwitching, setIsSwitching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Only show for coordinator users
  // Use case-insensitive comparison to handle potential backend case variations
  if (!currentUser || currentUser.role.toLowerCase() !== UserRole.COORDINATOR.toLowerCase()) {
    return null;
  }

  // Loading state
  if (isLoadingUsers) {
    return (
      <div className="bg-cream-dark rounded-card border border-warm-border p-4">
        <p className="text-sm text-text-secondary">Loading household members...</p>
      </div>
    );
  }

  // No users or error state
  if (!users || users.length === 0) {
    return null;
  }

  /**
   * Handle user switch
   * Validates selection and calls switchUser from AuthContext
   */
  const handleSwitchUser = async (userId: string) => {
    // Don't allow switching to current user
    if (userId === currentUser.id) {
      return;
    }

    setError(null);
    setIsSwitching(true);

    try {
      await switchUser({ user_id: userId });
      // Success - AuthContext handles refetch
    } catch (err) {
      // Handle API errors
      if (err instanceof ApiException) {
        setError(err.detail || err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to switch user. Please try again.');
      }
    } finally {
      setIsSwitching(false);
    }
  };

  return (
    <div className="bg-cream-dark rounded-card border border-warm-border p-4">
      {/* Header */}
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-text-primary">Who are you?</h3>
        <p className="text-xs text-text-tertiary mt-1">
          Quick switch for shared device
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="mb-3 rounded-button border border-terra bg-terra/10 p-2">
          <p className="text-xs text-terra-dark">{error}</p>
        </div>
      )}

      {/* User List */}
      <div className="space-y-2">
        {users.map((user) => {
          const isCurrentUser = user.id === currentUser.id;

          return (
            <button
              key={user.id}
              onClick={() => handleSwitchUser(user.id)}
              disabled={isSwitching || isCurrentUser}
              className={`
                w-full text-left px-3 py-2 rounded-button border transition-colors
                ${
                  isCurrentUser
                    ? 'bg-olive/20 border-olive text-olive-dark font-medium cursor-default'
                    : 'bg-cream border-warm-border text-text-primary hover:bg-warm hover:border-olive focus:outline-none focus:ring-2 focus:ring-olive'
                }
                ${isSwitching && !isCurrentUser ? 'opacity-50 cursor-wait' : ''}
                ${isCurrentUser ? '' : 'disabled:opacity-50 disabled:cursor-not-allowed'}
              `}
            >
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <p className="text-sm font-medium">
                    {user.name}
                    {isCurrentUser && ' (current)'}
                  </p>
                  {user.dietary_profile.length > 0 && (
                    <p className="text-xs text-text-tertiary mt-0.5">
                      {user.dietary_profile.join(', ')}
                    </p>
                  )}
                </div>
                {isCurrentUser && (
                  <svg
                    className="w-5 h-5 text-olive"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
