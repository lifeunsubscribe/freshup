/**
 * How an ingredient amount reads: "2 tbsp", "1.5 cup", "3" for a plain count,
 * "to taste" when the recipe gives none (the importer stores 0.001 for that).
 */

/** The importer's quantity for "no amount given" (UNPARSEABLE_QUANTITY_SENTINEL). */
const TO_TASTE_QUANTITY = 0.001

export function isToTaste(quantity: number): boolean {
  return Math.abs(quantity - TO_TASTE_QUANTITY) < 0.0001
}

export function formatAmount(quantity: number, unit: string, toTaste = isToTaste(quantity)): string {
  if (toTaste) return 'to taste'
  const amount = Number.isInteger(quantity) ? String(quantity) : String(Number(quantity.toFixed(2)))
  const plainUnit = (unit ?? '').trim()
  return plainUnit && plainUnit !== 'count' && plainUnit !== 'unit' ? `${amount} ${plainUnit}` : amount
}
