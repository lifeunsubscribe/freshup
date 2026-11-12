/**
 * Collection page tests (#546)
 *
 * Covers the five acceptance criteria:
 * AC1 — parent cards + header count render from mocked CollectionDetail
 * AC2 — no child request until sentinel; one-at-a-time walk; second waits for first to settle
 * AC3 — caught-up tail after last child; 429 → could-not, no further requests
 * AC4 — "Saved only" and "Under 30 min" chips filter client-side
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import Collection from './Collection'
import { useCollection } from '../api/hooks/useCatalog'
import type { CollectionDetail, CardResponse } from '../api/types'

// ── API mocks ──────────────────────────────────────────────────────────────────

vi.mock('../api/hooks/useCatalog', () => ({
  useCollection: vi.fn(),
  useCollections: vi.fn(() => ({ data: [], isLoading: false, isError: false, error: null })),
  useOpenCard: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    reset: vi.fn(),
  })),
}))

vi.mock('../contexts/AuthContext', () => ({
  useAuth: () => ({ currentUser: { id: 'user-1', name: 'Test' } }),
}))

// ── IntersectionObserver stub ──────────────────────────────────────────────────

type ObserverEntry = { callback: IntersectionObserverCallback; active: boolean }
const observers: ObserverEntry[] = []

class MockIntersectionObserver {
  private cb: IntersectionObserverCallback
  private idx = -1
  constructor(cb: IntersectionObserverCallback) { this.cb = cb }
  observe(_el: Element) {
    this.idx = observers.length
    observers.push({ callback: this.cb, active: true })
  }
  disconnect() {
    if (this.idx >= 0 && observers[this.idx]) {
      observers[this.idx].active = false
    }
  }
  unobserve() {}
}

function triggerObserver() {
  act(() => {
    observers.forEach(({ callback, active }) => {
      if (active) {
        callback([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver)
      }
    })
  })
}

// ── Fixtures ───────────────────────────────────────────────────────────────────

function makeCard(id: string, overrides: Partial<CardResponse> = {}): CardResponse {
  return {
    id,
    name: `Card ${id}`,
    headline: null,
    image_url: null,
    prep_time_minutes: 20,
    rating: null,
    rating_count: null,
    recipe_url: `https://example.com/${id}`,
    recipe_id: null,
    is_persisted: false,
    ...overrides,
  }
}

function makeDetail(slug: string, overrides: Partial<CollectionDetail> = {}): CollectionDetail {
  return {
    slug,
    name: `Collection ${slug}`,
    source_type: 'hellofresh_web',
    last_fetched_at: null,
    children: [],
    cards: [],
    fetch_error: null,
    ...overrides,
  }
}

const idle = { isLoading: false, isFetching: false, isError: false, error: null }

// ── Render helper ──────────────────────────────────────────────────────────────

function renderCollection(slug = 'quick-meals') {
  return render(
    <MemoryRouter initialEntries={[`/browse/hellofresh/${slug}`]}>
      <Routes>
        <Route path="/browse/hellofresh/:slug" element={<Collection />} />
        <Route path="/recipes" element={<div>recipes page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

// ── Setup / teardown ──────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks()
  observers.length = 0
  // @ts-expect-error
  window.IntersectionObserver = MockIntersectionObserver

  // Default: loading state for the parent
  vi.mocked(useCollection).mockReturnValue({
    data: undefined,
    ...idle,
    isLoading: true,
  } as any)
})

afterEach(() => {
  // @ts-expect-error
  delete window.IntersectionObserver
})

// ── AC1: parent cards + header count ──────────────────────────────────────────

describe('AC1 — parent cards and header count', () => {
  it('renders parent cards in a 2-column grid and shows the recipe count', async () => {
    const parentCards = [
      makeCard('c1', { name: 'Lemon Pasta' }),
      makeCard('c2', { name: 'Butter Chicken' }),
      makeCard('c3', { name: 'Veggie Stir Fry' }),
    ]
    const detail = makeDetail('quick-meals', { cards: parentCards, children: [] })

    vi.mocked(useCollection).mockReturnValue({ data: detail, ...idle } as any)

    renderCollection()

    await waitFor(() => {
      expect(screen.getByText('Lemon Pasta')).toBeInTheDocument()
      expect(screen.getByText('Butter Chicken')).toBeInTheDocument()
      expect(screen.getByText('Veggie Stir Fry')).toBeInTheDocument()
    })

    expect(screen.getByText('3 recipes')).toBeInTheDocument()
  })

  it('shows the collection name with an olive period in the heading', async () => {
    const detail = makeDetail('quick-meals', { name: 'Quick Meals', cards: [], children: [] })
    vi.mocked(useCollection).mockReturnValue({ data: detail, ...idle } as any)
    renderCollection()
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Quick Meals.')
    })
  })

  it('shows caught-up tail immediately when collection has no children', async () => {
    const detail = makeDetail('quick-meals', { cards: [makeCard('c1')], children: [] })
    vi.mocked(useCollection).mockReturnValue({ data: detail, ...idle } as any)
    renderCollection()
    await waitFor(() => {
      expect(screen.getByText(/that’s everything in this collection/i)).toBeInTheDocument()
    })
  })

  it('shows not-found state for a 404 from the API', async () => {
    vi.mocked(useCollection).mockReturnValue({
      data: undefined,
      ...idle,
      isError: true,
      error: { status: 404, message: 'Not found' },
    } as any)
    renderCollection()
    await waitFor(() => {
      expect(screen.getByText(/recipe collection not found/i)).toBeInTheDocument()
    })
  })
})

// ── AC2: sentinel walk, one-at-a-time ─────────────────────────────────────────

describe('AC2 — sentinel walk and one-at-a-time loading', () => {
  const parentSlug = 'quick-meals'
  const childASlug = 'child-a'
  const childBSlug = 'child-b'

  const parentDetail = makeDetail(parentSlug, {
    name: 'Quick Meals',
    cards: [makeCard('p1'), makeCard('p2')],
    children: [
      { slug: childASlug, name: 'Child A', card_count: 2, last_fetched_at: null },
      { slug: childBSlug, name: 'Child B', card_count: 2, last_fetched_at: null },
    ],
  })

  const childADetail = makeDetail(childASlug, {
    cards: [makeCard('a1', { name: 'Child A Card 1' }), makeCard('a2', { name: 'Child A Card 2' })],
  })

  const childBDetail = makeDetail(childBSlug, {
    cards: [makeCard('b1', { name: 'Child B Card 1' }), makeCard('b2', { name: 'Child B Card 2' })],
  })

  beforeEach(() => {
    vi.mocked(useCollection).mockImplementation((_source, slug, opts) => {
      const enabled = (opts as { enabled?: boolean })?.enabled !== false

      if (slug === parentSlug) {
        return { data: parentDetail, ...idle } as any
      }
      if (!enabled) {
        return { data: undefined, ...idle } as any
      }
      if (slug === childASlug) {
        return { data: childADetail, ...idle } as any
      }
      if (slug === childBSlug) {
        return { data: childBDetail, ...idle } as any
      }
      return { data: undefined, ...idle } as any
    })
  })

  it('makes no child request until sentinel fires', () => {
    renderCollection()

    // All calls for child slugs should have enabled: false
    const calls = vi.mocked(useCollection).mock.calls
    const childCalls = calls.filter((args) => args[1] !== parentSlug)
    childCalls.forEach((args) => {
      expect((args[2] as { enabled?: boolean })?.enabled).toBe(false)
    })
  })

  it('enables child-a after first sentinel fire, leaves child-b disabled', async () => {
    renderCollection()

    // Before sentinel: neither child enabled
    const before = vi.mocked(useCollection).mock.calls.filter((a) => a[1] === childBSlug)
    before.forEach((args) => {
      expect((args[2] as { enabled?: boolean })?.enabled).toBe(false)
    })

    // Fire sentinel → cursor becomes 0
    triggerObserver()

    await waitFor(() => {
      // child-a enabled call should exist
      const calls = vi.mocked(useCollection).mock.calls
      const aEnabled = calls.some((a) => a[1] === childASlug && (a[2] as any)?.enabled === true)
      expect(aEnabled).toBe(true)
    })

    // child-b should still not be enabled (cursor=0, settled={0} not yet observed by test)
    // We haven't fired the sentinel a second time, so cursor is still 0 at the test's last assertion.
    // child-b would be enabled = 1 <= 0 = false
    const afterFirst = vi.mocked(useCollection).mock.calls.filter(
      (a) => a[1] === childBSlug && (a[2] as any)?.enabled === true
    )
    expect(afterFirst).toHaveLength(0)
  })

  it('renders child-a cards with isNew marker after first sentinel', async () => {
    renderCollection()
    triggerObserver()

    await waitFor(() => {
      expect(screen.getByText('Child A Card 1')).toBeInTheDocument()
      expect(screen.getByText('Child A Card 2')).toBeInTheDocument()
    })

    // CatalogCard renders "New" for isNew=true
    const newMarkers = screen.getAllByText('New')
    expect(newMarkers.length).toBeGreaterThanOrEqual(2)
  })

  it('enables child-b only after second sentinel fire (once child-a has settled)', async () => {
    renderCollection()

    // Fire sentinel once → cursor=0, child-a settles immediately (mock returns data)
    triggerObserver()

    await waitFor(() => {
      expect(screen.getByText('Child A Card 1')).toBeInTheDocument()
    })

    // Fire sentinel again → cursor=1 (settled.has(0) is now true)
    triggerObserver()

    await waitFor(() => {
      const calls = vi.mocked(useCollection).mock.calls
      const bEnabled = calls.some((a) => a[1] === childBSlug && (a[2] as any)?.enabled === true)
      expect(bEnabled).toBe(true)
    })

    await waitFor(() => {
      expect(screen.getByText('Child B Card 1')).toBeInTheDocument()
    })
  })
})

// ── AC3: tail states — caught-up and could-not ────────────────────────────────

describe('AC3 — tail states', () => {
  const parentSlug = 'quick-meals'
  const childASlug = 'child-a'

  it('shows caught-up text after the last child settles', async () => {
    const parentDetail = makeDetail(parentSlug, {
      cards: [makeCard('p1')],
      children: [
        { slug: childASlug, name: 'Child A', card_count: 1, last_fetched_at: null },
      ],
    })
    const childADetail = makeDetail(childASlug, {
      cards: [makeCard('a1', { name: 'Child A Card' })],
    })

    vi.mocked(useCollection).mockImplementation((_source, slug, opts) => {
      const enabled = (opts as { enabled?: boolean })?.enabled !== false
      if (slug === parentSlug) return { data: parentDetail, ...idle } as any
      if (!enabled) return { data: undefined, ...idle } as any
      if (slug === childASlug) return { data: childADetail, ...idle } as any
      return { data: undefined, ...idle } as any
    })

    renderCollection()
    triggerObserver()

    await waitFor(() => {
      expect(screen.getByText(/that’s everything in this collection/i)).toBeInTheDocument()
    })
  })

  it('shows could-not-bring-in-more and stops walking on a 429 response', async () => {
    const parentDetail = makeDetail(parentSlug, {
      cards: [makeCard('p1')],
      children: [
        { slug: childASlug, name: 'Child A', card_count: 0, last_fetched_at: null },
        { slug: 'child-b', name: 'Child B', card_count: 0, last_fetched_at: null },
      ],
    })

    vi.mocked(useCollection).mockImplementation((_source, slug, opts) => {
      const enabled = (opts as { enabled?: boolean })?.enabled !== false
      if (slug === parentSlug) return { data: parentDetail, ...idle } as any
      if (!enabled) return { data: undefined, ...idle } as any
      if (slug === childASlug) {
        return {
          data: undefined,
          isLoading: false,
          isFetching: false,
          isError: true,
          error: { status: 429, message: 'Too Many Requests' },
        } as any
      }
      // child-b should never be enabled
      return { data: undefined, ...idle } as any
    })

    renderCollection()
    triggerObserver()

    await waitFor(() => {
      expect(
        screen.getByText(/could not bring in more right now/i)
      ).toBeInTheDocument()
    })

    // child-b should never have been enabled
    const bEnabledCalls = vi.mocked(useCollection).mock.calls.filter(
      (a) => a[1] === 'child-b' && (a[2] as any)?.enabled === true
    )
    expect(bEnabledCalls).toHaveLength(0)
  })

  it('shows could-not when child has fetch_error and no cards', async () => {
    const parentDetail = makeDetail(parentSlug, {
      cards: [makeCard('p1')],
      children: [{ slug: childASlug, name: 'Child A', card_count: 0, last_fetched_at: null }],
    })
    const failedChild = makeDetail(childASlug, {
      cards: [],
      fetch_error: 'Scrape failed',
    })

    vi.mocked(useCollection).mockImplementation((_source, slug, opts) => {
      const enabled = (opts as { enabled?: boolean })?.enabled !== false
      if (slug === parentSlug) return { data: parentDetail, ...idle } as any
      if (!enabled) return { data: undefined, ...idle } as any
      if (slug === childASlug) return { data: failedChild, ...idle } as any
      return { data: undefined, ...idle } as any
    })

    renderCollection()
    triggerObserver()

    await waitFor(() => {
      expect(screen.getByText(/could not bring in more right now/i)).toBeInTheDocument()
    })
  })
})

// ── Regression 1: settled children survive a later sibling failure ────────────

describe('Regression — settled child content survives a later sibling failure', () => {
  const parentSlug = 'quick-meals'
  const childASlug = 'child-a'

  it('leaves child-a cards visible when child-b fails with 429', async () => {
    const parentDetail = makeDetail(parentSlug, {
      cards: [],
      children: [
        { slug: childASlug, name: 'Child A', card_count: 1, last_fetched_at: null },
        { slug: 'child-b', name: 'Child B', card_count: 0, last_fetched_at: null },
      ],
    })
    const childADetail = makeDetail(childASlug, {
      cards: [makeCard('a1', { name: 'Child A Card' })],
    })

    vi.mocked(useCollection).mockImplementation((_source, slug, opts) => {
      const enabled = (opts as { enabled?: boolean })?.enabled !== false
      if (slug === parentSlug) return { data: parentDetail, ...idle } as any
      if (!enabled) return { data: undefined, ...idle } as any
      if (slug === childASlug) return { data: childADetail, ...idle } as any
      if (slug === 'child-b') {
        return {
          data: undefined,
          isLoading: false,
          isFetching: false,
          isError: true,
          error: { status: 429, message: 'Too Many Requests' },
        } as any
      }
      return { data: undefined, ...idle } as any
    })

    renderCollection()
    triggerObserver() // cursor=0 → child-a settles

    await waitFor(() => expect(screen.getByText('Child A Card')).toBeInTheDocument())

    triggerObserver() // cursor=1 → child-b fails

    await waitFor(() => {
      expect(screen.getByText(/could not bring in more right now/i)).toBeInTheDocument()
    })

    // Child A content must still be in the DOM after the failure
    expect(screen.getByText('Child A Card')).toBeInTheDocument()
  })
})

// ── Regression 2: slug navigation resets walk state ───────────────────────────

describe('Regression — slug change resets walk state', () => {
  it('shows fresh state when re-rendered with a new slug key', async () => {
    const detailA = makeDetail('collection-a', {
      cards: [],
      children: [{ slug: 'ca-child', name: 'Child A', card_count: 1, last_fetched_at: null }],
    })
    const detailB = makeDetail('collection-b', { cards: [makeCard('b1')], children: [] })
    const caChildDetail = makeDetail('ca-child', {
      cards: [makeCard('ca1', { name: 'CA Child Card' })],
    })

    vi.mocked(useCollection).mockImplementation((_source, slug, opts) => {
      const enabled = (opts as { enabled?: boolean })?.enabled !== false
      if (slug === 'collection-a') return { data: detailA, ...idle } as any
      if (slug === 'collection-b') return { data: detailB, ...idle } as any
      if (slug === 'ca-child' && enabled) return { data: caChildDetail, ...idle } as any
      return { data: undefined, ...idle } as any
    })

    // Render collection-a and advance the walk
    const { unmount } = render(
      <MemoryRouter initialEntries={['/browse/hellofresh/collection-a']}>
        <Routes>
          <Route path="/browse/hellofresh/:slug" element={<Collection key="collection-a" />} />
          <Route path="/recipes" element={<div>recipes page</div>} />
        </Routes>
      </MemoryRouter>
    )
    triggerObserver()
    await waitFor(() => expect(screen.getByText('CA Child Card')).toBeInTheDocument())

    // Navigate to collection-b: unmount the old tree and mount a fresh one so the
    // new MemoryRouter's initialEntries actually take effect (rerender keeps the old
    // router's location; unmount+render gives a genuinely fresh component tree).
    observers.length = 0
    unmount()
    render(
      <MemoryRouter initialEntries={['/browse/hellofresh/collection-b']}>
        <Routes>
          <Route path="/browse/hellofresh/:slug" element={<Collection key="collection-b" />} />
          <Route path="/recipes" element={<div>recipes page</div>} />
        </Routes>
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Collection collection-b.')
    })
    // Stale child content from collection-a must not appear
    expect(screen.queryByText('CA Child Card')).not.toBeInTheDocument()
    // collection-b has no children → caught-up tail shows immediately
    expect(screen.getByText(/that’s everything in this collection/i)).toBeInTheDocument()
  })
})

// ── Regression 3: 0-card child does not stall the walk ────────────────────────

describe('Regression — 0-card child advances the walk', () => {
  it('walks past a 0-card child when sentinel stays in viewport', async () => {
    const parentSlug = 'quick-meals'
    const parentDetail = makeDetail(parentSlug, {
      cards: [],
      children: [
        { slug: 'child-empty', name: 'Child Empty', card_count: 0, last_fetched_at: null },
        { slug: 'child-full', name: 'Child Full', card_count: 1, last_fetched_at: null },
      ],
    })
    const emptyChild = makeDetail('child-empty', { cards: [], fetch_error: null })
    const fullChildDetail = makeDetail('child-full', {
      cards: [makeCard('cf1', { name: 'Full Child Card' })],
    })

    vi.mocked(useCollection).mockImplementation((_source, slug, opts) => {
      const enabled = (opts as { enabled?: boolean })?.enabled !== false
      if (slug === parentSlug) return { data: parentDetail, ...idle } as any
      if (!enabled) return { data: undefined, ...idle } as any
      if (slug === 'child-empty') return { data: emptyChild, ...idle } as any
      if (slug === 'child-full') return { data: fullChildDetail, ...idle } as any
      return { data: undefined, ...idle } as any
    })

    renderCollection()
    triggerObserver() // cursor=0 → child-empty loads and settles with 0 cards; settledSet.size
                      // dep triggers re-subscribe (new observer registered in observers[])
    triggerObserver() // new observer fires → cursor=1 → child-full loads

    await waitFor(() => {
      expect(screen.getByText('Full Child Card')).toBeInTheDocument()
    })
  })
})

// ── Regression 4: non-404 errors show the correct error view ──────────────────

describe('Regression — non-404 error shows correct error view', () => {
  it('shows "could not load" for a 500 error, not "not found"', async () => {
    vi.mocked(useCollection).mockReturnValue({
      data: undefined,
      ...idle,
      isError: true,
      error: { status: 500, message: 'Internal Server Error' },
    } as any)

    renderCollection()

    await waitFor(() => {
      expect(screen.getByText(/could not load this collection right now/i)).toBeInTheDocument()
    })
    expect(screen.queryByText(/recipe collection not found/i)).not.toBeInTheDocument()
  })
})

// ── AC4: client-side chips ─────────────────────────────────────────────────────

describe('AC4 — Saved only and Under 30 min filters', () => {
  const parentDetail = makeDetail('quick-meals', {
    cards: [
      makeCard('saved-fast', { name: 'Saved Fast', is_persisted: true, prep_time_minutes: 20 }),
      makeCard('saved-slow', { name: 'Saved Slow', is_persisted: true, prep_time_minutes: 45 }),
      makeCard('unsaved-fast', { name: 'Unsaved Fast', is_persisted: false, prep_time_minutes: 15 }),
      makeCard('unsaved-slow', { name: 'Unsaved Slow', is_persisted: false, prep_time_minutes: 60 }),
    ],
    children: [],
  })

  beforeEach(() => {
    vi.mocked(useCollection).mockReturnValue({ data: parentDetail, ...idle } as any)
  })

  it('shows all cards when no filter is active', async () => {
    renderCollection()
    await waitFor(() => {
      expect(screen.getByText('Saved Fast')).toBeInTheDocument()
      expect(screen.getByText('Saved Slow')).toBeInTheDocument()
      expect(screen.getByText('Unsaved Fast')).toBeInTheDocument()
      expect(screen.getByText('Unsaved Slow')).toBeInTheDocument()
    })
  })

  it('"Saved only" hides cards where is_persisted is false', async () => {
    const user = userEvent.setup()
    renderCollection()

    await waitFor(() => expect(screen.getByText('Saved Fast')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /saved only/i }))

    await waitFor(() => {
      expect(screen.getByText('Saved Fast')).toBeInTheDocument()
      expect(screen.getByText('Saved Slow')).toBeInTheDocument()
      expect(screen.queryByText('Unsaved Fast')).not.toBeInTheDocument()
      expect(screen.queryByText('Unsaved Slow')).not.toBeInTheDocument()
    })
  })

  it('"Under 30 min" hides cards with prep_time_minutes > 30 or null', async () => {
    const user = userEvent.setup()
    renderCollection()

    await waitFor(() => expect(screen.getByText('Saved Fast')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /under 30 min/i }))

    await waitFor(() => {
      expect(screen.getByText('Saved Fast')).toBeInTheDocument()
      expect(screen.getByText('Unsaved Fast')).toBeInTheDocument()
      expect(screen.queryByText('Saved Slow')).not.toBeInTheDocument()
      expect(screen.queryByText('Unsaved Slow')).not.toBeInTheDocument()
    })
  })

  it('both chips can be active together (AND logic)', async () => {
    const user = userEvent.setup()
    renderCollection()

    await waitFor(() => expect(screen.getByText('Saved Fast')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: /saved only/i }))
    await user.click(screen.getByRole('button', { name: /under 30 min/i }))

    await waitFor(() => {
      // Only "Saved Fast" matches both: is_persisted=true AND prep_time=20
      expect(screen.getByText('Saved Fast')).toBeInTheDocument()
      expect(screen.queryByText('Saved Slow')).not.toBeInTheDocument()
      expect(screen.queryByText('Unsaved Fast')).not.toBeInTheDocument()
      expect(screen.queryByText('Unsaved Slow')).not.toBeInTheDocument()
    })
  })
})
