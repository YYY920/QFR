'use client'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Checkbox } from '@/components/ui/checkbox'
import { Card, CardContent } from '@/components/ui/card'
import type { FilterState } from '@/lib/report-utils'

type Props = {
  filters: FilterState
  allTypes: string[]
  onChange: (f: FilterState) => void
  onReset: () => void
}

export function FilterPanel({ filters, allTypes, onChange, onReset }: Props) {
  function set(partial: Partial<FilterState>) {
    onChange({ ...filters, ...partial })
  }

  function toggleType(type: string) {
    const next = new Set(filters.selectedTypes)
    if (next.has(type)) { next.delete(type) } else { next.add(type) }
    set({ selectedTypes: next })
  }

  return (
    <Card>
      <CardContent className="flex flex-wrap items-end gap-4 pt-4">
        <div className="flex flex-col gap-1">
          <Label htmlFor="start-date" className="text-xs text-muted-foreground">Start date</Label>
          <Input id="start-date" type="date" value={filters.startDate} onChange={(e) => set({ startDate: e.target.value })} className="w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="end-date" className="text-xs text-muted-foreground">End date</Label>
          <Input id="end-date" type="date" value={filters.endDate} onChange={(e) => set({ endDate: e.target.value })} className="w-36" />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="search" className="text-xs text-muted-foreground">Search</Label>
          <Input id="search" type="text" placeholder="Contact / description / category" value={filters.search} onChange={(e) => set({ search: e.target.value })} className="w-56" />
        </div>
        <div className="flex flex-col gap-2 min-w-[140px]">
          <Label className="text-xs text-muted-foreground">
            Top N: <span className="font-semibold text-foreground">{filters.topN}</span>
          </Label>
          <Slider min={5} max={25} step={1} value={[filters.topN]} onValueChange={(v) => set({ topN: Array.isArray(v) ? (v as number[])[0] : (v as number) })} className="w-32" />
        </div>
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-muted-foreground">Type filter</Label>
          <div className="flex flex-wrap gap-2">
            {allTypes.map((type) => (
              <label key={type} className="flex items-center gap-1.5 text-sm cursor-pointer">
                <Checkbox
                  checked={filters.selectedTypes.size === 0 || filters.selectedTypes.has(type)}
                  onCheckedChange={() => toggleType(type)}
                />
                {type}
              </label>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <Label className="text-xs text-muted-foreground">Quick filters</Label>
          <div className="flex gap-3">
            <label className="flex items-center gap-1.5 text-sm cursor-pointer">
              <Checkbox checked={filters.onlyUnmapped} onCheckedChange={(c) => set({ onlyUnmapped: !!c })} />
              Unmapped only
            </label>
            <label className="flex items-center gap-1.5 text-sm cursor-pointer">
              <Checkbox checked={filters.onlyLowConf} onCheckedChange={(c) => set({ onlyLowConf: !!c })} />
              Low confidence
            </label>
          </div>
        </div>
        <div className="ml-auto">
          <Button variant="outline" onClick={onReset}>Reset</Button>
        </div>
      </CardContent>
    </Card>
  )
}
