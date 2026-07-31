'use client'

import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceArea } from 'recharts'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { BS_PERIODS, periodForDate } from '@/lib/balance-sheet-periods'

const C = { blue: '#4361ee', black: '#111111', highlight: 'rgba(67,97,238,0.10)' }

function fmtAUD(value: number | string | readonly (number | string)[] | undefined) {
  if (value === undefined || Array.isArray(value)) return ''
  const amount = typeof value === 'string' ? Number(value) : value
  return amount.toLocaleString('en-AU', { style: 'currency', currency: 'AUD', maximumFractionDigits: 0 })
}

export function CashPosition({ startDate, endDate }: { startDate: string; endDate: string }) {
  const startP = periodForDate(startDate)
  const endP = periodForDate(endDate)
  const startIdx = BS_PERIODS.findIndex((p) => p.key === startP.key)
  const endIdx = BS_PERIODS.findIndex((p) => p.key === endP.key)
  const startMonth = startP.label.split(' ')[1]
  const endMonth = endP.label.split(' ')[1]

  // Split into two non-overlapping series: blue = outside selection, black = inside.
  // Boundary points appear in BOTH so the segments connect with no gap.
  const chartData = BS_PERIODS.map((p, i) => {
    const inRange = i >= startIdx && i <= endIdx
    const onBoundary = i === startIdx || i === endIdx
    return {
      month: p.label.split(' ')[1],
      cash: p.bank,
      blue: !inRange || onBoundary ? p.bank : null,
      black: inRange ? p.bank : null,
    }
  })

  const current = endP.bank
  const previous = endIdx > 0 ? BS_PERIODS[endIdx - 1].bank : current
  const delta = current - previous
  const deltaPct = previous !== 0 ? ((delta / Math.abs(previous)) * 100).toFixed(1) : '0.0'
  const up = delta >= 0

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <Card>
        <CardHeader className="pb-2 pt-4">
          <CardTitle className="text-sm font-semibold">Cash Position</CardTitle>
          <CardDescription>Illustrative — cash balance as at {endP.label}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-3xl font-bold">{fmtAUD(current)}</p>
          <p className={`mt-1 text-sm ${up ? 'text-emerald-600' : 'text-rose-600'}`}>
            {up ? '▲' : '▼'} {fmtAUD(Math.abs(delta))} ({deltaPct}%) vs prior month
          </p>
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader className="pb-2 pt-4">
          <CardTitle className="text-sm font-semibold">Cash Trend</CardTitle>
          <CardDescription>Illustrative — 2025, selected range highlighted.</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <ReferenceArea x1={startMonth} x2={endMonth} fill={C.highlight} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(Number(v) / 1000).toFixed(0)}k`} />
              <Tooltip formatter={fmtAUD} />
              <Line type="monotone" dataKey="blue" stroke={C.blue} strokeWidth={2.5} dot={{ r: 3, fill: C.blue }} connectNulls={false} isAnimationActive={false} />
              <Line type="monotone" dataKey="black" stroke={C.black} strokeWidth={2.5} dot={{ r: 3, fill: C.black }} connectNulls={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  )
}