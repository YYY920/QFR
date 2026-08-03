'use client'

import { useRef, useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { BSFilterState } from '@/lib/balance-sheet-filter'
import type { BalanceSheetData } from '@/lib/balance-sheet-mock'

type Props = {
  filters: BSFilterState
  data: BalanceSheetData
  onChange: (f: BSFilterState) => void
  onReset: () => void
}

type Sub = { title: string; items: string[] }
type Group = { section: string; subs: Sub[]; allItems: string[] }

function getGroups(data: BalanceSheetData): Group[] {
  const mk = (section: string, subs: Sub[]): Group => ({
    section,
    subs,
    allItems: subs.flatMap((s) => s.items),
  })
  return [
    mk('Assets', data.assets.subsections.map((s) => ({ title: s.title, items: s.items.map((i) => i.name) }))),
    mk('Liabilities', data.liabilities.subsections.map((s) => ({ title: s.title, items: s.items.map((i) => i.name) }))),
    mk('Equity', [{ title: 'Equity', items: data.equity.items.map((i) => i.name) }]),
  ]
}

function LineItemsDropdown({ filters, data, onChange }: { filters: BSFilterState; data: BalanceSheetData; onChange: (f: BSFilterState) => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const groups = getGroups(data)
  const allItems = groups.flatMap((g) => g.allItems)
  const selected = filters.selectedAccounts

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const isChecked = (item: string) => selected.size === 0 || selected.has(item)

  function apply(next: Set<string>) {
    onChange({ ...filters, selectedAccounts: next.size === allItems.length ? new Set() : next })
  }

  function toggleItem(item: string) {
    const base = selected.size === 0 ? new Set(allItems) : new Set(selected)
    if (base.has(item)) base.delete(item)
    else base.add(item)
    apply(base)
  }

  function groupState(items: string[]): boolean | 'indeterminate' {
    const shown = items.filter(isChecked).length
    if (shown === items.length) return true
    if (shown === 0) return false
    return 'indeterminate'
  }

  function toggleGroup(items: string[]) {
    const base = selected.size === 0 ? new Set(allItems) : new Set(selected)
    const allOn = items.every((i) => base.has(i))
    if (allOn) items.forEach((i) => base.delete(i))
    else items.forEach((i) => base.add(i))
    apply(base)
  }

  const count = selected.size === 0 ? allItems.length : selected.size
  const label = selected.size === 0 ? 'All line items' : `${count} selected`

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center justify-between gap-2 h-9 min-w-44 rounded-lg border border-input bg-transparent px-3 text-sm hover:bg-muted transition-colors"
      >
        <span>{label}</span>
        <ChevronDown className="size-4 text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-30 w-72 rounded-lg border bg-popover shadow-lg p-2 flex flex-col gap-2 max-h-96 overflow-y-auto">
          {groups.map((g) => (
            <div key={g.section} className="flex flex-col gap-0.5">
              <label className="flex items-center gap-2 text-sm font-semibold px-1.5 py-1 rounded hover:bg-muted cursor-pointer">
                <Checkbox checked={groupState(g.allItems)} onCheckedChange={() => toggleGroup(g.allItems)} />
                {g.section}
              </label>
              {g.subs.map((sub) => (
                <div key={sub.title} className="flex flex-col gap-0.5">
                  {sub.title !== g.section && (
                    <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground pl-6 pr-1.5 py-0.5 rounded hover:bg-muted cursor-pointer">
                      <Checkbox checked={groupState(sub.items)} onCheckedChange={() => toggleGroup(sub.items)} />
                      {sub.title}
                    </label>
                  )}
                  {sub.items.map((item) => (
                    <label key={item} className="flex items-center gap-2 text-sm pl-11 pr-1.5 py-0.5 rounded hover:bg-muted cursor-pointer">
                      <Checkbox checked={isChecked(item)} onCheckedChange={() => toggleItem(item)} />
                      {item}
                    </label>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function BalanceSheetFilterPanel({ filters, data, onChange, onReset }: Props) {
  function set(partial: Partial<BSFilterState>) {
    onChange({ ...filters, ...partial })
  }

  return (
    <Card>
      <CardContent className="flex flex-wrap items-end gap-4 pt-4">
        <div className="flex flex-col gap-1">
          <Label htmlFor="bs-start" className="text-xs text-muted-foreground">Start date</Label>
          <Input id="bs-start" type="date" value={filters.startDate} onChange={(e) => set({ startDate: e.target.value })} className="w-40" />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="bs-end" className="text-xs text-muted-foreground">End date</Label>
          <Input id="bs-end" type="date" value={filters.endDate} onChange={(e) => set({ endDate: e.target.value })} className="w-40" />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="bs-search" className="text-xs text-muted-foreground">Search</Label>
          <Input id="bs-search" type="text" placeholder="Account name" value={filters.search} onChange={(e) => set({ search: e.target.value })} className="w-52" />
        </div>
        <div className="flex flex-col gap-1">
          <Label className="text-xs text-muted-foreground">Line items</Label>
          <LineItemsDropdown filters={filters} data={data} onChange={onChange} />
        </div>
        <div className="ml-auto">
          <Button variant="outline" onClick={onReset}>Reset</Button>
        </div>
      </CardContent>
    </Card>
  )
}