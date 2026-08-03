'use client'

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { AR_ITEMS, AP_ITEMS, computeAging } from '@/lib/balance-sheet-aging'

const C = { blue: '#4361ee', pink: '#f72585' }

function fmtDate(iso: string): string {
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

function fmtAUD(value: number | string | readonly (number | string)[] | undefined) {
  if (value === undefined || Array.isArray(value)) return ''
  const amount = typeof value === 'string' ? Number(value) : value
  return amount.toLocaleString('en-AU', { style: 'currency', currency: 'AUD', maximumFractionDigits: 0 })
}

export function AgingAnalysis({ startDate, endDate }: { startDate: string; endDate: string }) {
  const ar = computeAging(AR_ITEMS, startDate, endDate)
  const ap = computeAging(AP_ITEMS, startDate, endDate)

  const buckets = ['0–30 days', '31–60 days', '61–90 days', '90+ days']
  const data = buckets.map((bucket, i) => ({ bucket, receivables: ar[i], payables: ap[i] }))

  return (
    <Card>
      <CardHeader className="pb-2 pt-4">
        <CardTitle className="text-sm font-semibold">Receivables &amp; Payables Aging</CardTitle>
        <CardDescription>
          Aging as at {fmtDate(endDate)}, for invoices issued from {fmtDate(startDate)}.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(Number(v) / 1000).toFixed(0)}k`} />
            <Tooltip formatter={fmtAUD} />
            <Legend />
            <Bar dataKey="receivables" name="Receivables" fill={C.blue} radius={[3, 3, 0, 0]} />
            <Bar dataKey="payables" name="Payables" fill={C.pink} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  )
}