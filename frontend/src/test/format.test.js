import { describe, it, expect } from 'vitest'
import { rupees, rupeesShort, shortDate } from '../lib/format'

describe('rupees', () => {
  it('formats integer', () => {
    expect(rupees(1000)).toBe('₹1,000')
  })
  it('formats lakhs with Indian grouping', () => {
    expect(rupees(100000)).toBe('₹1,00,000')
  })
  it('formats negative', () => {
    expect(rupees(-500)).toBe('-₹500')
  })
  it('handles null', () => {
    expect(rupees(null)).toBe('—')
  })
  it('handles undefined', () => {
    expect(rupees(undefined)).toBe('—')
  })
  it('handles NaN', () => {
    expect(rupees(NaN)).toBe('—')
  })
  it('rounds to integer', () => {
    expect(rupees(1000.7)).toBe('₹1,001')
  })
})

describe('rupeesShort', () => {
  it('formats thousands', () => {
    expect(rupeesShort(12000)).toBe('₹12k')
  })
  it('formats 12.5k', () => {
    expect(rupeesShort(12500)).toBe('₹12.5k')
  })
  it('formats lakhs', () => {
    expect(rupeesShort(150000)).toBe('₹1.5L')
  })
  it('no suffix for small values', () => {
    expect(rupeesShort(500)).toBe('₹500')
  })
  it('formats negative thousands', () => {
    expect(rupeesShort(-5000)).toBe('-₹5k')
  })
})

describe('shortDate', () => {
  it('formats date with day and month', () => {
    const r = shortDate('2026-11-15')
    expect(r).toMatch(/15/)
    expect(r).toMatch(/Nov/)
  })
  it('formats Jan correctly', () => {
    const r = shortDate('2026-01-01')
    expect(r).toMatch(/1/)
    expect(r).toMatch(/Jan/)
  })
})
