'use client'

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const C = { blue: '#4361ee', pink: '#f72585' }

// Illustrative AR/AP aging buckets (sample data, not from live Xero).
const AGING = [
  { bucket: '0–30 days', receivables: 38200, payables: 24100 },
  { bucket: '31–60 days', receivables: 21500, payables: 15800 },
  { bucket: '61–90 days', receivables: 9400, payables: 6200 },
  { bucket: '90+ days', receivables: 4100, payables: 8700 },
]

function fmtAUD(value: number | string | readonly (number | string)[] | undefined) {
  if (value === undefined || Array.isArray(value)) return ''
  const amount = typeof value === 'string' ? Number(value) : value
  return amount.toLocaleString('en-AU', { style: 'currency', currency: 'AUD', maximumFractionDigits: 0 })
}

export function AgingAnalysis() {
  return (
    <Card>
      <CardHeader className="pb-2 pt-4">
        <CardTitle className="text-sm font-semibold">Receivables &amp; Payables Aging</CardTitle>
        <CardDescription>Illustrative — outstanding balances by age bucket.</CardDescription>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={AGING} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
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