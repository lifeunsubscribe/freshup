import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import CollectionRow from './CollectionRow'
import { useCollection } from '../../api/hooks/useCatalog'
import type { CollectionSummary, CollectionDetail, CardResponse } from '../../api/types'

vi.mock('../../api/hooks/useCatalog', () => ({
  useCollection: vi.fn(),
  useOpenCard: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
    reset: vi.fn(),
  })),
}))

// IntersectionObserver is not available in jsdom — provide a controllable stub.
let observerCallback: IntersectionObserverCallback | null = null
class MockIntersectionObserver {
  constructor(cb: IntersectionObserverCallback, _opts?: IntersectionObserverInit) {
    observerCallback = cb
  }
  observe(_el: Element) {}
  disconnect() {
    observerCallback = null
  }
  unobserve() {}
}

beforeEach(() => {
  vi.clearAllMocks()
  observerCallback = null
  // @ts-expect-error - jsdom does not define IntersectionObserver
  window.IntersectionObserver = MockIntersectionObserver
})

afterEach(() => {
  // @ts-expect-error
  delete window.IntersectionObserver
})

const baseCollection: CollectionSummary = {
  slug: 'quick-dinners',
  name: 'Quick Dinners',
  card_count: 5,
  last_fetched_at: '2026-11-01T00:00:00Z',
}

const makeCard = (id: string, overrides: Partial<CardResponse> = {}): CardResponse => ({
  id,
  name: `Recipe ${id}`,
  headline: null,
  image_url: null,
  prep_time_minutes: null,
  rating: null,
  rating_count: null,
  recipe_url: `https://hellofresh.com/${id}`,
  recipe_id: null,
  is_persisted: false,
  ...overrides,
})

function setCollectionState(overrides: {
  data?: CollectionDetail | undefined
  isLoading?: boolean
  isFetching?: boolean
  enabled?: boolean
}) {
  vi.mocked(useCollection).mockReturnValue({
    data: overrides.data,
    isLoading: overrides.isLoading ?? false,
    isFetching: overrides.isFetching ?? false,
    isError: false,
    error: null,
  } as unknown as ReturnType<typeof useCollection>)
}

function triggerInView() {
  act(() => {
    observerCallback?.([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver)
  })
}

const renderRow = (collection: CollectionSummary = baseCollection) =>
  render(
    <BrowserRouter>
      <CollectionRow collection={collection} />
    </BrowserRouter>
  )

describe('CollectionRow', () => {
  describe('lazy loading — before inView', () => {
    it('renders the section with collection name', () => {
      setCollectionState({ isLoading: false })
      renderRow()
      // The row should render the heading even before in-view
      expect(screen.getByRole('region', { name: 'Quick Dinners' })).toBeInTheDocument()
    })

    it('does not call useCollection with enabled:true before inView', () => {
      setCollectionState({ isLoading: false })
      renderRow()
      // enabled should be false before in-view
      expect(useCollection).toHaveBeenCalledWith(
        'hellofresh_web',
        'quick-dinners',
        expect.objectContaining({ enabled: false })
      )
    })

    it('shows the height-reservation placeholder before inView', () => {
      setCollectionState({ isLoading: false })
      const { container } = renderRow()
      expect(container.querySelector('.h-48')).toBeInTheDocument()
    })
  })

  describe('lazy loading — after inView triggered', () => {
    it('calls useCollection with enabled:true once the observer fires', () => {
      setCollectionState({ isLoading: true })
      renderRow()
      triggerInView()
      expect(useCollection).toHaveBeenCalledWith(
        'hellofresh_web',
        'quick-dinners',
        expect.objectContaining({ enabled: true })
      )
    })

    it('rows with card_count > 0 pass fresh:false', () => {
      setCollectionState({ isLoading: true })
      renderRow({ ...baseCollection, card_count: 3 })
      triggerInView()
      expect(useCollection).toHaveBeenCalledWith(
        'hellofresh_web',
        'quick-dinners',
        expect.objectContaining({ fresh: false })
      )
    })

    it('rows with card_count === 0 do not pass fresh param', () => {
      setCollectionState({ isLoading: true })
      renderRow({ ...baseCollection, card_count: 0 })
      triggerInView()
      // fresh should be undefined (not passed)
      expect(useCollection).toHaveBeenCalledWith(
        'hellofresh_web',
        'quick-dinners',
        expect.objectContaining({ fresh: undefined })
      )
    })
  })

  describe('body states', () => {
    it('shows loading text when inView and fetching', () => {
      setCollectionState({ isLoading: true, isFetching: true })
      renderRow()
      triggerInView()
      expect(screen.getByText('Loading…')).toBeInTheDocument()
    })

    it('shows up to 10 cards when loaded', () => {
      const cards = Array.from({ length: 12 }, (_, i) => makeCard(`card-${i}`))
      setCollectionState({
        data: {
          slug: 'quick-dinners',
          name: 'Quick Dinners',
          source_type: 'hellofresh_web',
          last_fetched_at: null,
          children: [],
          cards,
          fetch_error: null,
        },
      })
      renderRow()
      triggerInView()
      // Max 10 cards rendered
      const listItems = screen.getAllByRole('listitem')
      expect(listItems).toHaveLength(10)
    })

    it('shows "Nothing here yet." when cards is empty and no error', () => {
      setCollectionState({
        data: {
          slug: 'quick-dinners',
          name: 'Quick Dinners',
          source_type: 'hellofresh_web',
          last_fetched_at: null,
          children: [],
          cards: [],
          fetch_error: null,
        },
      })
      renderRow()
      triggerInView()
      expect(screen.getByText('Nothing here yet.')).toBeInTheDocument()
    })

    it('shows the error note with stored cards on fetch_error', () => {
      const cards = [makeCard('card-1'), makeCard('card-2')]
      setCollectionState({
        data: {
          slug: 'quick-dinners',
          name: 'Quick Dinners',
          source_type: 'hellofresh_web',
          last_fetched_at: null,
          children: [],
          cards,
          fetch_error: 'upstream timeout',
        },
      })
      renderRow()
      triggerInView()
      expect(screen.getAllByRole('listitem')).toHaveLength(2)
      expect(screen.getByText('Could not bring in more right now.')).toBeInTheDocument()
    })

    it('shows only the error note when fetch_error and no cards', () => {
      setCollectionState({
        data: {
          slug: 'quick-dinners',
          name: 'Quick Dinners',
          source_type: 'hellofresh_web',
          last_fetched_at: null,
          children: [],
          cards: [],
          fetch_error: 'upstream timeout',
        },
      })
      renderRow()
      triggerInView()
      expect(screen.queryByRole('list')).not.toBeInTheDocument()
      expect(screen.getByText('Could not bring in more right now.')).toBeInTheDocument()
    })
  })

  describe('"See all" link', () => {
    it('links to /browse/hellofresh/{slug}', () => {
      setCollectionState({ isLoading: false })
      renderRow()
      const link = screen.getByRole('link', { name: /see all quick dinners/i })
      expect(link).toHaveAttribute('href', '/browse/hellofresh/quick-dinners')
    })
  })

  describe('subtitle', () => {
    it('shows "{count} recipes" when card_count > 0', () => {
      setCollectionState({ isLoading: false })
      renderRow({ ...baseCollection, card_count: 7 })
      expect(screen.getByText('7 recipes')).toBeInTheDocument()
    })

    it('shows "1 recipe" (singular) when card_count is 1', () => {
      setCollectionState({ isLoading: false })
      renderRow({ ...baseCollection, card_count: 1 })
      expect(screen.getByText('1 recipe')).toBeInTheDocument()
    })

    it('shows "Not loaded yet" before inView when card_count is 0', () => {
      setCollectionState({ isLoading: false })
      renderRow({ ...baseCollection, card_count: 0 })
      expect(screen.getByText('Not loaded yet')).toBeInTheDocument()
    })
  })

  describe('section id for SectionNav scroll', () => {
    it('section element has id hellofresh-{slug}', () => {
      setCollectionState({ isLoading: false })
      const { container } = renderRow()
      const section = container.querySelector('section')
      expect(section).toHaveAttribute('id', 'hellofresh-quick-dinners')
    })
  })

  describe('scroll arrow effect — cached remount path', () => {
    it('registers scroll listener on the container when inView flips with pre-cached data', () => {
      // Simulate a cached revisit: data is already populated before inView becomes true.
      const cards = Array.from({ length: 5 }, (_, i) => makeCard(`card-${i}`))
      setCollectionState({
        data: {
          slug: 'quick-dinners',
          name: 'Quick Dinners',
          source_type: 'hellofresh_web',
          last_fetched_at: null,
          children: [],
          cards,
          fetch_error: null,
        },
      })

      const addEventSpy = vi.spyOn(Element.prototype, 'addEventListener')
      renderRow()

      // Before inView the scroll container is absent from the DOM; no 'scroll' listener yet.
      const scrollCallsBefore = addEventSpy.mock.calls.filter(([event]) => event === 'scroll').length

      triggerInView()

      // After inView the container is rendered and the effect must re-run to attach the listener.
      const scrollCallsAfter = addEventSpy.mock.calls.filter(([event]) => event === 'scroll').length
      expect(scrollCallsAfter).toBeGreaterThan(scrollCallsBefore)

      addEventSpy.mockRestore()
    })
  })
})
