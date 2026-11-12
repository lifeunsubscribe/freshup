import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import RecipeHeader from '../RecipeHeader'

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

function renderHeader(props: Partial<React.ComponentProps<typeof RecipeHeader>> = {}) {
  return render(
    <BrowserRouter>
      <RecipeHeader title="Pasta Bake" {...props} />
    </BrowserRouter>
  )
}

describe('RecipeHeader', () => {
  it('renders the recipe title', () => {
    renderHeader()
    expect(screen.getByRole('heading', { name: /pasta bake/i })).toBeInTheDocument()
  })

  it('renders bookmark button in outline state when isBookmarked=false', () => {
    renderHeader({ isBookmarked: false, onBookmarkToggle: vi.fn() })
    const btn = screen.getByRole('button', { name: /bookmark recipe/i })
    expect(btn).toBeInTheDocument()
    expect(btn).toHaveAttribute('aria-pressed', 'false')
  })

  it('renders bookmark button in filled state when isBookmarked=true', () => {
    renderHeader({ isBookmarked: true, onBookmarkToggle: vi.fn() })
    const btn = screen.getByRole('button', { name: /remove bookmark/i })
    expect(btn).toHaveAttribute('aria-pressed', 'true')
  })

  it('renders heart button in outline state when isLiked=false', () => {
    renderHeader({ isLiked: false, onLikeToggle: vi.fn() })
    const btn = screen.getByRole('button', { name: /like recipe/i })
    expect(btn).toHaveAttribute('aria-pressed', 'false')
  })

  it('renders heart button in filled state when isLiked=true', () => {
    renderHeader({ isLiked: true, onLikeToggle: vi.fn() })
    const btn = screen.getByRole('button', { name: /unlike recipe/i })
    expect(btn).toHaveAttribute('aria-pressed', 'true')
  })

  it('calls onBookmarkToggle when bookmark button is clicked', async () => {
    const onBookmarkToggle = vi.fn()
    renderHeader({ isBookmarked: false, onBookmarkToggle })
    await userEvent.click(screen.getByRole('button', { name: /bookmark recipe/i }))
    expect(onBookmarkToggle).toHaveBeenCalledTimes(1)
  })

  it('calls onLikeToggle when heart button is clicked', async () => {
    const onLikeToggle = vi.fn()
    renderHeader({ isLiked: false, onLikeToggle })
    await userEvent.click(screen.getByRole('button', { name: /like recipe/i }))
    expect(onLikeToggle).toHaveBeenCalledTimes(1)
  })

  it('disables engagement buttons when isEngagementLoading=true', () => {
    renderHeader({
      isEngagementLoading: true,
      onBookmarkToggle: vi.fn(),
      onLikeToggle: vi.fn(),
    })
    expect(screen.getByRole('button', { name: /bookmark/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /like/i })).toBeDisabled()
  })

  it('renders subtitle when provided', () => {
    renderHeader({ subtitle: 'with garlic bread' })
    expect(screen.getByText('with garlic bread')).toBeInTheDocument()
  })
})
