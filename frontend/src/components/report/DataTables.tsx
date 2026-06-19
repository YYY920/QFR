import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { RawRow } from '@/lib/report-data'

function fmt(v: number) {
  return v.toLocaleString('en-AU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

type Props = {
  rows: RawRow[]
  reviewThreshold: number
}

export function DataTables({ rows, reviewThreshold }: Props) {
  const reviewRows = rows
    .filter((r) => r.Confidence < reviewThreshold)
    .sort((a, b) => a.Confidence - b.Confidence)
    .slice(0, 200)

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Profit &amp; Loss Detail</CardTitle>
          <CardDescription>Filtered line-level P&amp;L records. Showing first 200 rows.</CardDescription>
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
          <CardDescription>Items below confidence {reviewThreshold.toFixed(2)}</CardDescription>
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
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reviewRows.map((r, i) => (
                    <TableRow key={i}>
                      <TableCell>{r.Type}</TableCell>
                      <TableCell>{r.Date}</TableCell>
                      <TableCell>{r.Contact}</TableCell>
                      <TableCell>{r.AccountName}</TableCell>
                      <TableCell>{r.MappedCategory}</TableCell>
                      <TableCell className="text-right">${fmt(r.Amount)}</TableCell>
                      <TableCell className="text-right">{r.Confidence.toFixed(2)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
