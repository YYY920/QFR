// Real outstanding AR/AP items from Xero (dates shifted to 2025).
// [issued, due, amount] — aging is computed live at any selected date.
export type AgingItem = { issued: string; due: string; amount: number }
export const AR_ITEMS: AgingItem[] = [
  { issued: '2025-04-17', due: '2025-04-27', amount: 250.0 },
  { issued: '2025-05-07', due: '2025-05-23', amount: 660.0 },
  { issued: '2025-06-23', due: '2025-07-13', amount: 3850.0 },
  { issued: '2025-06-28', due: '2025-07-08', amount: 6187.5 },
  { issued: '2025-06-28', due: '2025-07-18', amount: 3080.0 },
  { issued: '2025-07-04', due: '2025-07-18', amount: 3200.0 },
  { issued: '2025-07-06', due: '2025-07-30', amount: 4200.0 },
  { issued: '2025-07-08', due: '2025-07-15', amount: 495.0 },
  { issued: '2025-07-08', due: '2025-07-28', amount: 825.0 },
  { issued: '2025-07-09', due: '2025-07-22', amount: 1650.0 },
  { issued: '2025-07-09', due: '2025-07-27', amount: 234.0 },
  { issued: '2025-07-09', due: '2025-07-15', amount: 396.0 },
  { issued: '2025-07-09', due: '2025-07-19', amount: 914.55 },
]
export const AP_ITEMS: AgingItem[] = [
  { issued: '2025-05-09', due: '2025-06-07', amount: 163.56 },
  { issued: '2025-05-28', due: '2025-06-11', amount: 2000.0 },
  { issued: '2025-06-26', due: '2025-07-08', amount: 54.13 },
  { issued: '2025-06-27', due: '2025-07-07', amount: 108.6 },
  { issued: '2025-06-28', due: '2025-07-11', amount: 2500.0 },
  { issued: '2025-06-28', due: '2025-07-13', amount: 1485.0 },
  { issued: '2025-07-03', due: '2025-07-28', amount: 2166.99 },
  { issued: '2025-07-03', due: '2025-07-13', amount: 130.0 },
  { issued: '2025-07-03', due: '2025-07-23', amount: 170.5 },
  { issued: '2025-07-08', due: '2025-07-23', amount: 840.0 },
  { issued: '2025-07-09', due: '2025-07-17', amount: 132.0 },
  { issued: '2025-07-09', due: '2025-07-15', amount: 242.0 },
]

// Aging buckets [0-30, 31-60, 61-90, 90+] as at endDate, items issued on/after startDate.
export function computeAging(items: AgingItem[], startDate: string, endDate: string): [number, number, number, number] {
  const buckets: [number, number, number, number] = [0, 0, 0, 0]
  const start = new Date(startDate)
  const end = new Date(endDate)
  for (const it of items) {
    const issued = new Date(it.issued)
    if (issued < start) continue
    if (issued > end) continue
    const due = new Date(it.due)
    const days = Math.floor((end.getTime() - due.getTime()) / 86400000)
    if (days <= 30) buckets[0] += it.amount
    else if (days <= 60) buckets[1] += it.amount
    else if (days <= 90) buckets[2] += it.amount
    else buckets[3] += it.amount
  }
  return buckets.map((b) => Math.round(b * 100) / 100) as [number, number, number, number]
}
