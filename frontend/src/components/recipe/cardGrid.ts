/**
 * Grid for recipe and catalog cards.
 *
 * Phones: 2 columns. From the sm breakpoint up: as many 200px-minimum columns
 * as fit, so a typical desktop window shows 5 per row.
 *
 * Kept as a literal so Tailwind's scanner sees the arbitrary value.
 */
export const CARD_GRID_CLASS = 'grid grid-cols-2 sm:grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-3'
