import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter, MemoryRouter } from 'react-router-dom'
import BottomNav from './BottomNav'

// Helper to render component with Router context
const renderWithRouter = (ui: React.ReactElement, { route = '/' } = {}) => {
  return render(<MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>)
}

describe('BottomNav', () => {
  describe('navigation structure', () => {
    it('renders as navigation element with accessible label', () => {
      renderWithRouter(<BottomNav />)
      const nav = screen.getByRole('navigation', { name: /main navigation/i })
      expect(nav).toBeInTheDocument()
    })

    it('renders all 5 navigation tabs', () => {
      renderWithRouter(<BottomNav />)

      expect(screen.getByText('Home')).toBeInTheDocument()
      expect(screen.getByText('Plan')).toBeInTheDocument()
      expect(screen.getByText('Recipes')).toBeInTheDocument()
      expect(screen.getByText('Pantry')).toBeInTheDocument()
      expect(screen.getByText('List')).toBeInTheDocument()
    })

    it('renders all navigation items as links', () => {
      renderWithRouter(<BottomNav />)

      const links = screen.getAllByRole('link')
      expect(links).toHaveLength(5)
    })
  })

  describe('navigation links', () => {
    it('Home tab links to /', () => {
      renderWithRouter(<BottomNav />)
      const homeLink = screen.getByRole('link', { name: /home/i })
      expect(homeLink).toHaveAttribute('href', '/')
    })

    it('Plan tab links to /plan', () => {
      renderWithRouter(<BottomNav />)
      const planLink = screen.getByRole('link', { name: /plan/i })
      expect(planLink).toHaveAttribute('href', '/plan')
    })

    it('Recipes tab links to /recipes', () => {
      renderWithRouter(<BottomNav />)
      const recipesLink = screen.getByRole('link', { name: /recipes/i })
      expect(recipesLink).toHaveAttribute('href', '/recipes')
    })

    it('Pantry tab links to /pantry', () => {
      renderWithRouter(<BottomNav />)
      const pantryLink = screen.getByRole('link', { name: /pantry/i })
      expect(pantryLink).toHaveAttribute('href', '/pantry')
    })

    it('List tab links to /grocery', () => {
      renderWithRouter(<BottomNav />)
      const groceryLink = screen.getByRole('link', { name: /list/i })
      expect(groceryLink).toHaveAttribute('href', '/grocery')
    })
  })

  describe('active state detection', () => {
    it('marks Home tab as active when on / route', () => {
      renderWithRouter(<BottomNav />, { route: '/' })
      const homeLink = screen.getByRole('link', { name: /home/i })
      expect(homeLink).toHaveAttribute('aria-current', 'page')
    })

    it('marks Plan tab as active when on /plan route', () => {
      renderWithRouter(<BottomNav />, { route: '/plan' })
      const planLink = screen.getByRole('link', { name: /plan/i })
      expect(planLink).toHaveAttribute('aria-current', 'page')
    })

    it('marks Recipes tab as active when on /recipes route', () => {
      renderWithRouter(<BottomNav />, { route: '/recipes' })
      const recipesLink = screen.getByRole('link', { name: /recipes/i })
      expect(recipesLink).toHaveAttribute('aria-current', 'page')
    })

    it('marks Recipes tab as active when on nested recipe detail route', () => {
      renderWithRouter(<BottomNav />, { route: '/recipes/123' })
      const recipesLink = screen.getByRole('link', { name: /recipes/i })
      expect(recipesLink).toHaveAttribute('aria-current', 'page')
    })

    it('marks Pantry tab as active when on /pantry route', () => {
      renderWithRouter(<BottomNav />, { route: '/pantry' })
      const pantryLink = screen.getByRole('link', { name: /pantry/i })
      expect(pantryLink).toHaveAttribute('aria-current', 'page')
    })

    it('marks List tab as active when on /grocery route', () => {
      renderWithRouter(<BottomNav />, { route: '/grocery' })
      const groceryLink = screen.getByRole('link', { name: /list/i })
      expect(groceryLink).toHaveAttribute('aria-current', 'page')
    })

    it('uses exact match for Home tab to avoid false positives', () => {
      renderWithRouter(<BottomNav />, { route: '/plan' })
      const homeLink = screen.getByRole('link', { name: /home/i })
      expect(homeLink).not.toHaveAttribute('aria-current', 'page')
    })

    it('only one tab is marked as active at a time', () => {
      renderWithRouter(<BottomNav />, { route: '/recipes' })
      const activeLinks = screen.getAllByRole('link').filter((link) =>
        link.getAttribute('aria-current') === 'page'
      )
      expect(activeLinks).toHaveLength(1)
    })
  })

  describe('visual styles', () => {
    it('applies fixed bottom positioning classes', () => {
      renderWithRouter(<BottomNav />)
      const nav = screen.getByRole('navigation')
      expect(nav).toHaveClass('fixed', 'bottom-0')
    })

    it('applies white background with top border', () => {
      renderWithRouter(<BottomNav />)
      const nav = screen.getByRole('navigation')
      expect(nav).toHaveClass('bg-white', 'border-t')
    })

    it('active tab has olive text color', () => {
      renderWithRouter(<BottomNav />, { route: '/' })
      const homeLabel = screen.getByText('Home')
      expect(homeLabel).toHaveClass('text-olive')
    })

    it('inactive tab has tertiary text color', () => {
      renderWithRouter(<BottomNav />, { route: '/' })
      const planLabel = screen.getByText('Plan')
      expect(planLabel).toHaveClass('text-tertiary')
    })
  })

  describe('badge display', () => {
    it('does not show badge when count is 0', () => {
      renderWithRouter(<BottomNav />)
      // Badge should not be visible when count is 0
      const badges = document.querySelectorAll('.bg-mocha')
      expect(badges).toHaveLength(0)
    })
  })

  describe('accessibility', () => {
    it('has minimum 44px height for mobile touch targets', () => {
      renderWithRouter(<BottomNav />)
      const nav = screen.getByRole('navigation')
      expect(nav.querySelector('.h-16')).toBeInTheDocument()
    })

    it('provides aria-current for active page', () => {
      renderWithRouter(<BottomNav />, { route: '/pantry' })
      const pantryLink = screen.getByRole('link', { name: /pantry/i })
      expect(pantryLink).toHaveAttribute('aria-current', 'page')
    })

    it('does not set aria-current for inactive pages', () => {
      renderWithRouter(<BottomNav />, { route: '/pantry' })
      const homeLink = screen.getByRole('link', { name: /home/i })
      expect(homeLink).not.toHaveAttribute('aria-current')
    })
  })

  describe('icons', () => {
    it('renders icons for all navigation items', () => {
      const { container } = renderWithRouter(<BottomNav />)
      // Each nav item should have an SVG icon (lucide-react renders as SVG)
      const icons = container.querySelectorAll('svg')
      expect(icons.length).toBeGreaterThanOrEqual(5)
    })
  })
})
