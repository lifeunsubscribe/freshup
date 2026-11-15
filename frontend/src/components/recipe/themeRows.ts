import type { RecipeListFilters, RecipeListResponse, Theme, ThemeCollection, ThemeValue } from '../../api'
import type { ThemeFilter } from './ThemeBar'

/** Cards per carousel row. Desktop shows ~7 at a time, so 20 gives a few pages of scroll. */
export const CAROUSEL_LIMIT = 20

/** How many of each theme's fullest lists the main page samples. */
const SAMPLER_PER_THEME = 2

/** Themes sampled on the main page. Source is left out: its lists are the other themes' lists again. */
const SAMPLED_THEMES = ['cuisine', 'ingredient', 'dish', 'diet', 'meal_type']

export interface LibraryRowSpec {
  kind: 'library'
  id: string
  title: string
  filters: RecipeListFilters
  /** Known item count, for ordering; undefined for the user's own rows. */
  size?: number
  subtitle?: (count: number | undefined) => string
  /** Show the row (whole) only if its loaded recipes pass. Set while theme filters are active. */
  showIf?: (recipes: RecipeListResponse[]) => boolean
}

export interface CollectionRowSpec {
  kind: 'collection'
  id: string
  collection: ThemeCollection
  size: number
}

export type RowSpec = LibraryRowSpec | CollectionRowSpec

/** The user's own rows: always first on the main page. */
export const YOUR_ROWS: LibraryRowSpec[] = [
  { kind: 'library', id: 'favorites', title: 'Your favorites', filters: { limit: CAROUSEL_LIMIT, liked: true } },
  { kind: 'library', id: 'recently-added', title: 'Recently added', filters: { limit: CAROUSEL_LIMIT } },
  { kind: 'library', id: 'quick-meals', title: 'Quick meals', filters: { limit: CAROUSEL_LIMIT, max_cook_time: 30 } },
]

const plural = (n: number) => `${n} recipe${n === 1 ? '' : 's'}`

/**
 * Every whole list behind one theme value: the user's matching recipes (if
 * any) and each catalog collection, each a separate row naming its source.
 */
export function valueRows(themeKey: string, value: ThemeValue): RowSpec[] {
  const rows: RowSpec[] = []
  const libraryFilters: RecipeListFilters | null = value.library_tag
    ? { limit: CAROUSEL_LIMIT, tag: value.library_tag }
    : value.library_source_type
      ? { limit: CAROUSEL_LIMIT, source_type: value.library_source_type }
      : null
  if (libraryFilters && value.library_count > 0) {
    rows.push({
      kind: 'library',
      id: `lib-${themeKey}-${value.value}`,
      title: value.label,
      filters: libraryFilters,
      size: value.library_count,
      subtitle: (n) => `${plural(n ?? value.library_count)} · Your recipes`,
    })
  }
  for (const collection of value.collections) {
    rows.push({ kind: 'collection', id: `${collection.source_type}-${collection.slug}`, collection, size: collection.card_count })
  }
  return rows
}

/** A recipe counts toward a value if it carries one of its tags or source types. */
export function matchesValue(value: ThemeValue): (recipe: RecipeListResponse) => boolean {
  const tags = new Set(value.match_tags)
  const sources = new Set(value.match_source_types)
  return (recipe) =>
    sources.has(recipe.source_type) || recipe.tags.some((t) => tags.has(t.toLowerCase()))
}

function dedupe(rows: RowSpec[]): RowSpec[] {
  const seen = new Set<string>()
  return rows.filter((r) => (seen.has(r.id) ? false : (seen.add(r.id), true)))
}

export interface PageRows {
  rows: RowSpec[]
  heading: { title: string; subtitle?: string } | null
}

interface ResolvedFilter {
  key: string
  themeKey: string
  value: ThemeValue
  /** Ids of the rows that belong to this value outright. */
  members: Set<string>
}

/**
 * Keep only rows that pass every filter, each shown whole.
 *
 * A row passes a filter when it belongs to that value (the Italian collection,
 * your Italian row) or contains something with that value: a recipe carrying
 * the tag, or a catalog card that also sits in that value's collection.
 * Collections are decided here; the user's rows are decided once their
 * recipes load, via showIf.
 */
function applyFilters(rows: RowSpec[], filters: ResolvedFilter[]): RowSpec[] {
  const kept: RowSpec[] = []
  for (const row of rows) {
    const pending = filters.filter((f) => !f.members.has(row.id))
    if (row.kind === 'collection') {
      if (pending.every((f) => row.collection.contains.includes(f.key))) kept.push(row)
    } else if (pending.length === 0) {
      kept.push(row)
    } else {
      const checks = pending.map((f) => matchesValue(f.value))
      kept.push({ ...row, showIf: (recipes) => checks.every((check) => recipes.some(check)) })
    }
  }
  return kept
}

/**
 * Decide which rows the Recipes page shows.
 *
 * - Main page: the user's rows, then the fullest few lists from each theme.
 * - Theme page ("See all cuisines"): every list from every value of the theme.
 * - Filters (Cuisine → Italian, Diet → Vegetarian) apply together: the
 *   candidates are the theme page's lists, or else the user's rows plus every
 *   list under any selected value; only rows passing every filter remain.
 */
export function buildPageRows(
  themes: Theme[] | undefined,
  themeKey: string | null,
  filters: ThemeFilter[] = []
): PageRows {
  const resolved: ResolvedFilter[] = []
  for (const f of filters) {
    const theme = themes?.find((t) => t.key === f.theme)
    const value = theme?.values.find((v) => v.value === f.value)
    // Unknown value (or themes not loaded yet): show nothing rather than guess.
    if (!theme || !value) return { rows: [], heading: null }
    resolved.push({
      key: `${f.theme}:${f.value}`,
      themeKey: theme.key,
      value,
      members: new Set(valueRows(theme.key, value).map((r) => r.id)),
    })
  }

  if (themeKey) {
    const theme = themes?.find((t) => t.key === themeKey)
    if (!theme) return { rows: [], heading: null }
    const rows = dedupe(theme.values.flatMap((v) => valueRows(theme.key, v)))
    return { rows: applyFilters(rows, resolved), heading: { title: theme.label } }
  }

  if (resolved.length > 0) {
    const candidates = dedupe([...YOUR_ROWS, ...resolved.flatMap((f) => valueRows(f.themeKey, f.value))])
    // No page heading: the theme bar already reads "Cuisine: Italian", and a
    // heading would sit right above the user's own "Italian" row.
    return { rows: applyFilters(candidates, resolved), heading: null }
  }

  const sampler = (themes ?? [])
    .filter((t) => SAMPLED_THEMES.includes(t.key))
    .flatMap((theme) =>
      theme.values
        .flatMap((v) => valueRows(theme.key, v))
        .sort((a, b) => (b.size ?? 0) - (a.size ?? 0))
        .slice(0, SAMPLER_PER_THEME)
    )
  return { rows: dedupe([...YOUR_ROWS, ...sampler]), heading: null }
}
