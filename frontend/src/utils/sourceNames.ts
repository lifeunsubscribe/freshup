export type SourceType = 'hellofresh' | 'kitchen_sanctuary'

const SOURCE_NAMES: Record<SourceType, string> = {
  hellofresh: 'HelloFresh',
  kitchen_sanctuary: 'Kitchen Sanctuary',
}

export function sourceName(sourceType: string): string {
  return SOURCE_NAMES[sourceType as SourceType] ?? sourceType
}

// Exact-hostname mapping from import domain to source_type string.
// Mirrors SUPPORTED_IMPORT_DOMAINS in src/routers/scraper.py.
const URL_SOURCE_TYPES: Partial<Record<string, SourceType>> = {
  'hellofresh.com': 'hellofresh',
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
