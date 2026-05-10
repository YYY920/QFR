## Deployment Requirements for QFR Xero Mapping Project

### 1) Project Scope (Context)
This service authenticates with Xero, pulls financial data (P&L, invoices, bills, bank transactions, credit notes, journals, and optional payroll), maps each line into predefined QFR categories using AI, and generates Excel/CSV/HTML outputs in the `output/` folder.

### 2) Client Inputs Required (Xero)

#### A. Xero App (OAuth2)
Please provide:
- `XERO_CLIENT_ID`
- `XERO_CLIENT_SECRET`
- Registered `XERO_REDIRECT_URI` (must exactly match runtime configuration)

Required OAuth scopes:
- `offline_access`
- `accounting.reports.read`
- `accounting.transactions`
- `accounting.journals.read`
- `accounting.settings`
- `accounting.contacts`
- `accounting.attachments.read`

Optional payroll scopes (only if payroll is required):
- `payroll.employees`
- `payroll.payruns`
- `payroll.payslip`

#### B. Xero Tenant Access
Please provide:
- The target Xero organization (tenant) to analyze
- A user account with permission to authorize the app
- One-time completion of OAuth browser consent
- Confirmed `XERO_TENANT_ID` after authorization

#### C. Functional Confirmations
Please confirm:
- Reporting period (e.g., full-year 2025 or custom date range)
- Whether payroll should be included
- Whether journals/manual journals should be included

### 3) Client Inputs Required (AI Provider)

At least one key is required:
- `OPENAI_API_KEY_QFR` (preferred) or `OPENAI_API_KEY`

Optional:
- `GEMINI_API_KEY` (not the current primary runtime path)

### 4) Server Requirements

Recommended minimum:
- OS: Linux (Ubuntu 22.04+ recommended)
- CPU: 2 vCPU minimum (4 vCPU preferred for larger data volumes)
- RAM: 4 GB minimum (8 GB preferred)
- Storage: 20 GB free minimum
- Python: 3.11+
- Outbound HTTPS access to:
  - `login.xero.com`
  - `identity.xero.com`
  - `api.xero.com`
  - OpenAI API endpoint(s)

### 5) Access Needed for Deployment

Please provide:
- SSH/admin access to the target server (or CI/CD pipeline access)
- Permission to install Python dependencies
- Permission to create/manage environment variables or secret-manager entries
- A deployment owner/contact for Xero authorization and UAT sign-off