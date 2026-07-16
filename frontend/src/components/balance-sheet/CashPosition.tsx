'use client'

import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

const C = { blue: '#4361ee', teal: '#72efdd' }

// Illustrative monthly cash balance across 2025 (sample data, not from live Xero).
const CASH_TREND = [
  { month: 'Jan', cash: 42000 },
  { month: 'Feb', cash: 45500 },
  { month: 'Mar', cash: 41800 },
  { month: 'Apr', cash: 48200 },
  { month: 'May', cash: 52900 },
  { month: 'Jun', cash: 50100 },
  { month: 'Jul', cash: 55400 },
  { month: 'Aug', cash: 58800 },
  { month: 'Sep', cash: 56200 },
  { month: 'Oct', cash: 61500 },
  { month: 'Nov', cash: 64800 },
  { month: 'Dec', cash: 68200 },
]

function fmtAUD(value: number | string | readonly (number | string)[] | undefined) {
  if (value === undefined || Array.isArray(value)) return ''
  const amount = typeof value === 'string' ? Number(value) : value
  return amount.toLocaleString('en-AU', { style: 'currency', currency: 'AUD', maximumFractionDigits: 0 })
}

export function CashPosition() {
  const current = CASH_TREND[CASH_TREND.length - 1].cash
  const previous = CASH_TREND[CASH_TREND.length - 2].cash
  const delta = current - previous
  const deltaPct = ((delta / previous) * 100).toFixed(1)
  const up = delta >= 0

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* Cash Position headline */}
      <Card>
        <CardHeader className="pb-2 pt-4">
          <CardTitle className="text-sm font-semibold">Cash Position</CardTitle>
          <CardDescription>Illustrative — closing cash balance</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-bold">{fmtAUD(current)}</p>
          <p className={`mt-1 text-sm ${up ? 'text-emerald-600' : 'text-rose-600'}`}>
            {up ? '▲' : '▼'} {fmtAUD(Math.abs(delta))} ({deltaPct}%) vs last month
          </p>
        </CardContent>
      </Card>

      {/* Cash Trend chart */}
      <Card className="lg:col-span-2">
        <CardHeader className="pb-2 pt-4">
          <CardTitle className="text-sm font-semibold">Cash Trend</CardTitle>
          <CardDescription>Illustrative monthly cash movement across 2025.</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={CASH_TREND} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(Number(v) / 1000).toFixed(0)}k`} />
              <Tooltip formatter={fmtAUD} />
              <Line type="monotone" dataKey="cash" stroke={C.blue} strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  )
}