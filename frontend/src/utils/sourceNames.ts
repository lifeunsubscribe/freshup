const SOURCE_NAMES: Record<string, string> = {
  hellofresh: 'HelloFresh',
  kitchen_sanctuary: 'Kitchen Sanctuary',
}

export function sourceName(sourceType: string): string {
  return SOURCE_NAMES[sourceType] ?? sourceType
}
