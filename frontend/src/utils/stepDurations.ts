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
 * Rules (all case-insensitive):
 *   - "N-M minutes"      → M (use upper bound of range)
 *   - "N.M hours"        → round(N.M × 60)
 *   - "N½ hours"         → round((N + fraction) × 60)
 *   - "N hours / N hrs"  → N × 60
 *   - "N h"              → N × 60
 *   - "N minutes / N min"→ N
 *   - "N seconds"        → 1 (ceiling)
 *   - "minute/minutes" without a leading number → ignored
 *
 * Returns distinct values sorted ascending.
 */
export function durationsInStep(step: string): number[] {
  const result = new Set<number>()
  let text = step

  // ── 1. Ranges: "20-25 minutes" → upper bound ──────────────────────────────
  const rangeRe = /\b(\d+)\s*[-–]\s*(\d+)\s*(?:minutes?|mins?)\b/gi
  for (const m of [...text.matchAll(rangeRe)]) {
    result.add(parseInt(m[2]))
    text = mask(text, m.index!, m.index! + m[0].length)
  }

  // ── 2. Decimal hours: "1.5 hours", "1,5 hours" ────────────────────────────
  const hourDecRe = /\b(\d+)[.,](\d+)\s*(?:hours?|hrs?)\b/gi
  for (const m of [...text.matchAll(hourDecRe)]) {
    result.add(Math.round(parseFloat(`${m[1]}.${m[2]}`) * 60))
    text = mask(text, m.index!, m.index! + m[0].length)
  }

  // ── 3. Integer+fraction hours: "1½ hours" ─────────────────────────────────
  const fracChars = Object.keys(FRAC_VALUES).join('')
  const hourFracRe = new RegExp(`\\b(\\d+)\\s*([${fracChars}])\\s*(?:hours?|hrs?)\\b`, 'g')
  for (const m of [...text.matchAll(hourFracRe)]) {
    result.add(Math.round((parseInt(m[1]) + (FRAC_VALUES[m[2]] ?? 0)) * 60))
    text = mask(text, m.index!, m.index! + m[0].length)
  }

  // ── 4. Pure-fraction hours: "½ hour" ──────────────────────────────────────
  // No leading \b because fraction chars are not word chars in JS regex.
  const pureFracRe = new RegExp(`([${fracChars}])\\s*(?:hours?|hrs?)\\b`, 'g')
  for (const m of [...text.matchAll(pureFracRe)]) {
    result.add(Math.round((FRAC_VALUES[m[1]] ?? 0) * 60))
    text = mask(text, m.index!, m.index! + m[0].length)
  }

  // ── 5. Integer hours: "2 hours", "2 hrs", "2 h" ───────────────────────────
  const hourIntRe = /\b(\d+)\s*(?:hours?|hrs?|h\b)/gi
  for (const m of [...text.matchAll(hourIntRe)]) {
    result.add(parseInt(m[1]) * 60)
  }

  // ── 6. Plain minutes: "15 minutes", "15 min" ──────────────────────────────
  const minRe = /\b(\d+)\s*(?:minutes?|mins?)\b/gi
  for (const m of [...text.matchAll(minRe)]) {
    result.add(parseInt(m[1]))
  }

  // ── 7. Seconds: any N seconds/secs → 1 min (ceiling) ─────────────────────
  if (/\b\d+\s*(?:seconds?|secs?)\b/i.test(text)) {
    result.add(1)
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
