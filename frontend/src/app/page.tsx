'use client'

import { useMemo, useState } from 'react'
import { REPORT_DATA } from '@/lib/report-data'
import { getFilteredRows, computeMetrics, type FilterState } from '@/lib/report-utils'
import { FilterPanel } from '@/components/report/FilterPanel'
import { MetricCards } from '@/components/report/MetricCards'
import { ChartsSection } from '@/components/report/ChartsSection'
import { DataTables } from '@/components/report/DataTables'

const ALL_TYPES = Array.from(new Set(REPORT_DATA.raw_data.map((r) => r.Type))).sort()

const DATE_RANGE = REPORT_DATA.raw_data.reduce(
  (acc, r) => ({ min: r.Date < acc.min ? r.Date : acc.min, max: r.Date > acc.max ? r.Date : acc.max }),
  { min: '9999-12-31', max: '0000-01-01' },
)

function defaultFilters(): FilterState {
  return {
    startDate: DATE_RANGE.min,
    endDate: DATE_RANGE.max,
    search: '',
    topN: 8,
    selectedTypes: new Set(),
    onlyUnmapped: false,
    onlyLowConf: false,
  }
}

export default function Home() {
  const [filters, setFilters] = useState<FilterState>(defaultFilters)
  const filteredRows = useMemo(() => getFilteredRows(REPORT_DATA.raw_data, filters), [filters])
  const metrics = useMemo(() => computeMetrics(filteredRows), [filteredRows])

  return (
    <main className="mx-auto max-w-screen-xl px-4 py-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold">AI Mapping Report</h1>
        <p className="text-sm text-muted-foreground">
          Generated from Xero P&amp;L and transaction mapping {REPORT_DATA.meta.report_from} to {REPORT_DATA.meta.report_to}
        </p>
      </div>
      <div className="flex flex-col gap-5">
        <FilterPanel filters={filters} allTypes={ALL_TYPES} onChange={setFilters} onReset={() => setFilters(defaultFilters())} />
        <MetricCards metrics={metrics} />
        <ChartsSection rows={filteredRows} topN={filters.topN} incomeCategories={REPORT_DATA.income_categories} />
        <DataTables rows={filteredRows} balanceSheetData={REPORT_DATA.balance_sheet_data} balanceSheetSummary={REPORT_DATA.balance_sheet_summary} reviewThreshold={REPORT_DATA.review_threshold} />
      </div>
    </main>
  )
}
