/**
 * Fallback UI component displayed when the AuthContext encounters an error.
 *
 * Provides user-friendly error message and recovery options:
 * - Try Again: Resets the error boundary to retry loading auth state
 * - Return to Login: Navigates to the login page for re-authentication
 *
 * Matches the app's design system (cream/olive/terra colors).
 */

interface AuthErrorFallbackProps {
  error: Error;
  resetError: () => void;
}

export default function AuthErrorFallback({ error, resetError }: AuthErrorFallbackProps) {
  const handleReturnToLogin = () => {
    // Clear any stale auth tokens before redirecting
    localStorage.removeItem('access_token');
    window.location.href = '/login';
  };

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="text-6xl mb-4">⚠️</div>
          <h1 className="text-2xl font-bold text-text-primary mb-2">Authentication Error</h1>
          <p className="text-text-secondary">Something went wrong while loading your session</p>
        </div>

        {/* Error Card */}
        <div className="bg-white rounded-card border border-warm-border p-8">
          {/* Error Message */}
          <div className="rounded-button border border-terra bg-terra/10 p-4 mb-6">
            <p className="text-sm text-terra-dark font-medium">{error.message}</p>
          </div>

          {/* Action Buttons */}
          <div className="space-y-3">
            <button
              onClick={resetError}
              className="w-full py-3 px-4 rounded-button bg-olive text-cream font-medium hover:bg-olive-dark focus:outline-none focus:ring-2 focus:ring-olive focus:ring-offset-2 focus:ring-offset-cream transition-colors"
            >
              Try Again
            </button>

            <button
              onClick={handleReturnToLogin}
              className="w-full py-3 px-4 rounded-button bg-cream text-olive font-medium border border-olive hover:bg-olive/10 focus:outline-none focus:ring-2 focus:ring-olive focus:ring-offset-2 focus:ring-offset-cream transition-colors"
            >
              Return to Login
            </button>
          </div>
        </div>

        {/* Footer Note */}
        <p className="text-center text-sm text-text-tertiary mt-6">
          If this problem persists, please contact your household coordinator.
        </p>
      </div>
    </div>
  );
}
