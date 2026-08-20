export type DataSource = 'xero' | 'quickbooks'

export type ConnectionStep = {
  label: string
  detail: string
}

export const CONNECTION_STEPS: Record<DataSource, ConnectionStep[]> = {
  xero: [
    { label: 'Authorising Xero organisation', detail: 'Checking OAuth token and tenant access' },
    { label: 'Profit & Loss report', detail: 'Loading the selected reporting period' },
    { label: 'Opening and closing Balance Sheet', detail: 'Loading both balance snapshots' },
    { label: 'Chart of Accounts', detail: 'Reading account codes, classes and reporting fields' },
    { label: 'Bills and sales invoices', detail: 'Loading full line-item detail across all pages' },
    { label: 'Bank transactions and transfers', detail: 'Loading spend, receive and transfer records' },
    { label: 'Credit notes and payments', detail: 'Loading adjustments and settlement evidence' },
    { label: 'Manual and general journals', detail: 'Loading posted accounting adjustments' },
    { label: 'Finance API Balance Sheet detail', detail: 'Loading supporting account-level balances' },
    { label: 'Payroll evidence', detail: 'Checking payroll report or pay-run availability' },
    { label: 'Normalising records', detail: 'Preparing line-level evidence for AI mapping' },
  ],
  quickbooks: [
    { label: 'Authorising QuickBooks company', detail: 'Checking OAuth token and company realm' },
    { label: 'Company and account profile', detail: 'Loading CompanyInfo and the full account list' },
    { label: 'Customers, vendors and items', detail: 'Loading source lists and product/service context' },
    { label: 'Invoices, bills and purchases', detail: 'Loading line-level sales and expense records' },
    { label: 'Payments, deposits and transfers', detail: 'Loading settlement and cash movement records' },
    { label: 'Credit and journal records', detail: 'Loading credit memos, vendor credits and journals' },
    { label: 'Profit & Loss reports', detail: 'Loading official summary and detailed P&L' },
    { label: 'Opening and closing Balance Sheet', detail: 'Loading the selected opening and endpoint' },
    { label: 'General Ledger', detail: 'Loading every record used in the Balance Sheet movement rebuild' },
    { label: 'Aging and balance reports', detail: 'Loading receivable, payable, customer and vendor balances' },
    { label: 'Validating downloaded data', detail: 'Checking report periods and preparing AI analysis' },
  ],
}

export function connectionProgress(completedSteps: number, totalSteps: number): number {
  if (totalSteps <= 0) return 0
  return Math.min(100, Math.max(0, Math.round((completedSteps / totalSteps) * 100)))
}
