import { describe, it, expect } from 'vitest'
import { checkCredentials } from './auth'

describe('checkCredentials', () => {
  it('returns true for correct credentials', () => {
    expect(checkCredentials('admin', 'admin123')).toBe(true)
  })
  it('returns false for wrong password', () => {
    expect(checkCredentials('admin', 'wrong')).toBe(false)
  })
  it('returns false for wrong username', () => {
    expect(checkCredentials('user', 'admin123')).toBe(false)
  })
  it('returns false for empty credentials', () => {
    expect(checkCredentials('', '')).toBe(false)
  })
})
