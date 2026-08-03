import json
from datetime import timezone, datetime

def pd(s):
    if not s: return None
    ms = int(s.split('(')[1].split('+')[0].split(')')[0])
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).date()

def shift_back(d):
    if d is None: return None
    try: return d.replace(year=d.year - 1)
    except ValueError: return d.replace(year=d.year - 1, day=28)

def load_outstanding(path):
    with open(path) as f: data = json.load(f)
    out = []
    for inv in data.get('Invoices', []):
        if inv.get('Status') in ('AUTHORISED', 'SUBMITTED'):
            issued = shift_back(pd(inv.get('Date')))
            due = shift_back(pd(inv.get('DueDate')))
            amt = inv.get('AmountDue', 0) or 0
            if issued and due and amt:
                out.append((issued.isoformat(), due.isoformat(), round(float(amt), 2)))
    return out

ar = load_outstanding('output/raw_invoices.json')
ap = load_outstanding('output/raw_bills.json')

print("// Real outstanding AR/AP items from Xero (dates shifted to 2025).")
print("// [issued, due, amount] — aging is computed live at any selected date.")
print("export type AgingItem = { issued: string; due: string; amount: number }")
print("export const AR_ITEMS: AgingItem[] = [")
for issued, due, amt in ar:
    print(f"  {{ issued: '{issued}', due: '{due}', amount: {amt} }},")
print("]")
print("export const AP_ITEMS: AgingItem[] = [")
for issued, due, amt in ap:
    print(f"  {{ issued: '{issued}', due: '{due}', amount: {amt} }},")
print("]")
print("")
print("// Aging buckets [0-30, 31-60, 61-90, 90+] as at endDate, items issued on/after startDate.")
print("export function computeAging(items: AgingItem[], startDate: string, endDate: string): [number, number, number, number] {")
print("  const buckets: [number, number, number, number] = [0, 0, 0, 0]")
print("  const start = new Date(startDate)")
print("  const end = new Date(endDate)")
print("  for (const it of items) {")
print("    const issued = new Date(it.issued)")
print("    if (issued < start) continue")
print("    if (issued > end) continue")
print("    const due = new Date(it.due)")
print("    const days = Math.floor((end.getTime() - due.getTime()) / 86400000)")
print("    if (days <= 30) buckets[0] += it.amount")
print("    else if (days <= 60) buckets[1] += it.amount")
print("    else if (days <= 90) buckets[2] += it.amount")
print("    else buckets[3] += it.amount")
print("  }")
print("  return buckets.map((b) => Math.round(b * 100) / 100) as [number, number, number, number]")
print("}")