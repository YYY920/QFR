import { describe, expect, it } from 'vitest'
import { CONNECTION_STEPS, connectionProgress } from './link-data'

describe('connectionProgress', () => {
  it('calculates and clamps whole-number progress', () => {
    expect(connectionProgress(0, 10)).toBe(0)
    expect(connectionProgress(5, 10)).toBe(50)
    expect(connectionProgress(11, 10)).toBe(100)
  })

  it('handles an empty workflow', () => {
    expect(connectionProgress(1, 0)).toBe(0)
  })
})

describe('connection workflows', () => {
  it('models the real Xero evidence pulls used by run_mvp', () => {
    const labels = CONNECTION_STEPS.xero.map((step) => step.label).join(' ')
    expect(labels).toContain('Profit & Loss')
    expect(labels).toContain('Opening and closing Balance Sheet')
    expect(labels).toContain('Bills and sales invoices')
    expect(labels).toContain('Manual and general journals')
    expect(labels).toContain('Payroll evidence')
  })

  it('includes the QuickBooks opening balance and line-record movement sources', () => {
    const labels = CONNECTION_STEPS.quickbooks.map((step) => step.label).join(' ')
    expect(labels).toContain('Opening and closing Balance Sheet')
    expect(labels).toContain('General Ledger')
  })
})
