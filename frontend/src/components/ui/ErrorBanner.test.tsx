/**
 * Tests for ErrorBanner component.
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ErrorBanner from './ErrorBanner'

describe('ErrorBanner', () => {
  it('should render error message when provided', () => {
    const message = 'Something went wrong. Please try again.'
    render(<ErrorBanner message={message} />)

    const banner = screen.getByRole('alert')
    expect(banner).toBeInTheDocument()
    expect(banner).toHaveTextContent(message)
  })

  it('should have correct styling classes', () => {
    const message = 'Error message'
    render(<ErrorBanner message={message} />)

    const banner = screen.getByRole('alert')
    expect(banner).toHaveClass('mt-1')
    expect(banner).toHaveClass('px-3')
    expect(banner).toHaveClass('py-2')
    expect(banner).toHaveClass('bg-red-50')
    expect(banner).toHaveClass('border')
    expect(banner).toHaveClass('border-red-200')
    expect(banner).toHaveClass('rounded-md')
    expect(banner).toHaveClass('text-sm')
    expect(banner).toHaveClass('text-red-800')
  })

  it('should not render when message is null', () => {
    const { container } = render(<ErrorBanner message={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('should not render when message is undefined', () => {
    const { container } = render(<ErrorBanner message={undefined} />)
    expect(container.firstChild).toBeNull()
  })

  it('should not render when message is empty string', () => {
    const { container } = render(<ErrorBanner message="" />)
    expect(container.firstChild).toBeNull()
  })

  it('should have role="alert" for accessibility', () => {
    const message = 'Accessible error message'
    render(<ErrorBanner message={message} />)

    const banner = screen.getByRole('alert')
    expect(banner).toBeInTheDocument()
  })

  it('should handle long error messages', () => {
    const longMessage =
      'This is a very long error message that contains a lot of detail about what went wrong and how the user might be able to fix it. It should still render correctly.'
    render(<ErrorBanner message={longMessage} />)

    const banner = screen.getByRole('alert')
    expect(banner).toHaveTextContent(longMessage)
  })
})
