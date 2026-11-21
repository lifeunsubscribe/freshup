export type SourceType = 'hellofresh' | 'hellofresh_web' | 'homechef' | 'homechef_web' | 'kitchen_sanctuary'

const SOURCE_NAMES: Record<SourceType, string> = {
  hellofresh: 'HelloFresh',
  hellofresh_web: 'HelloFresh',
  homechef: 'Home Chef',
  homechef_web: 'Home Chef',
  kitchen_sanctuary: 'Kitchen Sanctuary',
}

export function sourceName(sourceType: string): string {
  return SOURCE_NAMES[sourceType as SourceType] ?? sourceType
}

const OWN_RECIPE_SOURCES = new Set(['manual', 'ad_hoc'])

/** Byline for a planned meal: the source's name, or "Your recipes" for one the user wrote. */
export function ownOrSourceName(sourceType: string): string {
  return OWN_RECIPE_SOURCES.has(sourceType) ? 'Your recipes' : sourceName(sourceType)
}

// Exact-hostname mapping from import domain to source_type string.
// Mirrors SUPPORTED_IMPORT_DOMAINS in src/routers/scraper.py.
const URL_SOURCE_TYPES: Partial<Record<string, SourceType>> = {
  'hellofresh.com': 'hellofresh',
  'homechef.com': 'homechef',
  'kitchensanctuary.com': 'kitchen_sanctuary',
}

export function sourceTypeForUrl(url: string): SourceType | null {
  try {
    const { hostname } = new URL(url)
    const bare = hostname.startsWith('www.') ? hostname.slice(4) : hostname
    return URL_SOURCE_TYPES[bare] ?? null
  } catch {
    return null
  }
}
