from typing import Any, Dict

import requests

BASE = "https://api.xero.com/api.xro/2.0"


def _auth_headers(access_token: str, tenant_id: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }


def get_accounts(access_token: str, tenant_id: str) -> Dict[str, Any]:
    """Fetch the chart of accounts for the tenant."""
    url = f"{BASE}/Accounts"
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), timeout=60)
    resp.raise_for_status()
    return resp.json()
