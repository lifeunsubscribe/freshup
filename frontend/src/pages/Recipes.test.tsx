/**
 * Recipes page — theme and collection-row tests
 *
 * The library carousel/grid behaviour lives in __tests__/Recipes.test.tsx.
 * This file covers rows driven by GET /themes: the main-page sampler, theme
 * pages ("See all"), theme filters, lazy collection loading, the More
 * Collections sheet, and source bylines.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import Recipes from './Recipes'
import { useRecipeList } from '../api'
import { useCollections, useCollection } from '../api/hooks/useCatalog'
import { useThemes } from '../api/hooks/useThemes'
import type { CollectionSummary, Theme, ThemeCollection, ThemeValue } from '../api/types'

// ── API mocks ──────────────────────────────────────────────────────────────────

vi.mock('../api', () => ({
  useRecipeList: vi.fn(),
}))

vi.mock('../api/hooks/useRecipeEngagement', () => ({
  useMyRecipeRelations: () => ({ data: new Map() }),
  useToggleBookmark: () => ({ mutate: vi.fn() }),
  useToggleLike: () => ({ mutate: vi.fn() }),
}))

vi.mock('../api/hooks/useCatalog', () => ({
  useCollections: vi.fn(),
  useCollection: vi.fn(),
  useOpenCard: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    reset: vi.fn(),
  })),
}))

vi.mock('../api/hooks/useThemes', () => ({
  useThemes: vi.fn(),
}))

// ── IntersectionObserver stub ──────────────────────────────────────────────────

type ObserverEntry = { element: Element; callback: IntersectionObserverCallback }
const observers: ObserverEntry[] = []

class MockIntersectionObserver {
  private cb: IntersectionObserverCallback
  constructor(cb: IntersectionObserverCallback) {
    this.cb = cb
  }
  observe(el: Element) {
    observers.push({ element: el, callback: this.cb })
  }
  disconnect() {}
  unobserve() {}
}

function triggerAllObservers() {
  act(() => {
    observers.forEach(({ callback }) => {
      callback([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver)
    })
  })
}

// ── Fixtures ───────────────────────────────────────────────────────────────────

const coll = (
  slug: string,
  name: string,
  card_count: number,
  fetched = card_count > 0,
  contains: string[] = []
): ThemeCollection => ({
  source_type: 'hellofresh_web',
  slug,
  name,
  card_count,
  last_fetched_at: fetched ? '2026-11-01T00:00:00Z' : null,
  contains,
})

const val = (value: string, label: string, extra: Partial<ThemeValue> = {}): ThemeValue => ({
  value,
  label,
  library_tag: null,
  library_source_type: null,
  library_count: 0,
  match_tags: [],
  match_source_types: [],
  collections: [],
  ...extra,
})

const italianHF = coll('italian-recipes', 'Italian Recipes', 12, true, ['diet:vegetarian'])
const vegHF = coll('vegetarian-recipes', 'Vegetarian Recipes', 30, true, ['cuisine:italian'])
const thaiHF = coll('thai-recipes', 'Thai Recipes', 8)
const koreanHF = coll('korean-recipes', 'Korean Recipes', 0, false)
const chickenHF = coll('chicken-recipes', 'Chicken Recipes', 30)
const beefHF = coll('beef-recipes', 'Beef Recipes', 5)
const porkHF = coll('pork-recipes', 'Pork Recipes', 2)

const THEMES: Theme[] = [
  {
    key: 'cuisine',
    label: 'Cuisine',
    values: [
      val('italian', 'Italian', { library_tag: 'italian', library_count: 1, match_tags: ['italian'], collections: [italianHF] }),
      val('thai', 'Thai', { collections: [thaiHF] }),
      val('korean', 'Korean', { collections: [koreanHF] }),
    ],
  },
  {
    key: 'ingredient',
    label: 'Main ingredient',
    values: [
      val('chicken', 'Chicken', { collections: [chickenHF] }),
      val('beef', 'Beef', { collections: [beefHF] }),
      val('pork', 'Pork', { collections: [porkHF] }),
    ],
  },
  { key: 'dish', label: 'Dish type', values: [] },
  { key: 'diet', label: 'Diet', values: [val('vegetarian', 'Vegetarian', { collections: [vegHF] })] },
  {
    key: 'source',
    label: 'Source',
    values: [
      val('hellofresh', 'HelloFresh', {
        library_source_type: 'hellofresh_web',
        library_count: 1,
        match_source_types: ['hellofresh_web'],
        collections: [chickenHF, italianHF, thaiHF, beefHF, porkHF, koreanHF],
      }),
    ],
  },
]

const recipe = (id: string, tags: string[]) => ({
  id,
  name: `Recipe ${id}`,
  source_type: 'manual',
  created_at: '2026-01-01',
  tags,
  cook_time_minutes: 20,
  prep_time_minutes: 5,
  base_servings: 2,
})

const summary = (slug: string, name: string, card_count: number): CollectionSummary => ({
  slug,
  name,
  card_count,
  last_fetched_at: null,
})

const renderPage = (path = '/recipes') =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Recipes />
    </MemoryRouter>
  )

type RowQueryOptions = { enabled?: boolean; fresh?: boolean }

const region = (name: string) => screen.queryByRole('region', { name })

// ── Setup ──────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  observers.length = 0
  // @ts-expect-error -- jsdom has no IntersectionObserver; install the stub
  window.IntersectionObserver = MockIntersectionObserver

  vi.mocked(useRecipeList).mockReturnValue({ data: [], isLoading: false, isError: false, error: null } as never)
  vi.mocked(useCollection).mockReturnValue({
    data: undefined,
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
  } as never)
  vi.mocked(useCollections).mockReturnValue({
    data: [summary('italian-recipes', 'Italian Recipes', 12), summary('hall-of-fame', 'Hall of Fame', 0)],
    isLoading: false,
    isError: false,
    error: null,
  } as never)
  vi.mocked(useThemes).mockReturnValue({ data: THEMES } as never)
})

afterEach(() => {
  // @ts-expect-error -- remove the stub installed in beforeEach
  delete window.IntersectionObserver
})

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('Recipes page — themes', () => {
  describe('main page sampler', () => {
    it("shows each theme's two fullest lists, not every list", () => {
      renderPage()

      expect(region('Italian Recipes')).toBeInTheDocument()
      expect(region('Thai Recipes')).toBeInTheDocument()
      expect(region('Chicken Recipes')).toBeInTheDocument()
      expect(region('Beef Recipes')).toBeInTheDocument()

      expect(region('Korean Recipes')).not.toBeInTheDocument()
      expect(region('Pork Recipes')).not.toBeInTheDocument()
    })

    it('does not sample the source theme (its lists repeat the other themes)', () => {
      renderPage()
      // Pork is only reachable through Source here, and Source is not sampled
      expect(region('Pork Recipes')).not.toBeInTheDocument()
    })

    it('waits for the collections list (which seeds the catalog) before fetching themes', () => {
      vi.mocked(useCollections).mockReturnValue({ data: undefined, isLoading: true } as never)
      renderPage()
      expect(useThemes).toHaveBeenCalledWith({ enabled: false })
    })
  })

  describe('theme bar', () => {
    it('shows a dropdown for each theme that has values', () => {
      renderPage()
      const bar = screen.getByRole('navigation', { name: 'Recipe themes' })
      expect(within(bar).getByRole('button', { name: /Cuisine/ })).toBeInTheDocument()
      expect(within(bar).getByRole('button', { name: /Diet/ })).toBeInTheDocument()
      expect(within(bar).getByRole('button', { name: /Source/ })).toBeInTheDocument()
      expect(within(bar).queryByRole('button', { name: /Dish type/ })).not.toBeInTheDocument()
    })

    it('keeps Main ingredient behind Advanced', async () => {
      const user = userEvent.setup()
      renderPage()
      expect(screen.queryByRole('button', { name: /Main ingredient/ })).not.toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: /Advanced/ }))
      expect(screen.getByRole('button', { name: /Main ingredient/ })).toBeInTheDocument()
    })

    it('shows Advanced open while a Main ingredient filter is in use', () => {
      renderPage('/recipes?filter=ingredient:chicken')
      expect(screen.getByRole('button', { name: /Main ingredient: Chicken/ })).toBeInTheDocument()
    })

    it('lists values with their totals in the dropdown', async () => {
      const user = userEvent.setup()
      renderPage()
      await user.click(screen.getByRole('button', { name: /Cuisine/ }))

      const menu = screen.getByRole('menu', { name: 'Cuisine' })
      expect(within(menu).getByRole('menuitem', { name: 'See all cuisine' })).toBeInTheDocument()
      expect(within(menu).getByRole('menuitemradio', { name: /Italian\s*13/ })).toBeInTheDocument()
      // Korean has nothing loaded yet: listed without a count
      expect(within(menu).getByRole('menuitemradio', { name: 'Korean' })).toBeInTheDocument()
    })

    it('closes the dropdown on Escape', async () => {
      const user = userEvent.setup()
      renderPage()
      await user.click(screen.getByRole('button', { name: /Cuisine/ }))
      await user.keyboard('{Escape}')
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    })
  })

  describe('theme page ("See all")', () => {
    it("shows every list in the theme and none of the user's own rows", async () => {
      vi.mocked(useRecipeList).mockReturnValue({ data: [recipe('r1', ['italian'])], isLoading: false, isError: false, error: null } as never)
      const user = userEvent.setup()
      renderPage()
      await user.click(screen.getByRole('button', { name: /Cuisine/ }))
      await user.click(screen.getByRole('menuitem', { name: 'See all cuisine' }))

      expect(screen.getByRole('heading', { name: 'Cuisine.' })).toBeInTheDocument()
      // The user's Italian recipes and HelloFresh's Italian collection: two lists, two sources
      expect(region('Italian')).toBeInTheDocument()
      expect(region('Italian Recipes')).toBeInTheDocument()
      expect(region('Thai Recipes')).toBeInTheDocument()
      expect(region('Korean Recipes')).toBeInTheDocument()
      expect(region('Chicken Recipes')).not.toBeInTheDocument()
      expect(screen.queryByRole('heading', { name: 'Recently added.' })).not.toBeInTheDocument()
    })

    it("labels the user's list with its source", () => {
      vi.mocked(useRecipeList).mockReturnValue({ data: [recipe('r1', ['italian'])], isLoading: false, isError: false, error: null } as never)
      renderPage('/recipes?theme=cuisine')
      expect(region('Italian')).toHaveTextContent('1 recipe · Your recipes')
    })

    it('hides More HelloFresh collections off the main page', () => {
      renderPage('/recipes?theme=cuisine')
      expect(screen.queryByRole('button', { name: 'More HelloFresh collections' })).not.toBeInTheDocument()
    })
  })

  describe('theme filter', () => {
    it('keeps whole lists that are Italian or contain an Italian recipe, hides the rest', async () => {
      // Favorites contains an Italian recipe; Recently added and Quick meals do not
      vi.mocked(useRecipeList).mockImplementation((filters) =>
        ({
          data: (filters as { liked?: boolean } | undefined)?.liked
            ? [recipe('fav-1', ['italian']), recipe('fav-2', ['thai'])]
            : [recipe('other', ['mexican'])],
          isLoading: false,
          isError: false,
          error: null,
        }) as never
      )
      const user = userEvent.setup()
      renderPage()
      await user.click(screen.getByRole('button', { name: /Cuisine/ }))
      await user.click(screen.getByRole('menuitemradio', { name: /Italian/ }))

      expect(screen.getByRole('button', { name: /Cuisine: Italian/ })).toBeInTheDocument()

      // Favorites stays, untrimmed: both of its recipes, not just the Italian one
      const favorites = region('Your favorites')!
      expect(within(favorites).getByText('Recipe fav-1')).toBeInTheDocument()
      expect(within(favorites).getByText('Recipe fav-2')).toBeInTheDocument()
      expect(region('Recently added')).not.toBeInTheDocument()

      // The user's own Italian list and HelloFresh's, each separate
      expect(region('Italian')).toBeInTheDocument()
      expect(region('Italian Recipes')).toBeInTheDocument()
      expect(region('Thai Recipes')).not.toBeInTheDocument()
      expect(region('Chicken Recipes')).not.toBeInTheDocument()
    })

    it('Clear returns to the main page', async () => {
      const user = userEvent.setup()
      renderPage('/recipes?filter=cuisine:italian')
      expect(region('Chicken Recipes')).not.toBeInTheDocument()
      await user.click(screen.getByRole('button', { name: 'Clear' }))

      expect(screen.queryByRole('button', { name: /Cuisine: Italian/ })).not.toBeInTheDocument()
      expect(region('Chicken Recipes')).toBeInTheDocument()
    })

    it('a second theme’s value applies together with the first instead of replacing it', async () => {
      const user = userEvent.setup()
      renderPage('/recipes?filter=cuisine:italian')
      await user.click(screen.getByRole('button', { name: /^Diet/ }))
      await user.click(screen.getByRole('menuitemradio', { name: /Vegetarian/ }))

      expect(screen.getByRole('button', { name: /Cuisine: Italian/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Diet: Vegetarian/ })).toBeInTheDocument()
      // Both collections pass both filters (each contains the other's cards)
      expect(region('Italian Recipes')).toBeInTheDocument()
      expect(region('Vegetarian Recipes')).toBeInTheDocument()
      expect(region('Thai Recipes')).not.toBeInTheDocument()
    })

    it('picking the active value again clears just that filter', async () => {
      const user = userEvent.setup()
      renderPage('/recipes?filter=cuisine:italian&filter=diet:vegetarian')
      await user.click(screen.getByRole('button', { name: /Diet: Vegetarian/ }))
      await user.click(screen.getByRole('menuitemradio', { name: /Vegetarian/ }))

      expect(screen.queryByRole('button', { name: /Diet: Vegetarian/ })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Cuisine: Italian/ })).toBeInTheDocument()
    })

    it('filters apply on a theme page', () => {
      renderPage('/recipes?theme=cuisine&filter=diet:vegetarian')
      expect(screen.getByRole('heading', { name: 'Cuisine.' })).toBeInTheDocument()
      expect(region('Italian Recipes')).toBeInTheDocument()
      expect(region('Thai Recipes')).not.toBeInTheDocument()
      expect(region('Vegetarian Recipes')).not.toBeInTheDocument()
    })

    it('a source filter keeps that source’s collections', () => {
      renderPage('/recipes?filter=source:hellofresh')
      expect(region('Pork Recipes')).toBeInTheDocument()
      expect(region('Korean Recipes')).toBeInTheDocument()
    })
  })

  describe('lazy collection loading', () => {
    it('makes no /collections/{slug} requests before rows scroll into view', () => {
      renderPage()
      const calls = vi.mocked(useCollection).mock.calls
      expect(calls.length).toBeGreaterThan(0)
      calls.forEach((args) => expect((args[2] as { enabled?: boolean })?.enabled).toBe(false))
    })

    it('rows with stored cards pass fresh:false when triggered', async () => {
      renderPage('/recipes?filter=cuisine:thai')
      triggerAllObservers()

      await waitFor(() => {
        const inView = vi.mocked(useCollection).mock.calls.find((a) => (a[2] as RowQueryOptions | undefined)?.enabled === true)
        expect(inView).toBeDefined()
        expect((inView![2] as RowQueryOptions).fresh).toBe(false)
      })
    })

    it('never-fetched rows leave fresh to the default staleness check', async () => {
      renderPage('/recipes?filter=cuisine:korean')
      triggerAllObservers()

      await waitFor(() => {
        const inView = vi.mocked(useCollection).mock.calls.find((a) => (a[2] as RowQueryOptions | undefined)?.enabled === true)
        expect(inView).toBeDefined()
        expect((inView![2] as RowQueryOptions).fresh).toBeUndefined()
      })
    })
  })

  describe('"More collections" sheet', () => {
    it('opens with every catalog collection, themed or not', async () => {
      const user = userEvent.setup()
      renderPage()
      await user.click(screen.getByRole('button', { name: 'More HelloFresh collections' }))

      const dialog = screen.getByRole('dialog')
      expect(dialog).toHaveTextContent('Italian Recipes')
      expect(dialog).toHaveTextContent('Hall of Fame')
    })

    it('closes when the close button is clicked', async () => {
      const user = userEvent.setup()
      renderPage()
      await user.click(screen.getByRole('button', { name: 'More HelloFresh collections' }))
      await user.click(screen.getByRole('button', { name: 'Close' }))
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  describe('source byline', () => {
    it('names HelloFresh on each collection row rather than in a section header', () => {
      renderPage()
      expect(screen.queryByRole('heading', { name: 'From HelloFresh.' })).not.toBeInTheDocument()
      expect(region('Chicken Recipes')).toHaveTextContent('30 recipes · HelloFresh')
    })
  })

  describe('cold start', () => {
    it('shows loading text while collections list is fetching', () => {
      vi.mocked(useCollections).mockReturnValue({ data: undefined, isLoading: true } as never)
      vi.mocked(useThemes).mockReturnValue({ data: undefined } as never)
      renderPage()
      expect(screen.getByText('Loading HelloFresh collections…')).toBeInTheDocument()
    })
  })
})
