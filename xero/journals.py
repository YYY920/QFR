from typing import Any, Dict, Optional

import requests

BASE = "https://api.xero.com/api.xro/2.0"


def _auth_headers(access_token: str, tenant_id: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }


def get_manual_journals(
    access_token: str,
    tenant_id: str,
    page: int = 1,
    where: Optional[str] = None,
    order: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch manual journals (typically used for accounting adjustments)."""
    url = f"{BASE}/ManualJournals"
    params: Dict[str, Any] = {"page": page}
    if where:
        params["where"] = where
    if order:
        params["order"] = order
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()

