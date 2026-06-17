## Xero AI P&L Mapping MVP

Python MVP to connect to your **Xero Demo Company**, read the **Profit & Loss** and related transactions, use **Gemini** to semantically map transaction descriptions to reporting categories, and output an Excel report.

### 1. Setup

1. Create and activate a virtualenv (optional but recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root and fill in your keys:

Example:

```bash
cat > .env << 'EOF'
XERO_CLIENT_ID=your_xero_client_id
XERO_CLIENT_SECRET=your_xero_client_secret
XERO_REDIRECT_URI=http://localhost:51789/callback
XERO_TENANT_ID=
GEMINI_API_KEY=your_gemini_key
EOF
```

You must create a Xero OAuth2 app and a Google Gemini API key.

### 2. Xero OAuth Login

1. Run the login helper:

```bash
python login_xero.py
```

2. Copy-paste the URL into your browser, log into Xero, select **Demo Company**, and approve.
3. After redirect, the script will capture the code, exchange for tokens, and save:
   - `xero_token.json` (access + refresh token)
   - `XERO_TENANT_ID` into `.env`

### 3. Run the MVP

Generate the AI-enhanced P&L mapping report:

```bash
python run_mvp.py
```

Outputs will be written to the `output/` folder:

- `pl_mapping_report.xlsx` – line-level mapping
- `pl_mapping_summary.xlsx` – category-level totals

### 4. Notes

- This MVP **only** targets your own Demo Company.
- Mapping is done via **Gemini** few-shot prompting plus a simple local memory cache.
- You can adjust categories in `run_mvp.py` under `ALLOWED_CATEGORIES`.

