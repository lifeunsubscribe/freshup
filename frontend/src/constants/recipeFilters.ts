/**
 * Centralized constants for recipe filter options
 *
 * This file defines all available filter options for the recipe browse interface.
 * Centralizing these values ensures consistency across the application and makes
 * it easier to add, remove, or modify filter options.
 */

export interface FilterOption {
  value: string
  label: string
}

/**
 * Source type filter options
 *
 * Note: This is a subset of the SourceType enum in the backend.
 * Not all source types are exposed as filter options in the UI.
 */
export const SOURCE_TYPE_OPTIONS: FilterOption[] = [
  { value: 'manual', label: 'My recipes' },
  { value: 'hellofresh_card', label: 'HelloFresh' },
  { value: 'ad_hoc', label: 'Ad-hoc' },
]

/**
 * Tag/cuisine filter options
 *
 * These represent recipe tags that users can filter by.
 * Tags are stored as free-form strings in the database but
 * the UI exposes a curated list of common options.
 */
export const TAG_OPTIONS: FilterOption[] = [
  { value: 'italian', label: 'Italian' },
  { value: 'mexican', label: 'Mexican' },
  { value: 'asian', label: 'Asian' },
  { value: 'american', label: 'American' },
  { value: 'mediterranean', label: 'Mediterranean' },
  { value: 'indian', label: 'Indian' },
  { value: 'thai', label: 'Thai' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'vegetarian', label: 'Vegetarian' },
]

/**
 * Helper function to get the label for a source type value
 */
export function getSourceTypeLabel(sourceType: string): string {
  const option = SOURCE_TYPE_OPTIONS.find((opt) => opt.value === sourceType)
  return option?.label || sourceType
}

/**
 * Helper function to get the label for a tag value
 */
export function getTagLabel(tag: string): string {
  const option = TAG_OPTIONS.find((opt) => opt.value === tag)
  return option?.label || tag
}
