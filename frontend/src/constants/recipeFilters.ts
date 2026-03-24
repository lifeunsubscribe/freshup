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

export interface CookTimeOption {
  value: number
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
 * Cook time filter options (in minutes)
 *
 * These represent maximum cook time filters that users can select.
 */
export const COOK_TIME_OPTIONS: CookTimeOption[] = [
  { value: 15, label: '15 min or less' },
  { value: 30, label: '30 min or less' },
  { value: 45, label: '45 min or less' },
  { value: 60, label: '1 hour or less' },
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
 * Helper function to get the label for a cook time value
 */
export function getCookTimeLabel(cookTime: number | string): string {
  const numericCookTime = typeof cookTime === 'string' ? Number(cookTime) : cookTime
  const option = COOK_TIME_OPTIONS.find((opt) => opt.value === numericCookTime)
  return option?.label || `${numericCookTime} min`
}

/**
 * Helper function to get the label for a tag value
 */
export function getTagLabel(tag: string): string {
  const option = TAG_OPTIONS.find((opt) => opt.value === tag)
  return option?.label || tag
}
