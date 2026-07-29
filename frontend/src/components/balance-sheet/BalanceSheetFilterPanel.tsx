'use client'

import { useRef, useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import type { BSFilterState } from '@/lib/balance-sheet-filter'

type Props = {
  filters: BSFilterState
  allAccounts: string[]
  onChange: (f: BSFilterState) => void
  onReset: () => void
}

function AccountDropdown({ filters, allAccounts, onChange }: {
  filters: BSFilterState
  allAccounts: string[]
  onChange: (f: BSFilterState) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  function toggleAccount(account: string) {
    const next = new Set(filters.selectedAccounts)
    if (next.has(account)) { next.delete(account) } else { next.add(account) }
    onChange({ ...filters, selectedAccounts: next })
  }

  const count = filters.selectedAccounts.size
  const label = count === 0 ? 'All accounts' : `${count} selected`

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm hover:bg-muted transition-colors"
      >
        <span>{label}</span>
        <ChevronDown className="size-3.5 text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-20 min-w-48 rounded-lg border bg-popover shadow-md p-1.5 flex flex-col gap-0.5 max-h-52 overflow-y-auto">
          {allAccounts.map((account) => (
            <label key={account} className="flex items-center gap-2 text-sm px-2 py-1 rounded hover:bg-muted cursor-pointer">
              <Checkbox
                checked={filters.selectedAccounts.has(account)}
                onCheckedChange={() => toggleAccount(account)}
              />
              {account}
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

export function BalanceSheetFilterPanel({ filters, allAccounts, onChange, onReset }: Props) {
  function set(partial: Partial<BSFilterState>) {
    onChange({ ...filters, ...partial })
  }

  return (
    <Card>
      <CardContent className="flex flex-wrap items-end gap-4 pt-4">
        <div className="flex flex-col gap-1">
          <Label htmlFor="bs-start" className="text-xs text-muted-foreground">Start date</Label>
          <Input
            id="bs-start"
            type="date"
            value={filters.startDate}
            onChange={(e) => set({ startDate: e.target.value })}
            className="w-40"
          />
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="bs-end" className="text-xs text-muted-foreground">End date</Label>
          <Input
            id="bs-end"
            type="date"
            value={filters.endDate}
            onChange={(e) => set({ endDate: e.target.value })}
            className="w-40"
          />
        </div>

        <div className="flex flex-col gap-1">
          <Label htmlFor="bs-search" className="text-xs text-muted-foreground">Search</Label>
          <Input
            id="bs-search"
            type="text"
            placeholder="Account name"
            value={filters.search}
            onChange={(e) => set({ search: e.target.value })}
            className="w-56"
          />
        </div>

        <div className="flex flex-col gap-2">
          <Label className="text-xs text-muted-foreground">Sections</Label>
          <div className="flex flex-wrap gap-3">
            <label className="flex items-center gap-1.5 text-sm cursor-pointer">
              <Checkbox checked={filters.showAssets} onCheckedChange={(c) => set({ showAssets: !!c })} /> Assets
            </label>
            <label className="flex items-center gap-1.5 text-sm cursor-pointer">
              <Checkbox checked={filters.showLiabilities} onCheckedChange={(c) => set({ showLiabilities: !!c })} /> Liabilities
            </label>
            <label className="flex items-center gap-1.5 text-sm cursor-pointer">
              <Checkbox checked={filters.showEquity} onCheckedChange={(c) => set({ showEquity: !!c })} /> Equity
            </label>
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <Label className="text-xs text-muted-foreground">Account filter</Label>
          <AccountDropdown filters={filters} allAccounts={allAccounts} onChange={onChange} />
        </div>

        <div className="ml-auto">
          <Button variant="outline" onClick={onReset}>Reset</Button>
        </div>
      </CardContent>
    </Card>
  )
}