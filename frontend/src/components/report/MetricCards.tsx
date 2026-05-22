import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { Metrics } from '@/lib/report-utils'

function fmt(value: number): string {
  return value.toLocaleString('en-AU', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

export function MetricCards({ metrics }: { metrics: Metrics }) {
  const tiles = [
    { label: 'Total Lines', value: metrics.totalLines.toLocaleString() },
    { label: 'Total Amount', value: `$${fmt(metrics.totalAmount)}` },
    { label: 'Mapped / Total', value: `${metrics.mapped} / ${metrics.totalLines}` },
    { label: 'Avg Confidence', value: metrics.avgConfidence.toFixed(2) },
  ]
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {tiles.map((tile) => (
        <Card key={tile.label}>
          <CardHeader className="pb-1 pt-4">
            <CardTitle className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {tile.label}
            </CardTitle>
          </CardHeader>
          <CardContent className="pb-4">
            <p className="text-2xl font-bold">{tile.value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
