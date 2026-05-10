from typing import Any, Dict

import requests

BASE = "https://api.xero.com/payroll.xro/2.0"


def _auth_headers(access_token: str, tenant_id: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }


def get_payruns(access_token: str, tenant_id: str) -> Dict[str, Any]:
    """Fetch payroll pay runs (if payroll is enabled for the tenant)."""
    url = f"{BASE}/PayRuns"
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), timeout=60)
    resp.raise_for_status()
    return resp.json()
