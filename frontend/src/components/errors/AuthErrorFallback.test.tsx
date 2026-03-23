import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AuthErrorFallback from './AuthErrorFallback';

describe('AuthErrorFallback', () => {
  const mockError = new Error('Test authentication error');
  const mockResetError = vi.fn();

  // Mock window.location.href
  let originalLocation: Location;

  beforeEach(() => {
    originalLocation = window.location;
    delete (window as any).location;
    window.location = { href: '' } as Location;
    mockResetError.mockClear();
    localStorage.clear();
  });

  afterEach(() => {
    window.location = originalLocation;
  });

  describe('Rendering', () => {
    it('renders the error fallback UI with appropriate messaging', () => {
      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      // Check for main heading
      expect(screen.getByRole('heading', { name: 'Authentication Error' })).toBeInTheDocument();

      // Check for user-friendly description
      expect(screen.getByText('Something went wrong while loading your session')).toBeInTheDocument();

      // Check for generic error message (should NOT display raw error.message)
      expect(screen.getByText(/We're having trouble loading your authentication session/i)).toBeInTheDocument();

      // Verify raw error message is NOT displayed (security check)
      expect(screen.queryByText('Test authentication error')).not.toBeInTheDocument();
    });

    it('displays action buttons', () => {
      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      expect(screen.getByRole('button', { name: 'Try Again' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Return to Login' })).toBeInTheDocument();
    });

    it('displays contact support message', () => {
      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      expect(
        screen.getByText('If this problem persists, please contact your household coordinator.')
      ).toBeInTheDocument();
    });

    it('renders warning emoji', () => {
      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      expect(screen.getByText('⚠️')).toBeInTheDocument();
    });
  });

  describe('Error Message Security', () => {
    it('does not leak internal error details to users', () => {
      const sensitiveError = new Error('Database connection failed: postgresql://user:password@host/db');
      render(<AuthErrorFallback error={sensitiveError} resetError={mockResetError} />);

      // Verify the sensitive error message is not displayed
      expect(screen.queryByText(/Database connection failed/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/postgresql/i)).not.toBeInTheDocument();

      // Verify only generic message is shown
      expect(screen.getByText(/We're having trouble loading your authentication session/i)).toBeInTheDocument();
    });

    it('displays generic message for different error types', () => {
      const errors = [
        new Error('Network timeout'),
        new Error('Invalid token signature'),
        new Error('User not found in database'),
      ];

      errors.forEach((error) => {
        const { unmount } = render(<AuthErrorFallback error={error} resetError={mockResetError} />);

        // All errors should show the same generic message
        expect(screen.getByText(/We're having trouble loading your authentication session/i)).toBeInTheDocument();

        // Verify specific error messages are not shown (if non-empty)
        if (error.message) {
          expect(screen.queryByText(error.message)).not.toBeInTheDocument();
        }

        unmount();
      });
    });
  });

  describe('Try Again Button', () => {
    it('calls resetError when Try Again button is clicked', async () => {
      const user = userEvent.setup();
      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      const tryAgainButton = screen.getByRole('button', { name: 'Try Again' });
      await user.click(tryAgainButton);

      expect(mockResetError).toHaveBeenCalledTimes(1);
    });

    it('does not clear localStorage when Try Again is clicked', async () => {
      const user = userEvent.setup();
      localStorage.setItem('access_token', 'test-token');

      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      await user.click(screen.getByRole('button', { name: 'Try Again' }));

      // Token should still be present after trying again
      expect(localStorage.getItem('access_token')).toBe('test-token');
    });
  });

  describe('Return to Login Button', () => {
    it('clears access token from localStorage when Return to Login is clicked', async () => {
      const user = userEvent.setup();
      localStorage.setItem('access_token', 'test-token');

      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      await user.click(screen.getByRole('button', { name: 'Return to Login' }));

      expect(localStorage.getItem('access_token')).toBeNull();
    });

    it('redirects to /login when Return to Login is clicked', async () => {
      const user = userEvent.setup();
      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      await user.click(screen.getByRole('button', { name: 'Return to Login' }));

      expect(window.location.href).toBe('/login');
    });

    it('clears token before redirecting (correct order)', async () => {
      const user = userEvent.setup();
      localStorage.setItem('access_token', 'test-token');

      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      await user.click(screen.getByRole('button', { name: 'Return to Login' }));

      // Verify both operations completed
      expect(localStorage.getItem('access_token')).toBeNull();
      expect(window.location.href).toBe('/login');
    });

    it('does not call resetError when Return to Login is clicked', async () => {
      const user = userEvent.setup();
      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      await user.click(screen.getByRole('button', { name: 'Return to Login' }));

      expect(mockResetError).not.toHaveBeenCalled();
    });
  });

  describe('Styling and Accessibility', () => {
    it('uses appropriate ARIA roles for interactive elements', () => {
      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      const buttons = screen.getAllByRole('button');
      expect(buttons).toHaveLength(2);
    });

    it('has accessible button labels', () => {
      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      expect(screen.getByRole('button', { name: 'Try Again' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Return to Login' })).toBeInTheDocument();
    });

    it('renders with proper class structure for responsive design', () => {
      const { container } = render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      // Check for responsive container classes
      const mainContainer = container.firstChild as HTMLElement;
      expect(mainContainer.className).toContain('min-h-screen');
      expect(mainContainer.className).toContain('flex');
    });
  });

  describe('Edge Cases', () => {
    it('handles missing error message gracefully', () => {
      const emptyError = new Error();
      render(<AuthErrorFallback error={emptyError} resetError={mockResetError} />);

      // Should still render generic message
      expect(screen.getByText(/We're having trouble loading your authentication session/i)).toBeInTheDocument();
    });

    it('handles multiple rapid clicks on Try Again', async () => {
      const user = userEvent.setup();
      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      const tryAgainButton = screen.getByRole('button', { name: 'Try Again' });

      await user.click(tryAgainButton);
      await user.click(tryAgainButton);
      await user.click(tryAgainButton);

      expect(mockResetError).toHaveBeenCalledTimes(3);
    });

    it('handles case when access_token does not exist in localStorage', async () => {
      const user = userEvent.setup();
      render(<AuthErrorFallback error={mockError} resetError={mockResetError} />);

      // Ensure no token exists
      expect(localStorage.getItem('access_token')).toBeNull();

      // Should not throw error when trying to remove non-existent token
      await user.click(screen.getByRole('button', { name: 'Return to Login' }));

      expect(window.location.href).toBe('/login');
    });
  });
});
