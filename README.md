# QFR Xero AI Mapping

Python batch pipeline that authenticates with Xero, pulls Profit & Loss and
Balance Sheet evidence, maps P&L transaction lines into a controlled QFR
taxonomy, and generates Excel, CSV, JSON, and HTML reports.

The primary mapper is OpenAI (`gpt-4o-mini`). Gemini remains in the repository
as an optional/legacy mapper but is not used by `run_mvp.py`.

## What the pipeline reads

- Xero Profit & Loss and opening/closing Balance Sheet reports
- Chart of Accounts
- Bills and sales invoices
- Bank transactions and bank transfers
- Credit notes and payments
- Manual journals and general journals
- Finance API Balance Sheet detail when authorized
- Payroll report or pay runs when authorized

`run_mvp.py` normalizes these sources into line-level evidence, applies
deterministic business rules first, and sends only unresolved P&L rows to the
AI mapper.

## Requirements

- Python 3.11+
- A Xero OAuth2 app and an authorized Xero organization
- `OPENAI_API_KEY_QFR` or `OPENAI_API_KEY`
- Outbound HTTPS access to Xero and OpenAI

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and provide the required values:

```dotenv
XERO_CLIENT_ID=your_xero_client_id
XERO_CLIENT_SECRET=your_xero_client_secret
XERO_REDIRECT_URI=http://localhost:51789/callback
XERO_TENANT_ID=
OPENAI_API_KEY_QFR=your_openai_key
```

`OPENAI_API_KEY_QFR` is preferred. `OPENAI_API_KEY` is used as a fallback.

## Xero authorization

Run:

```bash
python login_xero.py
```

Open the printed authorization URL and approve the target Xero organization.
The script stores the OAuth token in `xero_token.json` and writes the selected
`XERO_TENANT_ID` to `.env`.

Both files contain local credentials and are excluded from Git.

## QuickBooks Online sandbox (independent connector)

The repository also contains a separate, read-only `quickbooks/` package. It
connects to a QuickBooks Online sandbox company, downloads paginated raw
accounting entities, and downloads standard reports as JSON. It does not alter
or feed into the existing Xero `run_mvp.py` pipeline.

After registering `http://localhost:51790/callback` in an Intuit app and adding
the development Client ID/Secret to `.env`, run:

```bash
python login_quickbooks.py
python download_quickbooks_data.py --from-date 2026-01-01 --to-date 2026-03-31
```

See [`quickbooks/README.md`](quickbooks/README.md) for sandbox setup, raw entity
coverage, report coverage, token behavior, and focused download examples.

## Generate reports

Run the default reporting period (currently 2026-01-01 to 2026-03-31):

```bash
python run_mvp.py
```

Common alternatives:

```bash
python run_mvp.py --year 2025
python run_mvp.py --from-date 2025-07-01 --to-date 2026-06-30
python run_mvp.py --mapping-workers 4 --ai-timeout 30
python run_mvp.py --use-cache --no-payroll
```

Important options:

- `--mapping-workers`: concurrent mapping requests, 1-32; default is 4 or
  `AI_MAPPING_WORKERS`.
- `--ai-timeout`: per-request OpenAI timeout, 1-120 seconds; default is 30 or
  `OPENAI_TIMEOUT_SECONDS`.
- `--use-cache`: reuse `output/raw_*.json`. Only use caches created for the
  same tenant and reporting period.
- `--no-payroll`, `--no-manual-journals`, `--no-journals`: skip optional APIs.
- `--payments-only`: request the Xero P&L in payments-only mode.
- `--no-progress`: disable the live mapping progress page.

## Mapping safety

AI output must be one JSON object with:

- `category`: an exact configured category from `category_definitions.json`
- `confidence`: a finite JSON number between 0 and 1
- `reason`: a non-empty string

Invalid model output is rejected to `Unmapped` with confidence `0.0` and a
validation RuleID. Rejected output is not cached.

`mapping_memory.json` uses a versioned schema and includes account, transaction,
amount, model, and taxonomy context in each cache key. Writes are locked and
atomic so concurrent mapping workers cannot corrupt the cache. Version 1 cache
entries are preserved for audit during migration but are not reused without
their missing context.

## Main outputs

Files are written under `output/`. The main deliverables are:

- `pl_mapping_report.xlsx`: line-level P&L mapping and audit fields
- `pl_mapping_summary.xlsx`: totals by mapped category
- `income_mapping_report.xlsx` and `expense_mapping_report.xlsx`
- `total_summary.csv` and `total_summary.xlsx`
- `xero_vs_ai_diff.xlsx`: Xero category totals compared with mapped totals
- `xero_vs_ai_line_debug.xlsx`: line-level reconciliation diagnostics
- `balance_sheet_mapping_report.xlsx`: official Xero Balance Sheet structure
- `balance_sheet_evidence_report.xlsx`: transaction and synthetic BS evidence
- `balance_sheet_xero_vs_ai_rebuild_diff.xlsx`: opening plus movement analysis
- `wages_reconciliation_lines.xlsx` and `wages_reconciliation_summary.xlsx`
- `report_data.json`: machine-readable report payload
- `report.html`: interactive report using the generated payload
- `report_assistant.html`: local report Q&A page with optional OpenAI narrative
- `progress.html` and `progress.json`: live mapping progress

Raw API payloads, generated reports, OAuth tokens, and mapping memory are
excluded from Git.

## Frontend status

`frontend/` is a separate Next.js 16 demonstration dashboard. Its P&L, Balance
Sheet, cash trend, aging, and AI Insights screens currently use mock data; it
does not automatically read Python's `output/report_data.json`.

Run it with:

```bash
cd frontend
npm install
npm run dev
```

Temporary demo credentials are `admin` / `admin123`. They are client-side only
and are not production authentication.

## Tests

```bash
python -m unittest -v test_ai_mapping.py
python test_mapping_consistency.py
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
```

`test_mapping_consistency.py` verifies that the generated P&L detail and summary
agree arithmetically. It is not a substitute for reconciliation against Xero.
