import { describe, it, expect } from 'vitest'
import { buildPageRows, matchesValue, valueRows, MIN_ROW_SIZE, YOUR_ROWS } from './themeRows'
import type { RecipeListResponse, Theme, ThemeValue } from '../../api'

const value = (extra: Partial<ThemeValue>): ThemeValue => ({
  value: 'italian',
  label: 'Italian',
  library_tag: null,
  library_source_type: null,
  library_count: 0,
  match_tags: [],
  match_source_types: [],
  collections: [],
  ...extra,
})

const recipe = (tags: string[], source_type = 'manual') =>
  ({ id: 'r', name: 'R', source_type, tags, created_at: '', cook_time_minutes: null, prep_time_minutes: null, base_servings: 2 }) as RecipeListResponse

describe('valueRows', () => {
  it('gives the user’s recipes and each collection their own row', () => {
    const rows = valueRows(
      'cuisine',
      value({
        library_tag: 'italian',
        library_count: 2,
        collections: [{ source_type: 'hellofresh_web', slug: 'italian-recipes', name: 'Italian Recipes', card_count: 9, last_fetched_at: null, contains: [] }],
      })
    )
    expect(rows.map((r) => r.id)).toEqual(['lib-cuisine-italian', 'hellofresh_web-italian-recipes'])
    expect(rows[0]).toMatchObject({ kind: 'library', filters: { tag: 'italian', limit: 20 } })
  })

  it('skips the library row when the user has none', () => {
    expect(valueRows('cuisine', value({ library_tag: 'italian', library_count: 0 }))).toEqual([])
  })

  it('queries by source type for source values', () => {
    const [row] = valueRows('source', value({ value: 'kitchen_sanctuary', library_source_type: 'kitchen_sanctuary', library_count: 3 }))
    expect(row).toMatchObject({ kind: 'library', filters: { source_type: 'kitchen_sanctuary' } })
  })
})

describe('matchesValue', () => {
  it('matches by tag case-insensitively or by source type', () => {
    const italian = matchesValue(value({ match_tags: ['italian'] }))
    expect(italian(recipe(['Italian']))).toBe(true)
    expect(italian(recipe(['thai']))).toBe(false)
    const ks = matchesValue(value({ match_source_types: ['kitchen_sanctuary'] }))
    expect(ks(recipe([], 'kitchen_sanctuary'))).toBe(true)
  })
})

describe('YOUR_ROWS recently-viewed row', () => {
  it('comes first, on the main page, on a theme page and on a filtered page', () => {
    const themes: Theme[] = [
      {
        key: 'cuisine',
        label: 'Cuisine',
        values: [value({ value: 'italian', library_tag: 'italian', library_count: 3 })],
      },
    ]

    expect(buildPageRows(themes, null, []).rows[0].id).toBe('recently-viewed')
    expect(buildPageRows(themes, 'cuisine', []).rows[0].id).toBe('recently-viewed')
    const filtered = buildPageRows(themes, null, [{ theme: 'cuisine', value: 'italian' }]).rows
    expect(filtered[0].id).toBe('recently-viewed')
    // Anchored means unfiltered: it carries no show-if rule on a filtered page.
    expect(filtered[0].kind === 'library' && filtered[0].showIf).toBeFalsy()
    expect(filtered.filter((r) => r.id === 'recently-viewed')).toHaveLength(1)
  })

  it('has id recently-viewed, title Recently viewed, and viewed: true filter', () => {
    const row = YOUR_ROWS.find((r) => r.id === 'recently-viewed')
    expect(row).toBeDefined()
    expect(row?.title).toBe('Recently viewed')
    expect(row?.filters).toMatchObject({ viewed: true })
  })

  it('no longer contains a recently-added row', () => {
    expect(YOUR_ROWS.find((r) => r.id === 'recently-added')).toBeUndefined()
    expect(YOUR_ROWS.map((r) => r.title)).not.toContain('Recently added')
  })
})

describe('buildPageRows', () => {
  it('shows only the user’s rows before themes load', () => {
    expect(buildPageRows(undefined, null, []).rows).toEqual(YOUR_ROWS)
  })

  it('returns nothing for an unknown filter value rather than guessing', () => {
    const themes: Theme[] = [{ key: 'cuisine', label: 'Cuisine', values: [] }]
    expect(buildPageRows(themes, null, [{ theme: 'cuisine', value: 'nope' }])).toEqual({ rows: [], heading: null })
  })

  it('does not repeat a collection that appears under two values', () => {
    const shared = { source_type: 'hellofresh_web', slug: 'x', name: 'X', card_count: 1, last_fetched_at: null, contains: [] }
    const themes: Theme[] = [
      { key: 'source', label: 'Source', values: [value({ value: 'a', collections: [shared] }), value({ value: 'b', collections: [shared] })] },
    ]
    // Recently viewed is anchored first on every page; then the collection, once.
    expect(buildPageRows(themes, 'source', []).rows.map((r) => r.id)).toEqual([
      'recently-viewed',
      'hellofresh_web-x',
    ])
  })

  describe('combined filters', () => {
    const c = (slug: string, contains: string[] = []) => ({
      source_type: 'hellofresh_web', slug, name: slug, card_count: 5, last_fetched_at: null, contains,
    })
    const themes: Theme[] = [
      {
        key: 'cuisine',
        label: 'Cuisine',
        values: [
          value({ value: 'italian', library_tag: 'italian', library_count: 2, match_tags: ['italian'], collections: [c('italian-recipes', ['diet:vegetarian'])] }),
          value({ value: 'thai', label: 'Thai', collections: [c('thai-recipes')] }),
        ],
      },
      {
        key: 'diet',
        label: 'Diet',
        values: [value({ value: 'vegetarian', label: 'Vegetarian', match_tags: ['vegetarian'], collections: [c('vegetarian-recipes', ['cuisine:italian'])] })],
      },
    ]
    const both = [{ theme: 'cuisine', value: 'italian' }, { theme: 'diet', value: 'vegetarian' }]

    it('keeps lists that pass every filter, by belonging or by containing', () => {
      const ids = buildPageRows(themes, null, both).rows.map((r) => r.id)
      expect(ids).toContain('hellofresh_web-italian-recipes') // Italian, contains vegetarian cards
      expect(ids).toContain('hellofresh_web-vegetarian-recipes') // Vegetarian, contains Italian cards
      expect(ids).not.toContain('hellofresh_web-thai-recipes')
    })

    it('defers library rows to their recipes for filters they do not belong to', () => {
      const rows = buildPageRows(themes, null, both).rows
      const italianLib = rows.find((r) => r.id === 'lib-cuisine-italian')
      expect(italianLib?.kind).toBe('library')
      const showIf = italianLib?.kind === 'library' ? italianLib.showIf! : () => false
      // Already Italian; needs a vegetarian recipe to pass the diet filter
      expect(showIf([recipe(['italian'])])).toBe(false)
      expect(showIf([recipe(['italian']), recipe(['italian', 'vegetarian'])])).toBe(true)
    })

    it('applies filters on a theme page too', () => {
      const ids = buildPageRows(themes, 'cuisine', [{ theme: 'diet', value: 'vegetarian' }]).rows.map((r) => r.id)
      expect(ids).toContain('hellofresh_web-italian-recipes')
      expect(ids).not.toContain('hellofresh_web-thai-recipes')
      expect(ids).not.toContain('hellofresh_web-vegetarian-recipes') // not a cuisine list
    })
  })
})

describe('rows worth showing on the main page', () => {
  const coll = (slug: string, card_count: number, fetched = card_count > 0) => ({
    source_type: 'hellofresh_web', slug, name: slug, card_count, last_fetched_at: fetched ? '2026-11-01T00:00:00Z' : null, contains: [],
  })
  const themes: Theme[] = [
    {
      key: 'cuisine',
      label: 'Cuisine',
      values: [
        value({ value: 'italian', library_tag: 'italian', library_count: 12, collections: [coll('italian-recipes', 30)] }),
        value({ value: 'thai', label: 'Thai', library_tag: 'thai', library_count: 3, collections: [coll('thai-recipes', 9)] }),
        value({ value: 'korean', label: 'Korean', collections: [coll('korean-recipes', 0)] }),
      ],
    },
  ]
  const sampled = () => buildPageRows(themes, null, []).rows.filter((r) => !YOUR_ROWS.some((y) => y.id === r.id))

  it('Quick meals needs ten recipes and something Recently viewed does not already show', () => {
    const recent = YOUR_ROWS.find((r) => r.id === 'recently-viewed')!
    const quick = YOUR_ROWS.find((r) => r.id === 'quick-meals')!
    expect(MIN_ROW_SIZE).toBe(10)
    expect(quick.minCount).toBe(MIN_ROW_SIZE)
    expect(quick.hideIfWithin).toEqual(recent.filters)
  })

  it('favorites and recently viewed show however short they are', () => {
    for (const id of ['favorites', 'recently-viewed']) {
      const row = YOUR_ROWS.find((r) => r.id === id)!
      expect(row.minCount).toBeUndefined()
      expect(row.hideIfWithin).toBeUndefined()
    }
  })

  it('leaves lists known to have fewer than ten out of the sampler', () => {
    // Thai (3 of the user's, 9 from HelloFresh) is dropped; the next fullest take its place
    expect(sampled().map((r) => r.id)).toEqual(['hellofresh_web-italian-recipes', 'lib-cuisine-italian'])
  })

  it('keeps a list that has not loaded yet, and has its row check once it has', () => {
    const onlyKorean: Theme[] = [{ ...themes[0], values: [themes[0].values[2]] }]
    const rows = buildPageRows(onlyKorean, null, []).rows.filter((r) => r.id === 'hellofresh_web-korean-recipes')
    expect(rows).toHaveLength(1)
    expect(rows[0].minCount).toBe(MIN_ROW_SIZE)
  })

  it('sampled rows carry the minimum so a short loaded list hides itself', () => {
    expect(sampled().every((r) => r.minCount === MIN_ROW_SIZE)).toBe(true)
  })

  it('a theme page and a filter still show short lists: the user asked for them', () => {
    const themePage = buildPageRows(themes, 'cuisine', []).rows
    expect(themePage.map((r) => r.id)).toContain('hellofresh_web-thai-recipes')
    expect(themePage.map((r) => r.id)).toContain('lib-cuisine-thai')
    expect(themePage.every((r) => r.minCount === undefined)).toBe(true)

    const filtered = buildPageRows(themes, null, [{ theme: 'cuisine', value: 'thai' }]).rows
    const thai = filtered.filter((r) => r.id.includes('thai'))
    expect(thai).toHaveLength(2)
    expect(thai.every((r) => r.minCount === undefined)).toBe(true)
  })
})
