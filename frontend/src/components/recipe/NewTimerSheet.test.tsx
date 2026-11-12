import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import NewTimerSheet from './NewTimerSheet'

describe('NewTimerSheet', () => {
  it('renders nothing when closed', () => {
    const { container } = render(
      <NewTimerSheet open={false} onClose={vi.fn()} onStart={vi.fn()} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders the sheet dialog when open', () => {
    render(<NewTimerSheet open={true} onClose={vi.fn()} onStart={vi.fn()} />)
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('shows "New timer" as the sheet title', () => {
    render(<NewTimerSheet open={true} onClose={vi.fn()} onStart={vi.fn()} />)
    expect(screen.getByText(/new timer/i)).toBeInTheDocument()
  })

  it('has a name field defaulting to "Timer"', () => {
    render(<NewTimerSheet open={true} onClose={vi.fn()} onStart={vi.fn()} />)
    const nameInput = screen.getByLabelText(/name/i)
    expect(nameInput).toHaveValue('Timer')
  })

  it('has a duration field defaulting to 5', () => {
    render(<NewTimerSheet open={true} onClose={vi.fn()} onStart={vi.fn()} />)
    const durationInput = screen.getByLabelText(/duration/i)
    expect(durationInput).toHaveValue(5)
  })

  it('renders quick-amount buttons', () => {
    render(<NewTimerSheet open={true} onClose={vi.fn()} onStart={vi.fn()} />)
    expect(screen.getByRole('button', { name: /^1 min$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^5 min$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^10 min$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^15 min$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^30 min$/ })).toBeInTheDocument()
  })

  it('clicking a quick-amount button updates the duration field', async () => {
    render(<NewTimerSheet open={true} onClose={vi.fn()} onStart={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /^15 min$/ }))
    expect(screen.getByLabelText(/duration/i)).toHaveValue(15)
  })

  it('calls onStart with the name and totalSeconds when Start is clicked', async () => {
    const onStart = vi.fn()
    render(<NewTimerSheet open={true} onClose={vi.fn()} onStart={onStart} />)

    // Set name to "Pasta" and duration to 10 min
    const nameInput = screen.getByLabelText(/name/i)
    await userEvent.clear(nameInput)
    await userEvent.type(nameInput, 'Pasta')
    await userEvent.click(screen.getByRole('button', { name: /^10 min$/ }))
    await userEvent.click(screen.getByRole('button', { name: /^start$/i }))

    expect(onStart).toHaveBeenCalledWith('Pasta', 600)
  })

  it('defaults name to "Timer" when the field is empty', async () => {
    const onStart = vi.fn()
    render(<NewTimerSheet open={true} onClose={vi.fn()} onStart={onStart} />)

    const nameInput = screen.getByLabelText(/name/i)
    await userEvent.clear(nameInput)
    await userEvent.click(screen.getByRole('button', { name: /^start$/i }))

    expect(onStart).toHaveBeenCalledWith('Timer', expect.any(Number))
  })

  it('calls onClose when the Close button is clicked', async () => {
    const onClose = vi.fn()
    render(<NewTimerSheet open={true} onClose={onClose} onStart={vi.fn()} />)
    await userEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(onClose).toHaveBeenCalled()
  })
})
