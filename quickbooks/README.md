# QuickBooks Online connector

This package is a separate, read-only QuickBooks Online (QBO) integration. It
does not change the existing Xero pipeline or feed QuickBooks rows into
`run_mvp.py` yet.

## Why this uses QBO, not QuickBooks Desktop

QuickBooks Desktop uses a locally installed Windows SDK or QuickBooks Web
Connector and exchanges qbXML. It does not provide the cloud REST/OAuth flow
used by Xero. Intuit's demo companies that can be connected to a REST API are
QuickBooks Online sandbox companies, so this connector targets QBO.

## 1. Create or select a sandbox

1. Sign in to the Intuit Developer portal.
2. Go to **My Hub > Sandboxes**. A developer profile normally starts with one
   sandbox; you can also add an AU QuickBooks Online Plus sandbox.
3. Go to **My Hub > App dashboard** and create/open a QuickBooks Online app.
4. In the app's development settings, register this redirect URI exactly:

   `http://localhost:51790/callback`

5. Copy the **Development** Client ID and Client Secret. Development keys must
   be used with sandbox companies.

## 2. Configure QFR

Add these values to the repository's `.env` file:

```dotenv
QUICKBOOKS_CLIENT_ID=your_development_client_id
QUICKBOOKS_CLIENT_SECRET=your_development_client_secret
QUICKBOOKS_REDIRECT_URI=http://localhost:51790/callback
QUICKBOOKS_ENVIRONMENT=sandbox
QUICKBOOKS_MINOR_VERSION=75
```

`QUICKBOOKS_REALM_ID` is optional because the login script stores the selected
company's realm ID with the local token.

## 3. Connect the demo company

```bash
python login_quickbooks.py
```

Open the printed URL, sign in, and choose the desired sandbox company. The
script validates the OAuth state, exchanges the one-time code, verifies the
company with the CompanyInfo API, and saves `quickbooks_token.json` locally.
That file is ignored by Git. To choose a different company, run:

```bash
python login_quickbooks.py --force
```

## 4. Download raw entities and reports

Download the default set for the current calendar year:

```bash
python download_quickbooks_data.py
```

Choose a reporting period or a smaller set of endpoints:

```bash
python download_quickbooks_data.py --from-date 2025-07-01 --to-date 2026-06-30
python download_quickbooks_data.py --entities Account,Invoice,Bill,Purchase,JournalEntry --skip-reports
python download_quickbooks_data.py --reports ProfitAndLoss,BalanceSheet,GeneralLedger --skip-entities
python download_quickbooks_data.py --accounting-method Cash
```

JSON files are written to:

```text
output/quickbooks/
├── company_info.json
├── manifest.json
├── entities/
│   ├── account.json
│   ├── invoice.json
│   └── ...
└── reports/
    ├── profit_and_loss.json
    ├── balance_sheet.json
    └── ...
```

The default entity list includes accounts, customers, vendors, invoices,
bills, payments, purchases, bank deposits/transfers, credit documents,
journal entries, items, classes, and departments. The default reports include
P&L, detailed P&L, Balance Sheet, Cash Flow, Trial Balance, General Ledger,
account list, AR/AP aging, and customer/vendor balances.

List entities are requested with both active and inactive records. `Attachable`
downloads attachment metadata only; downloading the binary files can be added
later if the QFR evidence pipeline needs them.

Some entities and reports vary by sandbox country and QBO subscription. By
default, one unavailable endpoint is recorded in `manifest.json` and the rest
continue downloading. Pass `--strict` to stop on the first error.

QBO sandboxes do not support Payroll or linking a live bank account. The sample
banking transactions already present in the sandbox are still available through
the accounting entities and reports.

## Token behavior

QBO access tokens last one hour. The downloader refreshes an expired access
token and always stores the newest rotating refresh token. If the refresh token
has not been used for 100 days, reconnect with `python login_quickbooks.py
--force`.

## Using the modules directly

```python
from quickbooks.client import QuickBooksClient
from quickbooks.oauth import load_token
from quickbooks.reports import build_report_params

token = load_token()
client = QuickBooksClient(
    token["access_token"],
    token["realm_id"],
    environment="sandbox",
)

invoices = client.query_all("Invoice")
profit_and_loss = client.get_report(
    "ProfitAndLoss",
    build_report_params(
        "ProfitAndLoss",
        from_date="2026-01-01",
        to_date="2026-03-31",
        accounting_method="Accrual",
    ),
)
```
