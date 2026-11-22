/**
 * How an ingredient amount reads: "2 tbsp", "1.5 cup", "3" for a plain count,
 * "to taste" when the recipe gives none (the importer stores 0.001 for that).
 */

/** The importer's quantity for "no amount given" (UNPARSEABLE_QUANTITY_SENTINEL). */
const TO_TASTE_QUANTITY = 0.001

export function isToTaste(quantity: number): boolean {
  return Math.abs(quantity - TO_TASTE_QUANTITY) < 0.0001
}

/** Short spellings, so amounts fit a narrow column: "2 tsp", not "2 teaspoon". */
const SHORT_UNITS: Record<string, string> = {
  teaspoon: 'tsp', teaspoons: 'tsp',
  tablespoon: 'tbsp', tablespoons: 'tbsp',
  ounce: 'oz', ounces: 'oz',
  pound: 'lb', pounds: 'lb', lbs: 'lb',
  gram: 'g', grams: 'g',
  kilogram: 'kg', kilograms: 'kg',
  milliliter: 'ml', milliliters: 'ml',
  liter: 'l', liters: 'l',
  cups: 'cup',
  cloves: 'clove',
}

export function shortUnit(unit: string): string {
  const plain = (unit ?? '').trim()
  return SHORT_UNITS[plain.toLowerCase()] ?? plain
}

export function formatAmount(quantity: number, unit: string, toTaste = isToTaste(quantity)): string {
  if (toTaste) return 'to taste'
  const amount = Number.isInteger(quantity) ? String(quantity) : String(Number(quantity.toFixed(2)))
  const plainUnit = shortUnit(unit)
  return plainUnit && plainUnit !== 'count' && plainUnit !== 'unit' ? `${amount} ${plainUnit}` : amount
}

/**
 * A recipe name short enough for a chip: the part before " with ", cut at a
 * word under `max` characters. "Cajun-Spiced Chickpea Power Bowls with ..."
 * becomes "Cajun-Spiced Chickpea…".
 */
export function shortRecipeName(name: string, max = 22): string {
  const main = name.split(/\s+with\s+/i)[0].trim()
  if (main.length <= max) return main
  const cut = main.slice(0, max + 1)
  const atWord = cut.lastIndexOf(' ')
  return `${(atWord > 8 ? cut.slice(0, atWord) : main.slice(0, max)).replace(/[\s,&-]+$/, '')}…`
}
