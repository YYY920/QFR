'use client'

import type { ReactNode } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { buildCategoryChartData, buildMonthlyChartData, buildConfidenceHistogram } from '@/lib/report-utils'
import type { RawRow } from '@/lib/report-data'

const C = { blue: '#4cc9f0', indigo: '#4361ee', pink: '#f72585', teal: '#72efdd', dark: '#2a344d' }

function fmt(v: number | string | readonly (number | string)[] | undefined) {
  if (v === undefined || Array.isArray(v)) return ''
  const n = typeof v === 'string' ? parseFloat(v as string) : (v as number)
  return `$${n.toLocaleString('en-AU', { minimumFractionDigits: 2 })}`
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader className="pb-2 pt-4">
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

export function ChartsSection({ rows, topN, incomeCategories }: { rows: RawRow[]; topN: number; incomeCategories: string[] }) {
  const catData = buildCategoryChartData(rows, topN)
  const top10Data = buildCategoryChartData(rows, Math.min(10, topN))
  const monthlyData = buildMonthlyChartData(rows, incomeCategories)
  const histData = buildConfidenceHistogram(rows)

  const totalAmt = rows.reduce((s, r) => s + r.Amount, 0)
  const unmappedAmt = rows.filter((r) => r.MappedCategory === 'Unmapped').reduce((s, r) => s + r.Amount, 0)
  const donutData = [
    { name: 'Mapped', value: Math.abs(totalAmt - unmappedAmt) },
    { name: 'Unmapped', value: Math.abs(unmappedAmt) },
  ]

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

      <ChartCard title={`Top ${Math.min(10, topN)} Categories`}>
        <ResponsiveContainer width="100%" height={380}>
          <BarChart data={top10Data} margin={{ left: 8, right: 8, top: 8, bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 10, angle: -25, textAnchor: 'end' }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip formatter={fmt} />
            <Bar dataKey="value" fill={C.indigo} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Mapped vs Unmapped">
        <ResponsiveContainer width="100%" height={380}>
          <PieChart>
            <Pie data={donutData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius="45%" outerRadius="70%" label={({ name, percent }: { name?: string; percent?: number }) => `${name ?? ''} ${((percent ?? 0) * 100).toFixed(0)}%`}>
              <Cell fill={C.blue} />
              <Cell fill={C.dark} />
            </Pie>
            <Tooltip formatter={fmt} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="AI Confidence Distribution">
        <ResponsiveContainer width="100%" height={380}>
          <BarChart data={histData} margin={{ left: 8, right: 8, top: 8, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="bin" tick={{ fontSize: 10 }} />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" fill={C.teal} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Monthly Income vs Expense">
        <ResponsiveContainer width="100%" height={380}>
          <BarChart data={monthlyData} margin={{ left: 8, right: 8, top: 8, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 10, angle: -30, textAnchor: 'end' }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip formatter={fmt} />
            <Legend />
            <Bar dataKey="income" name="Income" fill={C.blue} radius={[3, 3, 0, 0]} />
            <Bar dataKey="expense" name="Expense" fill={C.pink} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>

      <ChartCard title="Payroll Summary">
        <div className="flex h-[380px] items-center justify-center text-sm text-muted-foreground">
          No payroll data returned.
        </div>
      </ChartCard>
    </div>
  )
}
