from typing import Any, Dict, Optional

import requests

BASE = "https://api.xero.com/api.xro/2.0"


def _auth_headers(access_token: str, tenant_id: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }


def _build_params(where: str, page: int, summary_only: Optional[bool], order: Optional[str]) -> Dict[str, Any]:
    params: Dict[str, Any] = {"where": where, "page": page}
    if summary_only is not None:
        params["summaryOnly"] = str(summary_only).lower()
    if order:
        params["order"] = order
    return params


def get_bills(
    access_token: str,
    tenant_id: str,
    page: int = 1,
    summary_only: Optional[bool] = None,
    order: Optional[str] = None,
) -> Dict[str, Any]:
    """Accounts Payable bills (ACCPAY)."""
    url = f"{BASE}/Invoices"
    params = _build_params('Type=="ACCPAY"', page, summary_only, order)
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_invoices(
    access_token: str,
    tenant_id: str,
    page: int = 1,
    summary_only: Optional[bool] = None,
    order: Optional[str] = None,
) -> Dict[str, Any]:
    """Accounts Receivable invoices (ACCREC)."""
    url = f"{BASE}/Invoices"
    params = _build_params('Type=="ACCREC"', page, summary_only, order)
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_bank_transactions(
    access_token: str,
    tenant_id: str,
    page: int = 1,
    summary_only: Optional[bool] = None,
    order: Optional[str] = None,
) -> Dict[str, Any]:
    """Bank transactions (SPEND/RECEIVE)."""
    url = f"{BASE}/BankTransactions"
    params: Dict[str, Any] = {"page": page}
    if summary_only is not None:
        params["summaryOnly"] = str(summary_only).lower()
    if order:
        params["order"] = order
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_credit_notes(
    access_token: str,
    tenant_id: str,
    page: int = 1,
    summary_only: Optional[bool] = None,
    order: Optional[str] = None,
) -> Dict[str, Any]:
    """Credit notes (ACCPAYCREDIT/ACCRECCREDIT)."""
    url = f"{BASE}/CreditNotes"
    params: Dict[str, Any] = {"page": page}
    if summary_only is not None:
        params["summaryOnly"] = str(summary_only).lower()
    if order:
        params["order"] = order
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_payments(
    access_token: str,
    tenant_id: str,
    page: int = 1,
    where: Optional[str] = None,
    order: Optional[str] = None,
    page_size: Optional[int] = 100,
) -> Dict[str, Any]:
    """Payments for invoices and credit notes."""
    url = f"{BASE}/Payments"
    params: Dict[str, Any] = {"page": page}
    if where:
        params["where"] = where
    if order:
        params["order"] = order
    if page_size is not None:
        params["pageSize"] = page_size
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_bank_transfers(
    access_token: str,
    tenant_id: str,
    page: int = 1,
    where: Optional[str] = None,
    order: Optional[str] = None,
) -> Dict[str, Any]:
    """Bank transfers between bank accounts."""
    url = f"{BASE}/BankTransfers"
    params: Dict[str, Any] = {"page": page}
    if where:
        params["where"] = where
    if order:
        params["order"] = order
    resp = requests.get(url, headers=_auth_headers(access_token, tenant_id), params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()
