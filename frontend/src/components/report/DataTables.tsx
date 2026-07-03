'use client'

import { useMemo, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { ExportControls, type ExportMode } from '@/components/ExportControls'
import { exportRowsToExcel, type ExportRow } from '@/lib/excel-export'
import type { RawRow } from '@/lib/report-data'

function fmt(v: number) {
  return v.toLocaleString('en-AU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

type Props = {
  rows: RawRow[]
  reviewThreshold: number
}

type ReviewStatus = 'Pending' | 'Approved' | 'Needs changes' | 'Rejected'
type ReviewState = Record<string, { status: ReviewStatus; note: string }>

function rowKey(row: RawRow, index: number): string {
  return [
    row.Type,
    row.InvoiceNumber,
    row.Date,
    row.Contact,
    row.AccountCode,
    row.Description,
    index,
  ].join('|')
}

export function DataTables({ rows, reviewThreshold }: Props) {
  const [reviewState, setReviewState] = useState<ReviewState>({})
  const [exportMode, setExportMode] = useState<ExportMode>('summary')
  const rowsWithKeys = useMemo(() => rows.map((row, index) => ({ row, key: rowKey(row, index) })), [rows])
  const reviewRows = rowsWithKeys
    .filter(({ row }) => row.Confidence < reviewThreshold)
    .sort((a, b) => a.row.Confidence - b.row.Confidence)
    .slice(0, 200)

  function updateReview(key: string, patch: Partial<ReviewState[string]>) {
    setReviewState((current) => ({
      ...current,
      [key]: {
        status: current[key]?.status ?? 'Pending',
        note: current[key]?.note ?? '',
        ...patch,
      },
    }))
  }

  function reviewFor(key: string): ReviewState[string] {
    return reviewState[key] ?? { status: 'Pending', note: '' }
  }

  function buildSummaryExport(): ExportRow[] {
    const grouped = new Map<string, {
      category: string
      lines: number
      amount: number
      budget: number
      confidenceTotal: number
      lowConfidence: number
      approved: number
      needsChanges: number
      rejected: number
    }>()

    rowsWithKeys.forEach(({ row, key }) => {
      const category = row.MappedCategory || 'Unmapped'
      const item = grouped.get(category) ?? {
        category,
        lines: 0,
        amount: 0,
        budget: 0,
        confidenceTotal: 0,
        lowConfidence: 0,
        approved: 0,
        needsChanges: 0,
        rejected: 0,
      }
      const review = reviewFor(key)
      item.lines += 1
      item.amount += row.Amount
      item.budget += row.Budget ?? 0
      item.confidenceTotal += row.Confidence
      if (row.Confidence < reviewThreshold) item.lowConfidence += 1
      if (review.status === 'Approved') item.approved += 1
      if (review.status === 'Needs changes') item.needsChanges += 1
      if (review.status === 'Rejected') item.rejected += 1
      grouped.set(category, item)
    })

    return Array.from(grouped.values())
      .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount))
      .map((item) => ({
        Category: item.category,
        Lines: item.lines,
        Amount: item.amount,
        Budget: item.budget || null,
        'Average Confidence': item.lines ? item.confidenceTotal / item.lines : 0,
        'Low Confidence Lines': item.lowConfidence,
        Approved: item.approved,
        'Needs Changes': item.needsChanges,
        Rejected: item.rejected,
      }))
  }

  function buildLineExport(): ExportRow[] {
    return rowsWithKeys.map(({ row, key }) => {
      const review = reviewFor(key)
      return {
        Type: row.Type,
        Invoice: String(row.InvoiceNumber),
        Date: row.Date,
        Contact: row.Contact,
        'Account Code': row.AccountCode,
        Account: row.AccountName,
        Description: row.Description,
        Category: row.MappedCategory,
        Amount: row.Amount,
        Budget: row.Budget,
        Confidence: row.Confidence,
        Reason: row.Reason,
        'Review Status': review.status,
        'Reviewer Note': review.note,
      }
    })
  }

  function handleExport() {
    const isSummary = exportMode === 'summary'
    exportRowsToExcel(
      isSummary ? buildSummaryExport() : buildLineExport(),
      isSummary ? 'profit-loss-summary.xlsx' : 'profit-loss-by-line.xlsx',
      isSummary ? 'P&L Summary' : 'P&L By Line',
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>Profit &amp; Loss Detail</CardTitle>
            <CardDescription>Filtered line-level P&amp;L records. Showing first 200 rows.</CardDescription>
          </div>
          <ExportControls mode={exportMode} onModeChange={setExportMode} onExport={handleExport} />
        </CardHeader>
        <CardContent>
          <div className="max-h-80 overflow-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead><TableHead>Invoice</TableHead><TableHead>Date</TableHead>
                  <TableHead>Contact</TableHead><TableHead>Account</TableHead><TableHead>Category</TableHead>
                  <TableHead className="text-right">Amount</TableHead><TableHead className="text-right">Budget</TableHead><TableHead>Reason</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.slice(0, 200).map((r, i) => (
                  <TableRow key={i}>
                    <TableCell>{r.Type}</TableCell>
                    <TableCell className="max-w-[100px] truncate">{String(r.InvoiceNumber)}</TableCell>
                    <TableCell>{r.Date}</TableCell>
                    <TableCell>{r.Contact}</TableCell>
                    <TableCell>{r.AccountName}</TableCell>
                    <TableCell>{r.MappedCategory}</TableCell>
                    <TableCell className="text-right">${fmt(r.Amount)}</TableCell>
                    <TableCell className="text-right">{r.Budget !== undefined ? `$${fmt(r.Budget)}` : '—'}</TableCell>
                    <TableCell className="max-w-[200px] truncate text-xs text-muted-foreground">{r.Reason}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Human-in-the-loop Review (Low Confidence)</CardTitle>
          <CardDescription>
            Items below confidence {reviewThreshold.toFixed(2)}. Review decisions stay in this browser session and are included in exports.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="max-h-80 overflow-auto">
            {reviewRows.length === 0 ? (
              <p className="text-sm text-muted-foreground">No items below threshold.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead><TableHead>Date</TableHead><TableHead>Contact</TableHead>
                    <TableHead>Account</TableHead><TableHead>Category</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                    <TableHead className="text-right">Confidence</TableHead>
                    <TableHead>Decision</TableHead>
                    <TableHead>Reviewer Note</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reviewRows.map(({ row: r, key }) => {
                    const review = reviewFor(key)
                    return (
                    <TableRow key={key}>
                      <TableCell>{r.Type}</TableCell>
                      <TableCell>{r.Date}</TableCell>
                      <TableCell>{r.Contact}</TableCell>
                      <TableCell>{r.AccountName}</TableCell>
                      <TableCell>{r.MappedCategory}</TableCell>
                      <TableCell className="text-right">${fmt(r.Amount)}</TableCell>
                      <TableCell className="text-right">{r.Confidence.toFixed(2)}</TableCell>
                      <TableCell>
                        <div className="flex min-w-40 flex-wrap gap-1">
                          {(['Approved', 'Needs changes', 'Rejected'] as ReviewStatus[]).map((status) => (
                            <Button
                              key={status}
                              type="button"
                              size="xs"
                              variant={review.status === status ? 'default' : 'outline'}
                              onClick={() => updateReview(key, { status })}
                              className={review.status === status ? 'bg-blue-700 text-white hover:bg-blue-600' : undefined}
                            >
                              {status}
                            </Button>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell>
                        <input
                          value={review.note}
                          onChange={(event) => updateReview(key, { note: event.target.value })}
                          placeholder="Add note..."
                          className="h-8 min-w-48 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                        />
                      </TableCell>
                    </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
