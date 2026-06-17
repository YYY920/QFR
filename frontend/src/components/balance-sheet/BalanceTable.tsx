import { Fragment } from 'react'
import { cn } from '@/lib/utils'
import type { BalanceSheetData, BSLineItem } from '@/lib/balance-sheet-mock'

function fmtAUD(value: number): string {
  return new Intl.NumberFormat('en-AU', {
    style: 'currency',
    currency: 'AUD',
    minimumFractionDigits: 2,
  }).format(value)
}

function AmountCell({ value, className }: { value: number; className?: string }) {
  return (
    <td className={cn(
      'px-4 py-2 text-right tabular-nums',
      value < 0 ? 'text-red-600' : value > 0 ? 'text-green-600' : 'text-muted-foreground',
      className,
    )}>
      {fmtAUD(value)}
    </td>
  )
}

function ChangeCell({ current, prior }: { current: number; prior: number }) {
  const change = current - prior
  return (
    <td className={cn(
      'px-4 py-2 text-right tabular-nums',
      change < 0 ? 'text-red-600' : change > 0 ? 'text-green-600' : 'text-muted-foreground',
    )}>
      {fmtAUD(change)}
    </td>
  )
}

function SectionHeader({ title }: { title: string }) {
  return (
    <tr className="bg-slate-100">
      <td colSpan={4} className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-slate-600">
        {title}
      </td>
    </tr>
  )
}

function SubsectionHeader({ title }: { title: string }) {
  return (
    <tr>
      <td colSpan={4} className="px-6 py-1.5 text-xs font-medium text-muted-foreground">
        {title}
      </td>
    </tr>
  )
}

function LineItemRow({ item }: { item: BSLineItem }) {
  return (
    <tr className="hover:bg-slate-50">
      <td className="px-4 py-2 pl-10 text-sm">{item.name}</td>
      <AmountCell value={item.current} className="text-sm" />
      <AmountCell value={item.prior} className="text-sm" />
      <ChangeCell current={item.current} prior={item.prior} />
    </tr>
  )
}

function SummaryRow({ item }: { item: BSLineItem }) {
  return (
    <tr className="border-t">
      <td className="px-4 py-2 pl-6 text-sm font-medium">{item.name}</td>
      <AmountCell value={item.current} className="text-sm font-medium" />
      <AmountCell value={item.prior} className="text-sm font-medium" />
      <ChangeCell current={item.current} prior={item.prior} />
    </tr>
  )
}

function TotalRow({ item, className }: { item: BSLineItem; className?: string }) {
  return (
    <tr className={cn('border-t-2 border-slate-300', className)}>
      <td className="px-4 py-2.5 text-sm font-bold">{item.name}</td>
      <AmountCell value={item.current} className="text-sm font-bold" />
      <AmountCell value={item.prior} className="text-sm font-bold" />
      <ChangeCell current={item.current} prior={item.prior} />
    </tr>
  )
}

export function BalanceTable({ data }: { data: BalanceSheetData }) {
  return (
    <div className="overflow-hidden rounded-lg border">
      <table className="w-full">
        <thead>
          <tr className="border-b bg-slate-50">
            <th className="w-1/2 px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Account
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {data.asAt}
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {data.priorPeriod}
            </th>
            <th className="px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Change
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {/* ASSETS */}
          <SectionHeader title="Assets" />
          {data.assets.subsections.map((sub) => (
            <Fragment key={sub.title}>
              <SubsectionHeader title={sub.title} />
              {sub.items.map((item) => <LineItemRow key={item.name} item={item} />)}
              <SummaryRow item={sub.total} />
            </Fragment>
          ))}
          <TotalRow item={data.assets.total} />

          {/* LIABILITIES */}
          <SectionHeader title="Liabilities" />
          {data.liabilities.subsections.map((sub) => (
            <Fragment key={sub.title}>
              <SubsectionHeader title={sub.title} />
              {sub.items.map((item) => <LineItemRow key={item.name} item={item} />)}
              <SummaryRow item={sub.total} />
            </Fragment>
          ))}
          <TotalRow item={data.liabilities.total} />

          {/* NET ASSETS */}
          <TotalRow item={data.netAssets} className="border-t-2 border-slate-400 bg-slate-50" />

          {/* EQUITY */}
          <SectionHeader title="Equity" />
          {data.equity.items.map((item) => <LineItemRow key={item.name} item={item} />)}
          <TotalRow item={data.equity.total} />
        </tbody>
      </table>
    </div>
  )
}
