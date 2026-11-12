/**
 * Recipes page — HelloFresh section tests (#545)
 *
 * The existing Recipes suite lives at __tests__/Recipes.test.tsx and covers the
 * library carousel/grid behaviour. This file covers the new "From HelloFresh"
 * section: collection row mounting, lazy loading AC, More Collections sheet.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import Recipes from './Recipes'
import { useRecipeList } from '../api'
import { useCollections, useCollection } from '../api/hooks/useCatalog'
import type { CollectionSummary } from '../api/types'

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

// ── IntersectionObserver stub ──────────────────────────────────────────────────

type ObserverEntry = { element: Element; callback: IntersectionObserverCallback }
const observers: ObserverEntry[] = []

class MockIntersectionObserver {
  private cb: IntersectionObserverCallback
  constructor(cb: IntersectionObserverCallback, _opts?: IntersectionObserverInit) {
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

// ── Helpers ────────────────────────────────────────────────────────────────────

const makeCollection = (slug: string, name: string, card_count: number): CollectionSummary => ({
  slug,
  name,
  card_count,
  last_fetched_at: null,
})

const renderPage = () =>
  render(
    <BrowserRouter>
      <Recipes />
    </BrowserRouter>
  )

// ── Setup ──────────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  observers.length = 0
  // @ts-expect-error
  window.IntersectionObserver = MockIntersectionObserver

  vi.mocked(useRecipeList).mockReturnValue({
    data: [],
    isLoading: false,
    isError: false,
    error: null,
  } as any)

  vi.mocked(useCollection).mockReturnValue({
    data: undefined,
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
  } as any)
})

afterEach(() => {
  // @ts-expect-error
  delete window.IntersectionObserver
})

// ── Tests ──────────────────────────────────────────────────────────────────────

describe('Recipes page — HelloFresh section', () => {
  describe('collection row count', () => {
    it('mounts at most 6 CollectionRow components when 8 collections are returned', () => {
      const collections = Array.from({ length: 8 }, (_, i) =>
        makeCollection(`col-${i}`, `Collection ${i}`, i * 2)
      )
      vi.mocked(useCollections).mockReturnValue({
        data: collections,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderPage()

      // 6 sections are rendered (each has a region aria-label matching the collection name)
      // The first 6 from the sorted list should be present, the 7th and 8th should not
      const sorted = [...collections].sort((a, b) => b.card_count - a.card_count)
      const shown = sorted.slice(0, 6)
      const hidden = sorted.slice(6)

      shown.forEach((c) => {
        expect(screen.getByRole('region', { name: c.name })).toBeInTheDocument()
      })
      hidden.forEach((c) => {
        expect(screen.queryByRole('region', { name: c.name })).not.toBeInTheDocument()
      })
    })
  })

  describe('zero detail requests before any row is in view', () => {
    it('makes no /collections/{slug} requests before rows scroll into view', () => {
      const collections = Array.from({ length: 6 }, (_, i) =>
        makeCollection(`slug-${i}`, `Col ${i}`, i)
      )
      vi.mocked(useCollections).mockReturnValue({
        data: collections,
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderPage()

      // Every useCollection call should have enabled:false
      const calls = vi.mocked(useCollection).mock.calls
      calls.forEach((args) => {
        const opts = args[2] as { enabled?: boolean }
        expect(opts?.enabled).toBe(false)
      })
    })
  })

  describe('lazy loading — fresh param', () => {
    it('rows with card_count > 0 pass fresh:false when triggered', async () => {
      const col = makeCollection('tasty-veg', 'Tasty Veg', 4)
      vi.mocked(useCollections).mockReturnValue({
        data: [col],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderPage()
      triggerAllObservers()

      await waitFor(() => {
        const calls = vi.mocked(useCollection).mock.calls
        const inViewCall = calls.find((args) => (args[2] as any)?.enabled === true)
        expect(inViewCall).toBeDefined()
        expect((inViewCall![2] as any).fresh).toBe(false)
      })
    })

    it('rows with card_count === 0 do not pass fresh when triggered', async () => {
      const col = makeCollection('empty-col', 'Empty Col', 0)
      vi.mocked(useCollections).mockReturnValue({
        data: [col],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderPage()
      triggerAllObservers()

      await waitFor(() => {
        const calls = vi.mocked(useCollection).mock.calls
        const inViewCall = calls.find((args) => (args[2] as any)?.enabled === true)
        expect(inViewCall).toBeDefined()
        expect((inViewCall![2] as any).fresh).toBeUndefined()
      })
    })
  })

  describe('"More collections" sheet', () => {
    const makeCollections = (n: number) =>
      Array.from({ length: n }, (_, i) => makeCollection(`c${i}`, `Coll ${i}`, i))

    beforeEach(() => {
      vi.mocked(useCollections).mockReturnValue({
        data: makeCollections(8),
        isLoading: false,
        isError: false,
        error: null,
      } as any)
    })

    it('opens the MoreCollectionsSheet when "More collections…" is clicked', async () => {
      const user = userEvent.setup()
      renderPage()

      const btn = screen.getByRole('button', { name: 'More collections' })
      await user.click(btn)

      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('sheet lists all collections', async () => {
      const user = userEvent.setup()
      renderPage()

      await user.click(screen.getByRole('button', { name: 'More collections' }))

      // All 8 collection names should appear in the sheet
      const dialog = screen.getByRole('dialog')
      for (let i = 0; i < 8; i++) {
        expect(dialog).toHaveTextContent(`Coll ${i}`)
      }
    })

    it('sheet filters collections by typed text', async () => {
      const user = userEvent.setup()
      renderPage()

      await user.click(screen.getByRole('button', { name: 'More collections' }))

      const filterInput = screen.getByRole('searchbox', { name: 'Filter collections' })
      await user.type(filterInput, 'Coll 3')

      await waitFor(() => {
        const dialog = screen.getByRole('dialog')
        expect(dialog).toHaveTextContent('Coll 3')
        // Other collections should not be visible
        expect(dialog).not.toHaveTextContent('Coll 1')
        expect(dialog).not.toHaveTextContent('Coll 7')
      })
    })

    it('sheet closes when the close button is clicked', async () => {
      const user = userEvent.setup()
      renderPage()

      await user.click(screen.getByRole('button', { name: 'More collections' }))
      expect(screen.getByRole('dialog')).toBeInTheDocument()

      await user.click(screen.getByRole('button', { name: 'Close' }))
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  describe('section header', () => {
    it('renders "From HelloFresh." heading', () => {
      vi.mocked(useCollections).mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderPage()
      expect(screen.getByRole('heading', { name: 'From HelloFresh.' })).toBeInTheDocument()
    })
  })

  describe('cold start', () => {
    it('shows loading text while collections list is fetching', () => {
      vi.mocked(useCollections).mockReturnValue({
        data: undefined,
        isLoading: true,
        isError: false,
        error: null,
      } as any)

      renderPage()
      expect(screen.getByText('Loading collections…')).toBeInTheDocument()
    })
  })

  describe('existing library sections preserved', () => {
    it('still shows existing library section headings alongside HelloFresh section', () => {
      vi.mocked(useCollections).mockReturnValue({
        data: [makeCollection('summer', 'Summer Meals', 3)],
        isLoading: false,
        isError: false,
        error: null,
      } as any)

      renderPage()

      expect(screen.getByRole('heading', { name: 'Your favorites.' })).toBeInTheDocument()
      expect(screen.getByRole('heading', { name: 'From HelloFresh.' })).toBeInTheDocument()
    })
  })
})
