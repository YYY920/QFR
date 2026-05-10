from typing import Any, Dict, Optional

import requests

BASE = "https://api.xero.com/api.xro/2.0"


def _auth_headers(access_token: str, tenant_id: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }


def get_journals(
    access_token: str,
    tenant_id: str,
    offset: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Fetch general journals.
    Xero journals pagination is offset-based using JournalNumber.
    """
    url = f"{BASE}/Journals"
    params: Dict[str, Any] = {}
    if offset is not None:
        params["offset"] = offset
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()

