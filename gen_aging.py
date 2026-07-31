import json
from datetime import date, timezone, datetime

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
            due = shift_back(pd(inv.get('DueDate')))
            amt = inv.get('AmountDue', 0) or 0
            if due and amt: out.append((due, float(amt)))
    return out

def buckets(items, as_at):
    b = [0.0, 0.0, 0.0, 0.0]
    for due, amt in items:
        days = (as_at - due).days
        if days <= 30: b[0] += amt
        elif days <= 60: b[1] += amt
        elif days <= 90: b[2] += amt
        else: b[3] += amt
    return [round(x, 2) for x in b]

ar = load_outstanding('output/raw_invoices.json')
ap = load_outstanding('output/raw_bills.json')

months = [('2025-%02d' % m, date(2025, m, [31,28,31,30,31,30,31,31,30,31,30,31][m-1])) for m in range(1,13)]

print("// REAL AR/AP aging from Xero outstanding invoices/bills (dates shifted to 2025).")
print("export type AgingByMonth = { [key: string]: { ar: [number,number,number,number]; ap: [number,number,number,number] } }")
print("export const AGING_BY_MONTH: AgingByMonth = {")
for key, dt in months:
    arb = buckets(ar, dt); apb = buckets(ap, dt)
    print(f"  '{key}': {{ ar: [{arb[0]}, {arb[1]}, {arb[2]}, {arb[3]}], ap: [{apb[0]}, {apb[1]}, {apb[2]}, {apb[3]}] }},")
print("}")