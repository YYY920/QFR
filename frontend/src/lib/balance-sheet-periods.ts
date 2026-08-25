export type BSPeriod = {
  key: string
  label: string
  bank: number
  receivables: number
  fixedAssets: number
  payables: number
  gst: number
  arAging: [number, number, number, number]
  apAging: [number, number, number, number]
}

// Illustrative multi-period balance sheet data for 2025.
// December closing anchors to the real Xero figures (bank, GST).
export const BS_PERIODS: BSPeriod[] = [
  { key: '2025-01', label: '31 Jan 2025', bank: 42000, receivables: 18000, fixedAssets: 24500, payables: 12000, gst: 1450, arAging: [9900, 4500, 2340, 1260], apAging: [6600, 3000, 1560, 840] },
  { key: '2025-02', label: '28 Feb 2025', bank: 45500, receivables: 19500, fixedAssets: 24500, payables: 13200, gst: 1600, arAging: [10725, 4875, 2535, 1365], apAging: [7260, 3300, 1716, 924] },
  { key: '2025-03', label: '31 Mar 2025', bank: 41800, receivables: 22000, fixedAssets: 24200, payables: 14800, gst: 1380, arAging: [12100, 5500, 2860, 1540], apAging: [8140, 3700, 1924, 1036] },
  { key: '2025-04', label: '30 Apr 2025', bank: 38200, receivables: 24500, fixedAssets: 23900, payables: 16100, gst: 1250, arAging: [13475, 6125, 3185, 1715], apAging: [8855, 4025, 2093, 1127] },
  { key: '2025-05', label: '31 May 2025', bank: 31500, receivables: 26800, fixedAssets: 23600, payables: 17500, gst: 1100, arAging: [14740, 6700, 3484, 1876], apAging: [9625, 4375, 2275, 1225] },
  { key: '2025-06', label: '30 Jun 2025', bank: 24800, receivables: 28200, fixedAssets: 23300, payables: 18900, gst: 980, arAging: [15510, 7050, 3666, 1974], apAging: [10395, 4725, 2457, 1323] },
  { key: '2025-07', label: '31 Jul 2025', bank: 16200, receivables: 29500, fixedAssets: 23000, payables: 20200, gst: 890, arAging: [16225, 7375, 3835, 2065], apAging: [11110, 5050, 2626, 1414] },
  { key: '2025-08', label: '31 Aug 2025', bank: 8800, receivables: 31000, fixedAssets: 22700, payables: 21400, gst: 840, arAging: [17050, 7750, 4030, 2170], apAging: [11770, 5350, 2782, 1498] },
  { key: '2025-09', label: '30 Sep 2025', bank: 2200, receivables: 33200, fixedAssets: 22400, payables: 22600, gst: 810, arAging: [18260, 8300, 4316, 2324], apAging: [12430, 5650, 2938, 1582] },
  { key: '2025-10', label: '31 Oct 2025', bank: -3100, receivables: 35100, fixedAssets: 22100, payables: 23800, gst: 800, arAging: [19305, 8775, 4563, 2457], apAging: [13090, 5950, 3094, 1666] },
  { key: '2025-11', label: '30 Nov 2025', bank: -6200, receivables: 37000, fixedAssets: 21800, payables: 25100, gst: 795, arAging: [20350, 9250, 4810, 2590], apAging: [13805, 6275, 3263, 1757] },
  { key: '2025-12', label: '31 Dec 2025', bank: -8703.2, receivables: 38420, fixedAssets: 21500, payables: 26300, gst: 791.2, arAging: [21131, 9605, 4994.6, 2689.4], apAging: [14465, 6575, 3419, 1841] },
]

// Pick the period whose month is <= the selected end date (closing as-at).
export function periodForDate(endDate: string): BSPeriod {
  const target = endDate.slice(0, 7) // 'YYYY-MM'
  let chosen = BS_PERIODS[0]
  for (const p of BS_PERIODS) {
    if (p.key <= target) chosen = p
  }
  return chosen
}

export function periodForKey(key: string): BSPeriod {
  return BS_PERIODS.find((p) => p.key === key) ?? BS_PERIODS[BS_PERIODS.length - 1]
}

import type { BalanceSheetData } from './balance-sheet-mock'

// Build a full BalanceSheetData object from a period (so existing components work unchanged).
export function buildBalanceSheet(p: BSPeriod, priorLabel: string): BalanceSheetData {
  const receivables = p.receivables
  const totalAssets = p.bank + receivables + p.fixedAssets
  const totalLiab = p.payables + p.gst
  const netAssets = totalAssets - totalLiab

  return {
    company: 'Demo Company (AU)',
    currency: 'AUD',
    source: 'Xero',
    asAt: p.label,
    priorPeriod: priorLabel,
    assets: {
      subsections: [
        { title: 'Bank', items: [{ name: 'Business Bank Account', current: p.bank, prior: 0 }], total: { name: 'Total Bank', current: p.bank, prior: 0 } },
        { title: 'Current Assets', items: [{ name: 'Accounts Receivable', current: receivables, prior: 0 }], total: { name: 'Total Current Assets', current: receivables, prior: 0 } },
        { title: 'Fixed Assets', items: [{ name: 'Property, Plant & Equipment', current: p.fixedAssets, prior: 0 }], total: { name: 'Total Fixed Assets', current: p.fixedAssets, prior: 0 } },
      ],
      total: { name: 'Total Assets', current: totalAssets, prior: 0 },
    },
    liabilities: {
      subsections: [
        { title: 'Current Liabilities', items: [
          { name: 'Accounts Payable', current: p.payables, prior: 0 },
          { name: 'GST', current: p.gst, prior: 0 },
        ], total: { name: 'Total Current Liabilities', current: totalLiab, prior: 0 } },
      ],
      total: { name: 'Total Liabilities', current: totalLiab, prior: 0 },
    },
    netAssets: { name: 'Net Assets', current: netAssets, prior: 0 },
    equity: {
      items: [{ name: 'Retained Earnings', current: netAssets, prior: 0 }],
      total: { name: 'Total Equity', current: netAssets, prior: 0 },
    },
  }
}
