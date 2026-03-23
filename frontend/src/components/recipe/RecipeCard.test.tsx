import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import userEvent from '@testing-library/user-event'
import RecipeCard from './RecipeCard'

// Helper to render component with Router context
const renderWithRouter = (ui: React.ReactElement) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>)
}

describe('RecipeCard', () => {
  const mockRecipe = {
    id: 'recipe-123',
    name: 'Sweet Potato Chickpea Curry',
    source_type: 'hellofresh_card',
    cook_time_minutes: 25,
    prep_time_minutes: 10,
    tags: ['mexican', 'vegetarian', 'spicy'],
  }

  describe('basic rendering', () => {
    it('renders recipe name correctly', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      expect(screen.getByText('Sweet Potato Chickpea Curry')).toBeInTheDocument()
    })

    it('renders as a link to recipe detail page', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      const link = screen.getByRole('link')
      expect(link).toHaveAttribute('href', '/recipes/recipe-123')
    })

    it('displays "No image" placeholder when imageUrl is not provided', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      expect(screen.getByText('No image')).toBeInTheDocument()
    })

    it('renders image when imageUrl is provided', () => {
      renderWithRouter(
        <RecipeCard recipe={mockRecipe} imageUrl="https://example.com/image.jpg" />
      )
      const image = screen.getByAltText('Sweet Potato Chickpea Curry')
      expect(image).toHaveAttribute('src', 'https://example.com/image.jpg')
    })
  })

  describe('source badge', () => {
    it('displays "HelloFresh" badge for hellofresh_card source', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      expect(screen.getByText('HelloFresh')).toBeInTheDocument()
    })

    it('displays "My recipe" badge for manual source', () => {
      const manualRecipe = { ...mockRecipe, source_type: 'manual' }
      renderWithRouter(<RecipeCard recipe={manualRecipe} />)
      expect(screen.getByText('My recipe')).toBeInTheDocument()
    })

    it('displays "My recipe" badge for ad_hoc source', () => {
      const adHocRecipe = { ...mockRecipe, source_type: 'ad_hoc' }
      renderWithRouter(<RecipeCard recipe={adHocRecipe} />)
      expect(screen.getByText('My recipe')).toBeInTheDocument()
    })

    it('does not display badge for unknown source type', () => {
      const unknownRecipe = { ...mockRecipe, source_type: 'unknown' }
      renderWithRouter(<RecipeCard recipe={unknownRecipe} />)
      expect(screen.queryByText('HelloFresh')).not.toBeInTheDocument()
      expect(screen.queryByText('My recipe')).not.toBeInTheDocument()
    })
  })

  describe('favorite heart', () => {
    it('renders heart icon as outline when not favorited', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} isFavorited={false} />)
      const button = screen.getByRole('button', { name: 'Add to favorites' })
      expect(button).toBeInTheDocument()
    })

    it('renders heart icon as filled when favorited', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} isFavorited={true} />)
      const button = screen.getByRole('button', { name: 'Remove from favorites' })
      expect(button).toBeInTheDocument()
    })

    it('calls onFavoriteToggle when heart is clicked', async () => {
      const user = userEvent.setup()
      const onFavoriteToggle = vi.fn()
      renderWithRouter(
        <RecipeCard recipe={mockRecipe} onFavoriteToggle={onFavoriteToggle} />
      )
      const button = screen.getByRole('button', { name: 'Add to favorites' })
      await user.click(button)
      expect(onFavoriteToggle).toHaveBeenCalledTimes(1)
    })

    it('prevents navigation when heart is clicked', async () => {
      const user = userEvent.setup()
      const onFavoriteToggle = vi.fn()
      renderWithRouter(
        <RecipeCard recipe={mockRecipe} onFavoriteToggle={onFavoriteToggle} />
      )
      const button = screen.getByRole('button', { name: 'Add to favorites' })
      await user.click(button)
      // Navigation would change pathname, but it should remain at test root
      expect(window.location.pathname).toBe('/')
    })
  })

  describe('metadata display', () => {
    it('displays cook time when provided', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      expect(screen.getByText(/25 min/)).toBeInTheDocument()
    })

    it('displays servings when provided', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} servings={4} />)
      expect(screen.getByText(/4 srv/)).toBeInTheDocument()
    })

    it('displays cuisine tag (first tag) when available', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      expect(screen.getByText(/mexican/)).toBeInTheDocument()
    })

    it('displays metadata with separators in correct format', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} servings={4} />)
      // Check for the pattern: "25 min · 4 srv · mexican"
      const metadataText = screen.getByText(/25 min/).textContent
      expect(metadataText).toContain('25 min')
      expect(metadataText).toContain('4 srv')
      expect(metadataText).toContain('mexican')
      expect(metadataText).toContain(' · ')
    })

    it('handles missing cook time gracefully', () => {
      const recipeNoCookTime = { ...mockRecipe, cook_time_minutes: null }
      renderWithRouter(<RecipeCard recipe={recipeNoCookTime} servings={4} />)
      expect(screen.queryByText(/min/)).not.toBeInTheDocument()
      expect(screen.getByText(/4 srv/)).toBeInTheDocument()
    })

    it('handles missing servings gracefully', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      expect(screen.queryByText(/srv/)).not.toBeInTheDocument()
      expect(screen.getByText(/25 min/)).toBeInTheDocument()
    })

    it('handles missing cuisine tag gracefully', () => {
      const recipeNoTags = { ...mockRecipe, tags: [] }
      renderWithRouter(<RecipeCard recipe={recipeNoTags} servings={4} />)
      expect(screen.getByText(/25 min/)).toBeInTheDocument()
      expect(screen.getByText(/4 srv/)).toBeInTheDocument()
      // No extra separator after servings
      const metadataText = screen.getByText(/25 min/).textContent
      expect(metadataText).not.toMatch(/srv · $/)
    })
  })

  describe('household context', () => {
    it('displays "Never cooked" when no household context provided', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      expect(screen.getByText('Never cooked')).toBeInTheDocument()
    })

    it('displays "Never cooked" when timesCooked is 0', () => {
      renderWithRouter(
        <RecipeCard recipe={mockRecipe} householdContext={{ timesCooked: 0 }} />
      )
      expect(screen.getByText('Never cooked')).toBeInTheDocument()
    })

    it('displays "✓ Cooked 1x" when cooked once', () => {
      renderWithRouter(
        <RecipeCard recipe={mockRecipe} householdContext={{ timesCooked: 1 }} />
      )
      expect(screen.getByText('✓ Cooked 1x')).toBeInTheDocument()
    })

    it('displays "✓ Cooked 12x" when cooked multiple times', () => {
      renderWithRouter(
        <RecipeCard recipe={mockRecipe} householdContext={{ timesCooked: 12 }} />
      )
      expect(screen.getByText('✓ Cooked 12x')).toBeInTheDocument()
    })

    it('applies olive color class to cooked recipes', () => {
      renderWithRouter(
        <RecipeCard recipe={mockRecipe} householdContext={{ timesCooked: 5 }} />
      )
      const contextText = screen.getByText('✓ Cooked 5x')
      expect(contextText.className).toContain('text-olive')
    })

    it('applies mocha color class to never cooked recipes', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      const contextText = screen.getByText('Never cooked')
      expect(contextText.className).toContain('text-mocha')
    })
  })

  describe('variant styles', () => {
    it('renders grid variant by default', () => {
      const { container } = renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      const link = container.querySelector('a')
      expect(link?.className).not.toContain('min-w-[150px]')
      expect(link?.className).not.toContain('flex-shrink-0')
    })

    it('applies carousel variant classes when variant="carousel"', () => {
      const { container } = renderWithRouter(
        <RecipeCard recipe={mockRecipe} variant="carousel" />
      )
      const link = container.querySelector('a')
      expect(link?.className).toContain('min-w-[150px]')
      expect(link?.className).toContain('flex-shrink-0')
    })

    it('applies opacity-70 when isLastVisible is true', () => {
      const { container } = renderWithRouter(
        <RecipeCard recipe={mockRecipe} isLastVisible={true} />
      )
      const link = container.querySelector('a')
      expect(link?.className).toContain('opacity-70')
    })

    it('does not apply opacity-70 when isLastVisible is false', () => {
      const { container } = renderWithRouter(
        <RecipeCard recipe={mockRecipe} isLastVisible={false} />
      )
      const link = container.querySelector('a')
      expect(link?.className).not.toContain('opacity-70')
    })

    it('combines carousel variant with isLastVisible styles', () => {
      const { container } = renderWithRouter(
        <RecipeCard recipe={mockRecipe} variant="carousel" isLastVisible={true} />
      )
      const link = container.querySelector('a')
      expect(link?.className).toContain('min-w-[150px]')
      expect(link?.className).toContain('flex-shrink-0')
      expect(link?.className).toContain('opacity-70')
    })
  })

  describe('card styling', () => {
    it('applies rounded corners with 10px radius', () => {
      const { container } = renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      const link = container.querySelector('a')
      expect(link?.className).toContain('rounded-[10px]')
    })

    it('applies shadow and hover effects', () => {
      const { container } = renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      const link = container.querySelector('a')
      expect(link?.className).toContain('shadow-sm')
      expect(link?.className).toContain('hover:shadow-md')
    })

    it('applies overflow-hidden to contain rounded corners on image', () => {
      const { container } = renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      const link = container.querySelector('a')
      expect(link?.className).toContain('overflow-hidden')
    })
  })

  describe('recipe name truncation', () => {
    it('applies line-clamp-2 to recipe name', () => {
      renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      const heading = screen.getByRole('heading', {
        name: 'Sweet Potato Chickpea Curry',
      })
      expect(heading.className).toContain('line-clamp-2')
    })

    it('renders long recipe names with truncation class', () => {
      const longNameRecipe = {
        ...mockRecipe,
        name: 'This is an extremely long recipe name that should definitely truncate at two lines when displayed in the card component',
      }
      renderWithRouter(<RecipeCard recipe={longNameRecipe} />)
      const heading = screen.getByRole('heading')
      expect(heading.className).toContain('line-clamp-2')
      expect(heading.textContent).toContain('This is an extremely long recipe name')
    })
  })

  describe('image aspect ratio', () => {
    it('applies 4:3 aspect ratio container with padding-bottom 75%', () => {
      const { container } = renderWithRouter(<RecipeCard recipe={mockRecipe} />)
      const imageContainer = container.querySelector('.relative.w-full')
      expect(imageContainer).toHaveStyle({ paddingBottom: '75%' })
    })
  })
})
