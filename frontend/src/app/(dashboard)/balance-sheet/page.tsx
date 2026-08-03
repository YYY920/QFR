'use client'
import { useMemo, useState } from 'react'
import { BALANCE_SHEET_DATA } from '@/lib/balance-sheet-mock'
import { filterBalanceSheet, defaultBSFilters, allAccountNames, type BSFilterState } from '@/lib/balance-sheet-filter'
import { BalanceSheetFilterPanel } from '@/components/balance-sheet/BalanceSheetFilterPanel'
import { SummaryCards } from '@/components/balance-sheet/SummaryCards'
import { BalanceTable } from '@/components/balance-sheet/BalanceTable'
import { FinancialAnalysisTables } from '@/components/balance-sheet/FinancialAnalysisTables'
import { BalanceSheetFigures } from '@/components/balance-sheet/BalanceSheetFigures'
import { CashPosition } from '@/components/balance-sheet/CashPosition'
import { AgingAnalysis } from '@/components/balance-sheet/AgingAnalysis'
import { periodForDate, buildBalanceSheet } from '@/lib/balance-sheet-periods'

export default function BalanceSheetPage() {
  const [filters, setFilters] = useState<BSFilterState>(defaultBSFilters)
  const period = useMemo(() => periodForDate(filters.endDate), [filters.endDate])
  const baseData = useMemo(() => buildBalanceSheet(period, '31 Dec 2024'), [period])
  const data = useMemo(() => filterBalanceSheet(baseData, filters), [baseData, filters])

  return (
    <main className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">Balance Sheet</h1>
        <p className="text-sm text-muted-foreground">
          {BALANCE_SHEET_DATA.company} — As at {BALANCE_SHEET_DATA.asAt}
        </p>
      </div>
      <div className="flex flex-col gap-5">
        <BalanceSheetFilterPanel
        filters={filters}
        data={baseData}
        onChange={setFilters}
        onReset={() => setFilters(defaultBSFilters())}
      />
        <CashPosition startDate={filters.startDate} endDate={filters.endDate} />
        <SummaryCards data={data} />
        <BalanceSheetFigures data={data} />
        <FinancialAnalysisTables data={data} />
        <AgingAnalysis startDate={filters.startDate} endDate={filters.endDate} />
        <BalanceTable data={data} />
      </div>
    </main>
  )
}