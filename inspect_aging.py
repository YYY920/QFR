import json
from datetime import datetime, timezone

def pd(s):
    if not s: return None
    ms = int(s.split('(')[1].split('+')[0].split(')')[0])
    return datetime.fromtimestamp(ms/1000, tz=timezone.utc).date()

for fname, label in [('output/raw_invoices.json','INVOICES (AR)'), ('output/raw_bills.json','BILLS (AP)')]:
    with open(fname) as f:
        data = json.load(f)
    invoices = data.get('Invoices', [])
    outstanding = [i for i in invoices if i.get('Status') in ('AUTHORISED','SUBMITTED')]
    print(f"\n{label}: {len(outstanding)} outstanding")
    total_due = 0
    for i in outstanding:
        issued = pd(i.get('Date'))
        due = pd(i.get('DueDate'))
        due_amt = i.get('AmountDue', 0)
        total_due += due_amt
        print(f"  issued {issued} | due {due} | total {i.get('Total')} | amountDue {due_amt}")
    print(f"  TOTAL OUTSTANDING: {total_due}")