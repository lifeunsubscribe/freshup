/**
 * Short forms for the long unit names recipe sources give us, for places
 * where a quantity sits in a narrow column ("3 tbsp", not "3 tablespoon").
 * Display only: stored units are not changed.
 */
const SHORT_UNITS: Record<string, string> = {
  tablespoon: 'tbsp',
  tablespoons: 'tbsp',
  teaspoon: 'tsp',
  teaspoons: 'tsp',
  ounce: 'oz',
  ounces: 'oz',
  pound: 'lb',
  pounds: 'lb',
}

/** The unit as shown beside a quantity; unknown units pass through unchanged. */
export function displayUnit(unit: string | null | undefined): string {
  if (!unit) return ''
  return SHORT_UNITS[unit.trim().toLowerCase()] ?? unit
}
