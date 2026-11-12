import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AddToPlanSheet from '../AddToPlanSheet'

function renderSheet(props: Partial<React.ComponentProps<typeof AddToPlanSheet>> = {}) {
  return render(
    <AddToPlanSheet
      open={true}
      onClose={vi.fn()}
      recipeId="recipe-1"
      defaultServings={4}
      onAdd={vi.fn().mockResolvedValue(undefined)}
      {...props}
    />
  )
}

describe('AddToPlanSheet', () => {
  it('renders day chips', () => {
    renderSheet()
    expect(screen.getByRole('button', { name: /today/i })).toBeInTheDocument()
  })

  it('renders meal type chips', () => {
    renderSheet()
    expect(screen.getByRole('button', { name: /breakfast/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /lunch/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /dinner/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /snack/i })).toBeInTheDocument()
  })

  it('defaults to dinner meal type', () => {
    renderSheet()
    expect(screen.getByRole('button', { name: /dinner/i })).toHaveAttribute('aria-pressed', 'true')
  })

  it('defaults to the provided servings', () => {
    renderSheet({ defaultServings: 2 })
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('increments servings when + button is clicked', async () => {
    renderSheet({ defaultServings: 4 })
    await userEvent.click(screen.getByRole('button', { name: /increase servings/i }))
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('decrements servings when − button is clicked', async () => {
    renderSheet({ defaultServings: 4 })
    await userEvent.click(screen.getByRole('button', { name: /decrease servings/i }))
    expect(screen.getByText('3')).toBeInTheDocument()
  })

  it('does not decrement servings below 1', async () => {
    renderSheet({ defaultServings: 1 })
    await userEvent.click(screen.getByRole('button', { name: /decrease servings/i }))
    expect(screen.getByText('1')).toBeInTheDocument()
  })

  it('calls onAdd with selected date, meal type and servings when Add is clicked', async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined)
    renderSheet({ defaultServings: 4, onAdd })
    await userEvent.click(screen.getByRole('button', { name: /^add$/i }))
    await waitFor(() => expect(onAdd).toHaveBeenCalledTimes(1))
    const [date, mealType, servings] = onAdd.mock.calls[0]
    expect(typeof date).toBe('string')
    expect(date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(mealType).toBe('dinner')
    expect(servings).toBe(4)
  })

  it('shows API error message in the sheet when onAdd rejects', async () => {
    const onAdd = vi.fn().mockRejectedValue(new Error('Slot already filled'))
    renderSheet({ onAdd })
    await userEvent.click(screen.getByRole('button', { name: /^add$/i }))
    await waitFor(() => expect(screen.getByText('Slot already filled')).toBeInTheDocument())
  })

  it('does not render when open=false', () => {
    renderSheet({ open: false })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
