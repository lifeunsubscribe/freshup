const FRAC_VALUES: Record<string, number> = {
  '½': 0.5, '¼': 0.25, '¾': 0.75,
  '⅓': 1 / 3, '⅔': 2 / 3,
  '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875,
}

// Replace characters in `text` between `start` and `end` with null bytes so
// later patterns do not re-match the same span.
function mask(text: string, start: number, end: number): string {
  return text.slice(0, start) + '\x00'.repeat(end - start) + text.slice(end)
}

/**
 * Extracts cook durations (in whole minutes) from a step instruction.
 *
 * Evaluation order (each pass masks consumed spans so later passes skip them):
 *   1. Compound:        "1 hour 30 minutes", "1 hr 30 min", "1h30"  → sum
 *   2. Ranges:          "N-M minutes"   → upper bound (M)
 *   3. Decimal hours:   "N.M hours"     → round(N.M × 60)
 *   4. Int+frac hours:  "N½ hours"      → round((N + frac) × 60)
 *   5. Pure-frac hours: "½ hour"        → round(frac × 60)
 *   6. Integer hours:   "N hours / N h" → N × 60
 *   7. Decimal minutes: "N.M minutes"   → ceil(N.M)
 *   8. Plain minutes:   "N minutes"     → N
 *   9. Seconds:         "N seconds"     → ceil(N/60), min 1
 *
 * All patterns carry the `i` flag (case-insensitive).
 * "minute/minutes" without a leading number is ignored.
 * Returns distinct values sorted ascending.
 */
export function durationsInStep(step: string): number[] {
  const result = new Set<number>()
  let text = step

  // ── 1. Compound: "1 hour 30 minutes", "1 hr 30 min", "1h30" ─────────────
  // Run first so the parts are never re-matched by later passes.
  const compoundWordRe = /\b(\d+)\s*(?:hours?|hrs?)\s+(\d+)\s*(?:minutes?|mins?)\b/gi
  for (const m of [...text.matchAll(compoundWordRe)]) {
    result.add(parseInt(m[1]) * 60 + parseInt(m[2]))
    text = mask(text, m.index!, m.index! + m[0].length)
  }

  // Compact form: "1h30" (digit immediately followed by 'h' then digits).
  // \b before the first digit; word boundary after the minute digits.
  const compoundCompactRe = /\b(\d+)h([0-5]?\d)\b/gi
  for (const m of [...text.matchAll(compoundCompactRe)]) {
    result.add(parseInt(m[1]) * 60 + parseInt(m[2]))
    text = mask(text, m.index!, m.index! + m[0].length)
  }

  // ── 2. Ranges: "20-25 minutes" → upper bound ──────────────────────────────
  const rangeRe = /\b(\d+)\s*[-–]\s*(\d+)\s*(?:minutes?|mins?)\b/gi
  for (const m of [...text.matchAll(rangeRe)]) {
    result.add(parseInt(m[2]))
    text = mask(text, m.index!, m.index! + m[0].length)
  }

  // ── 3. Decimal hours: "1.5 hours", "1,5 hours" ────────────────────────────
  const hourDecRe = /\b(\d+)[.,](\d+)\s*(?:hours?|hrs?)\b/gi
  for (const m of [...text.matchAll(hourDecRe)]) {
    result.add(Math.round(parseFloat(`${m[1]}.${m[2]}`) * 60))
    text = mask(text, m.index!, m.index! + m[0].length)
  }

  // ── 4. Integer+fraction hours: "1½ hours" ─────────────────────────────────
  const fracChars = Object.keys(FRAC_VALUES).join('')
  const hourFracRe = new RegExp(`\\b(\\d+)\\s*([${fracChars}])\\s*(?:hours?|hrs?)\\b`, 'gi')
  for (const m of [...text.matchAll(hourFracRe)]) {
    result.add(Math.round((parseInt(m[1]) + (FRAC_VALUES[m[2]] ?? 0)) * 60))
    text = mask(text, m.index!, m.index! + m[0].length)
  }

  // ── 5. Pure-fraction hours: "½ hour" ──────────────────────────────────────
  // No leading \b because fraction chars are not word chars in JS regex.
  const pureFracRe = new RegExp(`([${fracChars}])\\s*(?:hours?|hrs?)\\b`, 'gi')
  for (const m of [...text.matchAll(pureFracRe)]) {
    result.add(Math.round((FRAC_VALUES[m[1]] ?? 0) * 60))
    text = mask(text, m.index!, m.index! + m[0].length)
  }

  // ── 6. Integer hours: "2 hours", "2 hrs", "2 h" ───────────────────────────
  const hourIntRe = /\b(\d+)\s*(?:hours?|hrs?|h\b)/gi
  for (const m of [...text.matchAll(hourIntRe)]) {
    result.add(parseInt(m[1]) * 60)
  }

  // ── 7. Decimal minutes: "2.5 minutes" → ceil(2.5) = 3 ────────────────────
  // Must run before the integer-minutes pass; masks the span so "2.5 minutes"
  // is not also matched as "5 minutes" (the dot creates a word boundary before 5).
  const minDecRe = /\b(\d+)[.,](\d+)\s*(?:minutes?|mins?)\b/gi
  for (const m of [...text.matchAll(minDecRe)]) {
    result.add(Math.ceil(parseFloat(`${m[1]}.${m[2]}`)))
    text = mask(text, m.index!, m.index! + m[0].length)
  }

  // ── 8. Plain minutes: "15 minutes", "15 min" ──────────────────────────────
  const minRe = /\b(\d+)\s*(?:minutes?|mins?)\b/gi
  for (const m of [...text.matchAll(minRe)]) {
    result.add(parseInt(m[1]))
  }

  // ── 9. Seconds: N seconds/secs → ceil(N/60) min ──────────────────────────
  const secRe = /\b(\d+)\s*(?:seconds?|secs?)\b/gi
  for (const m of [...text.matchAll(secRe)]) {
    result.add(Math.max(1, Math.ceil(parseInt(m[1]) / 60)))
  }

  return [...result].sort((a, b) => a - b)
}

/**
 * Formats a duration in minutes for display on a "Start N min" button.
 * Values < 60 → "Start N min"; ≥ 60 → "Start N hr [M min]".
 */
export function formatStartLabel(minutes: number): string {
  if (minutes < 60) return `Start ${minutes} min`
  const hrs = Math.floor(minutes / 60)
  const mins = minutes % 60
  if (mins === 0) return `Start ${hrs} hr`
  return `Start ${hrs} hr ${mins} min`
}
