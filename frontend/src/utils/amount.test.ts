import { describe, it, expect } from 'vitest'
import { formatAmount, isToTaste } from './amount'

describe('formatAmount', () => {
  it('writes an amount with its unit', () => {
    expect(formatAmount(2, 'tbsp')).toBe('2 tbsp')
    expect(formatAmount(1.5, 'cup')).toBe('1.5 cup')
    expect(formatAmount(0.333333, 'cup')).toBe('0.33 cup')
  })

  it('leaves out a plain count', () => {
    expect(formatAmount(3, 'count')).toBe('3')
    expect(formatAmount(2, '')).toBe('2')
    expect(formatAmount(1, 'unit')).toBe('1')
  })

  it('says "to taste" for the importer\'s no-amount marker', () => {
    expect(isToTaste(0.001)).toBe(true)
    expect(formatAmount(0.001, '')).toBe('to taste')
    expect(formatAmount(5, 'clove', true)).toBe('to taste')
    expect(isToTaste(0.5)).toBe(false)
  })
})
