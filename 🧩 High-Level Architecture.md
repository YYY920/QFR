# QFR High-Level Architecture

## 1. Business Goal

QFR is a financial reporting MVP for turning Xero accounting data into a clearer management reporting layer.

The core business flow is:

1. Connect to Xero Demo Company through OAuth.
2. Pull Profit & Loss, Balance Sheet, invoices, bills, payments, journals, accounts, and optional payroll evidence.
3. Flatten accounting lines into a consistent transaction dataset.
4. Map each transaction line into predefined QFR reporting categories.
5. Produce auditable Excel/CSV outputs with mapping confidence, reasons, review flags, and reconciliation views.
6. Present the output in a Next.js dashboard with P&L analytics, Balance Sheet analytics, and an AI assistant for finance Q&A.

The product is not intended to let the LLM perform accounting calculations directly. Calculations, totals, filters, ratios, and reconciliations are deterministic code paths. The LLM is used for classification and narrative explanation.

## 2. Business Logic

### Profit & Loss Mapping

The backend converts Xero transaction evidence into line-level records with:

- transaction type
- invoice number
- date
- contact/vendor/customer
- account code
- account name
- description
- amount
- mapped QFR category
- confidence score
- reason
- rule ID or fallback indicator

The mapping business rule is:

1. Use deterministic patch rules where known accounting policies exist.
2. Check versioned local mapping memory using contact, description, amount,
   account, transaction type, model, and taxonomy context.
3. Ask OpenAI for a category suggestion when no deterministic result exists.
4. Strictly validate category, confidence, and reason; reject invalid model
   output to `Unmapped` with an audit RuleID.
5. Apply post-mapping policy guards.
6. Fall back to account-name matching or `Unmapped` if the model/API is unavailable.
7. Flag low-confidence mappings for review.

Mapping is performed with bounded concurrency. The default is four workers and
a 30-second per-request timeout; both are configurable through CLI flags or
environment variables.

Current categories include items such as `Sales`, `Advertising`, `Office Expenses`, `Rent`, `Subscriptions`, `Wages and Salaries`, and `Unmapped`.

### Balance Sheet Mapping and Analysis

The backend produces Balance Sheet detail and summary outputs from Xero Balance Sheet structure plus supporting evidence such as journals, invoice control lines, payments, GST, receivables, and payables.

The frontend currently displays Balance Sheet data from `frontend/src/lib/balance-sheet-mock.ts`. The Balance Sheet page implements:

- summary cards for total assets, liabilities, net assets, and equity
- Balance Sheet figures:
  - Balance Sheet Totals
  - Capital Structure Mix
  - Working Capital Bridge
  - Net Position
- financial analysis tables:
  - liquidity and leverage ratios
  - balance composition/common-size view
  - year-on-year movement
- detailed Balance Sheet table with current, prior, and movement columns

The current mock Balance Sheet contains negative bank/assets/equity values, so the UI explicitly warns that sign conventions should be reviewed before treating ratios as final advice.

### AI Assistant Business Logic

The floating AI assistant is available across dashboard pages. It supports P&L and Balance Sheet questions.

It follows a two-step logic:

1. Generate a local deterministic draft from known frontend data:
   - P&L top category totals
   - low-confidence mappings
   - payroll trend
   - advertising suppliers
   - Balance Sheet liquidity, working capital, assets, liabilities, equity
2. Send the question, local draft, dataset summary, and sample rows to `/api/ai-insights` for LLM narrative polish.

If no API key is configured or the API fails, the assistant still shows the local draft.

## 3. Backend Architecture

### Main Entrypoints

- `login_xero.py`
  - Starts Xero OAuth.
  - Exchanges auth code for tokens.
  - Saves `xero_token.json`.
  - Stores/uses `XERO_TENANT_ID`.

- `run_mvp.py`
  - Main data pipeline.
  - Pulls Xero reports and evidence.
  - Applies mapping rules and OpenAI mapping.
  - Writes Excel/CSV/JSON/HTML outputs into `output/`.
  - Supports date range flags and cache flags.

- `config.py`
  - Loads environment variables from `.env`.
  - Supports Xero credentials, Gemini key, OpenAI key, and QFR-specific OpenAI key.

### Xero Modules

The `xero/` package wraps Xero API endpoints:

- `oauth.py`
- `reports.py`
- `transactions.py`
- `accounts.py`
- `journals.py`
- `general_journals.py`
- `finance.py`
- `payroll.py`
- `invoice_files.py`

The backend can request:

- Profit & Loss
- Balance Sheet
- invoices
- bills
- bank transactions
- bank transfers
- payments
- credit notes
- chart of accounts
- manual/general journals
- payroll pay runs where authorized

### AI Modules

The `ai/` package contains:

- `openai_mapper.py`
  - Current active mapper.
  - Uses `gpt-4o-mini`.
  - Requires `OPENAI_API_KEY_QFR` or `OPENAI_API_KEY`.
  - Returns category, confidence, reason, and optional rule ID.

- `gemini_mapper.py`
  - Still present, but current `run_mvp.py` imports the OpenAI mapper.
  - Optional/legacy path; it now shares the strict output validator and cache schema.

- `memory_store.py`
  - Uses a versioned, context-aware cache schema.
  - Migrates legacy entries for audit without reusing contextless results.
  - Uses thread/process locking and atomic replacement for concurrent writes.

- `mapping_validation.py`
  - Enforces the model output contract and produces deterministic rejection RuleIDs.

- `prompts.py`
  - Holds the mapping prompt template and category constraints.

### Backend Outputs

Typical generated files include:

- `output/pl_mapping_report.xlsx`
- `output/pl_mapping_summary.xlsx`
- income/expense split reports
- payroll reconciliation files when available
- Balance Sheet mapping detail and summary files
- Xero-vs-AI reconciliation/debug files
- raw JSON caches when `--use-cache` or dump options are used
- visual HTML/progress outputs for review

## 4. Frontend Architecture

The frontend is a standalone Next.js app in `frontend/`.

Tech stack:

- Next.js 16
- React 19
- TypeScript
- Tailwind CSS
- shadcn-style UI components
- Recharts
- Vitest

### Routing

- `/`
  - Redirects to `/profit-loss`.

- `/login`
  - Temporary local login screen.
  - Hardcoded credentials:
    - username: `admin`
    - password: `admin123`
  - Optional OpenAI API key input.
  - Stores login flag and optional API key in `sessionStorage`.

- `/profit-loss`
  - Main AI mapping report dashboard.
  - Uses `REPORT_DATA` from `frontend/src/lib/report-data-mock.ts`.
  - Supports filtering by date, transaction type, account, search text, unmapped-only, and low-confidence-only.
  - Displays metric cards, charts, and detailed tables.

- `/balance-sheet`
  - Balance Sheet dashboard.
  - Uses `BALANCE_SHEET_DATA` from `frontend/src/lib/balance-sheet-mock.ts`.
  - Displays summary cards, figures, financial analysis tables, and detailed account table.

- `/ai-insights`
  - Visual AI insights animation page.
  - Separate from the floating assistant.

- `/api/ai-insights`
  - Server route used by the floating assistant.
  - Accepts question, local draft, dataset summary, sample rows, and optional session API key.
  - Calls OpenAI Chat Completions.
  - Falls back to environment variables if no session key is provided.

### Layout and Auth

- `frontend/src/app/(dashboard)/layout.tsx`
  - Wraps dashboard pages with `Sidebar`.
  - Mounts `FloatingAssistant` globally.

- `frontend/src/proxy.ts`
  - Handles simple cookie-based route protection.

- `frontend/src/lib/auth.ts`
  - Temporary browser-only auth helper.
  - Sets `qfr_auth` cookie and `qfr_session`.
  - Stores optional `qfr_openai_api_key` for the current browser session.

## 5. Data Flow

### Backend Data Flow

```text
Xero OAuth
  -> Xero reports and transaction APIs
  -> flatten transaction/report evidence
  -> deterministic patch rules
  -> local mapping memory
  -> OpenAI category mapping
  -> validation/fallbacks
  -> Excel/CSV/JSON/HTML outputs
```

### Frontend Data Flow

```text
mock report data
  -> filters and deterministic calculations
  -> dashboard cards/charts/tables
  -> floating assistant local draft
  -> /api/ai-insights
  -> OpenAI narrative answer
```

## 6. What Has Been Implemented

### Backend

- Xero OAuth login flow.
- Xero P&L and Balance Sheet report pulling.
- Transaction evidence pulling for bills, invoices, payments, credit notes, bank activity, journals, accounts, and optional payroll.
- OpenAI-based mapping into constrained QFR categories.
- Strict category/confidence/reason validation with hard rejection to `Unmapped`.
- Context-aware, versioned, atomically written mapping memory.
- Bounded concurrent mapping with configurable worker count and timeout.
- Deterministic patch/policy rules for known edge cases.
- Confidence scores, reasons, and rule IDs.
- Excel/CSV outputs for mapping reports and summaries.
- Reconciliation/debug outputs comparing Xero and AI-derived views.
- CLI flags for date ranges, full-year reports, cache usage, raw dumps, payroll skipping, journal skipping, and payments-only mode.

### Frontend

- Login page with optional session API key configuration.
- Protected dashboard shell with sidebar navigation.
- P&L dashboard:
  - filters
  - metric cards
  - category charts
  - mapped/unmapped view
  - confidence distribution
  - monthly income vs expense
  - data tables
- Balance Sheet dashboard:
  - summary cards
  - visual figures
  - liquidity/leverage analysis
  - balance composition
  - year-on-year movement
  - detailed Balance Sheet table
- Floating AI assistant:
  - available across dashboard pages
  - P&L and Balance Sheet pre-baked questions
  - local deterministic draft
  - optional OpenAI answer
  - visible thinking/loading state
  - readable answer panel
- `/api/ai-insights` route for server-side OpenAI calls.

## 7. Testing and Local Commands

### Backend

```bash
python login_xero.py
python run_mvp.py --use-cache --no-progress
python -m unittest -v test_ai_mapping.py
python test_mapping_consistency.py
python test_openai.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
npm run lint
npm run test
npm run build
```

Recent frontend checks passed:

- `npm run lint`
- `npm run test`
- `npm run build`

There is a local Next.js workspace-root warning caused by another lockfile outside this repo (`/Users/jinhongyu/package-lock.json`). It does not currently block the build.

## 8. Deployment Status

No deploy automation is stored in this repository:

- no `.github/workflows`
- no `vercel.json`
- no committed `.vercel` directory

The prior automatic deployment was most likely configured through the Vercel Dashboard GitHub integration.

For the transferred GitHub ownership/new Vercel account setup:

1. Import the GitHub repository into the new Vercel account.
2. Ensure the Vercel GitHub App has access to the new repository owner/org.
3. Set Vercel Root Directory to `frontend`.
4. Use Next.js defaults:
   - install: `npm install`
   - build: `npm run build`
5. Add environment variables in Vercel:
   - `OPENAI_API_KEY_QFR` or `OPENAI_API_KEY`
   - any future backend/API secrets as needed
6. Set the production branch, usually `main`.
7. Push or merge to that branch to trigger automatic deployment.

## 9. Current Limitations and Risks

- The frontend currently uses mock data rather than live backend output.
- Login is temporary and hardcoded.
- The browser-session API key is convenient for demos but should be replaced by a proper secure backend secret model for production.
- Balance Sheet signs require accounting validation before ratios are treated as final advice.
- Payroll access may be unavailable depending on Xero tenant authorization.
- Formal ACFR import-template generation and tracking/category dictionaries are not fully implemented.
- Human review workflow exists as output/reporting logic, but not yet as a full interactive approval workflow.
- Mapping cache and validation are versioned, but broader rule ownership and
  approval governance are still required before production use.

## 10. Near-Term Next Steps

1. Wire frontend dashboards to generated backend JSON instead of mock data.
2. Replace hardcoded login with real auth.
3. Move API key handling fully server-side for production.
4. Add deploy documentation or `vercel.json` if the project needs repo-controlled deployment behavior.
5. Expand Balance Sheet data coverage beyond the current mock dataset.
6. Add a human review UI for low-confidence mapping approvals.
