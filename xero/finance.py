from typing import Any, Dict

import requests

BASE = "https://api.xero.com/finance.xro/1.0"


def _auth_headers(access_token: str, tenant_id: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }


def get_financial_statement_balance_sheet(
    access_token: str,
    tenant_id: str,
    balance_date: str,
) -> Dict[str, Any]:
    """Fetch Finance API Balance Sheet account-level financial statement data."""
    url = f"{BASE}/FinancialStatements/BalanceSheet"
    params = {"balanceDate": balance_date}
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()
