from typing import Any, Dict

import requests

BASE = "https://api.xero.com/api.xro/2.0"


def _auth_headers(access_token: str, tenant_id: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }


def get_profit_and_loss(
    access_token: str,
    tenant_id: str,
    from_date: str,
    to_date: str,
    tracking_category_id: str | None = None,
    payments_only: bool = False,
) -> Dict[str, Any]:
    url = f"{BASE}/Reports/ProfitAndLoss"
    params: Dict[str, Any] = {
        "fromDate": from_date,
        "toDate": to_date,
        "paymentsOnly": str(payments_only).lower(),
    }
    if tracking_category_id:
        params["trackingCategoryID"] = tracking_category_id

    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_balance_sheet(
    access_token: str,
    tenant_id: str,
    date: str,
) -> Dict[str, Any]:
    url = f"{BASE}/Reports/BalanceSheet"
    params = {"date": date}
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_reports(access_token: str, tenant_id: str) -> Dict[str, Any]:
    """Fetch available reports list."""
    url = f"{BASE}/Reports"
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_report_by_id(access_token: str, tenant_id: str, report_id: str) -> Dict[str, Any]:
    """Fetch a report by ReportID from the reports list."""
    url = f"{BASE}/Reports/{report_id}"
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), timeout=60)
    resp.raise_for_status()
    return resp.json()
