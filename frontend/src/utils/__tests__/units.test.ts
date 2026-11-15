import { describe, it, expect } from 'vitest'
import { displayUnit } from '../units'

describe('displayUnit', () => {
  it('shortens the long unit names sources use', () => {
    expect(displayUnit('tablespoon')).toBe('tbsp')
    expect(displayUnit('Teaspoons')).toBe('tsp')
    expect(displayUnit('ounce')).toBe('oz')
    expect(displayUnit('pounds')).toBe('lb')
  })

  it('leaves other units as they are', () => {
    expect(displayUnit('cup')).toBe('cup')
    expect(displayUnit('clove')).toBe('clove')
    expect(displayUnit('tsp')).toBe('tsp')
  })

  it('returns an empty string for a missing unit', () => {
    expect(displayUnit('')).toBe('')
    expect(displayUnit(null)).toBe('')
    expect(displayUnit(undefined)).toBe('')
  })
})
