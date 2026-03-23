import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ErrorBoundary } from './ErrorBoundary';

// Test component that throws an error when shouldThrow is true
function ThrowError({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Test error message');
  }
  return <div>Normal content</div>;
}

describe('ErrorBoundary', () => {
  // Suppress console.error in tests to avoid cluttering test output
  const originalError = console.error;
  beforeAll(() => {
    console.error = vi.fn();
  });

  afterAll(() => {
    console.error = originalError;
  });

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary fallback={() => <div>Error occurred</div>}>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Normal content')).toBeInTheDocument();
    expect(screen.queryByText('Error occurred')).not.toBeInTheDocument();
  });

  it('renders fallback when an error is thrown', () => {
    render(
      <ErrorBoundary fallback={(error) => <div>Error: {error.message}</div>}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Error: Test error message')).toBeInTheDocument();
    expect(screen.queryByText('Normal content')).not.toBeInTheDocument();
  });

  it('passes error to fallback function', () => {
    const fallbackFn = vi.fn(() => <div>Fallback</div>);

    render(
      <ErrorBoundary fallback={fallbackFn}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(fallbackFn).toHaveBeenCalled();
    const error = fallbackFn.mock.calls[0][0];
    expect(error).toBeInstanceOf(Error);
    expect(error.message).toBe('Test error message');
  });

  it('calls resetError when reset function is invoked', async () => {
    const user = userEvent.setup();

    const FallbackWithReset = ({ error, resetError }: { error: Error; resetError: () => void }) => (
      <div>
        <div>Error: {error.message}</div>
        <button onClick={resetError}>Reset</button>
      </div>
    );

    // Start with error state
    const { rerender } = render(
      <ErrorBoundary fallback={(error, resetError) => <FallbackWithReset error={error} resetError={resetError} />}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Error: Test error message')).toBeInTheDocument();

    // Click reset - this will reset the error boundary but children still throw
    // So we need to provide non-throwing children after reset
    await user.click(screen.getByText('Reset'));

    // After reset, rerender with non-throwing children
    rerender(
      <ErrorBoundary fallback={(error, resetError) => <FallbackWithReset error={error} resetError={resetError} />}>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );

    expect(screen.getByText('Normal content')).toBeInTheDocument();
  });

  it('logs error to console', () => {
    const consoleSpy = vi.spyOn(console, 'error');

    render(
      <ErrorBoundary fallback={() => <div>Error</div>}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(consoleSpy).toHaveBeenCalled();
  });

  it('handles different error types', () => {
    function ThrowCustomError() {
      throw new Error('Custom error type');
    }

    render(
      <ErrorBoundary fallback={(error) => <div>Caught: {error.message}</div>}>
        <ThrowCustomError />
      </ErrorBoundary>
    );

    expect(screen.getByText('Caught: Custom error type')).toBeInTheDocument();
  });

  it('renders custom fallback UI', () => {
    const CustomFallback = ({ error }: { error: Error }) => (
      <div className="custom-error">
        <h1>Oops!</h1>
        <p>{error.message}</p>
      </div>
    );

    render(
      <ErrorBoundary fallback={(error) => <CustomFallback error={error} />}>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    expect(screen.getByRole('heading', { name: 'Oops!' })).toBeInTheDocument();
    expect(screen.getByText('Test error message')).toBeInTheDocument();
  });
});
