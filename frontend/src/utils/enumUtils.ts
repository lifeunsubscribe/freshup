/**
 * Utility functions for working with TypeScript enums
 *
 * Provides helpers to:
 * - Extract all values from an enum
 * - Format enum keys into human-readable labels
 */

/**
 * Extracts all values from a TypeScript enum
 *
 * @param enumObject - The enum to extract values from
 * @returns Array of enum values
 *
 * @example
 * enum Color { RED = 'red', BLUE = 'blue' }
 * getEnumValues(Color) // ['red', 'blue']
 */
export function getEnumValues<T extends Record<string, string>>(
  enumObject: T
): T[keyof T][] {
  return Object.values(enumObject)
}

/**
 * Converts an enum key to a human-readable label
 *
 * Handles various formatting patterns:
 * - UPPER_CASE → Title Case
 * - camelCase → Title Case
 * - snake_case → Title Case
 *
 * @param enumKey - The enum key to format
 * @returns Formatted label
 *
 * @example
 * formatEnumLabel('GLUTEN_FREE') // 'Gluten Free'
 * formatEnumLabel('produce') // 'Produce'
 * formatEnumLabel('STORAGE_LOCATION') // 'Storage Location'
 */
export function formatEnumLabel(enumKey: string): string {
  return enumKey
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

/**
 * Gets all enum values with their formatted labels
 *
 * **Important:** The order of returned options depends on the definition order of enum members.
 * If you need a specific display order (e.g., alphabetical), the enum members must be defined
 * in that order, or the result should be sorted after calling this function.
 *
 * @param enumObject - The enum to process
 * @returns Array of objects with value and label properties, in enum definition order
 *
 * @example
 * enum Status { ACTIVE = 'active', PENDING = 'pending' }
 * getEnumOptions(Status)
 * // [{ value: 'active', label: 'Active' }, { value: 'pending', label: 'Pending' }]
 */
export function getEnumOptions<T extends Record<string, string>>(
  enumObject: T
): Array<{ value: T[keyof T]; label: string }> {
  return Object.entries(enumObject).map(([key, value]) => ({
    value: value as T[keyof T],
    label: formatEnumLabel(key),
  }))
}
