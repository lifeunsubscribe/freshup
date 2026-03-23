/**
 * Login page component.
 *
 * Provides email/password authentication form with:
 * - Design system styling (mocha/terra colors)
 * - Form validation
 * - Error message display
 * - Redirect to home on successful login
 */

import { useState, FormEvent } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { ApiException } from '../api/client';

export default function Login() {
  const { login } = useAuth();

  // Form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Handle form submission
   * Validates inputs, calls login, and handles errors
   */
  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);

    // Client-side validation
    if (!email.trim()) {
      setError('Email is required');
      return;
    }
    if (!password) {
      setError('Password is required');
      return;
    }

    setIsSubmitting(true);

    try {
      await login({ email: email.trim(), password });
      // Login success - AuthContext handles redirect to home
    } catch (err) {
      // Handle API errors
      if (err instanceof ApiException) {
        // Use the detail message from the API
        setError(err.detail || err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-text-primary mb-2">FreshUp</h1>
          <p className="text-text-secondary">Sign in to your account</p>
        </div>

        {/* Login Form Card */}
        <div className="bg-white rounded-card border border-warm-border p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Email Input */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-text-primary mb-2">
                Email
              </label>
              <input
                type="email"
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={isSubmitting}
                className="w-full px-4 py-2 rounded-button border border-warm-border bg-cream text-text-primary placeholder-text-tertiary focus:outline-none focus:ring-2 focus:ring-olive focus:border-olive disabled:opacity-50 disabled:cursor-not-allowed"
                placeholder="you@example.com"
                autoComplete="email"
                required
              />
            </div>

            {/* Password Input */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-text-primary mb-2">
                Password
              </label>
              <input
                type="password"
                id="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                className="w-full px-4 py-2 rounded-button border border-warm-border bg-cream text-text-primary placeholder-text-tertiary focus:outline-none focus:ring-2 focus:ring-olive focus:border-olive disabled:opacity-50 disabled:cursor-not-allowed"
                placeholder="Enter your password"
                autoComplete="current-password"
                required
              />
            </div>

            {/* Error Message */}
            {error && (
              <div className="rounded-button border border-terra bg-terra/10 p-4">
                <p className="text-sm text-terra-dark font-medium">{error}</p>
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3 px-4 rounded-button bg-olive text-cream font-medium hover:bg-olive-dark focus:outline-none focus:ring-2 focus:ring-olive focus:ring-offset-2 focus:ring-offset-cream disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSubmitting ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>

        {/* Footer Note */}
        <p className="text-center text-sm text-text-tertiary mt-6">
          FreshUp is a household kitchen management system. Contact your household coordinator if you need access.
        </p>
      </div>
    </div>
  );
}
