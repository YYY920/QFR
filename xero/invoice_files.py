from typing import Any, Dict

import requests

BASE = "https://api.xero.com/api.xro/2.0"


def _auth_headers(access_token: str, tenant_id: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
    }


def get_invoice_pdf(access_token: str, tenant_id: str, invoice_id: str) -> bytes:
    url = f"{BASE}/Invoices/{invoice_id}/pdf"
    headers = _auth_headers(access_token, tenant_id)
    headers["Accept"] = "application/pdf"
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.content


def get_invoice_attachments(access_token: str, tenant_id: str, invoice_id: str) -> Dict[str, Any]:
    url = f"{BASE}/Invoices/{invoice_id}/Attachments"
    headers = _auth_headers(access_token, tenant_id)
    headers["Accept"] = "application/json"
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_invoice_attachment_by_id(
    access_token: str,
    tenant_id: str,
    invoice_id: str,
    attachment_id: str,
    content_type: str,
) -> bytes:
    url = f"{BASE}/Invoices/{invoice_id}/Attachments/{attachment_id}"
    headers = _auth_headers(access_token, tenant_id)
    headers["Accept"] = content_type
    headers["Content-Type"] = content_type
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    return resp.content
