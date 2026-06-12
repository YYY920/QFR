import { BALANCE_SHEET_DATA } from '@/lib/balance-sheet-mock'
import { SummaryCards } from '@/components/balance-sheet/SummaryCards'
import { BalanceTable } from '@/components/balance-sheet/BalanceTable'

export default function BalanceSheetPage() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Balance Sheet</h1>
        <p className="text-sm text-muted-foreground">
          {BALANCE_SHEET_DATA.company} — As at {BALANCE_SHEET_DATA.asAt}
        </p>
      </div>
      <div className="flex flex-col gap-5">
        <SummaryCards data={BALANCE_SHEET_DATA} />
        <BalanceTable data={BALANCE_SHEET_DATA} />
      </div>
    </main>
  )
}
