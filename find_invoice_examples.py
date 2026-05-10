import json
import os
from pathlib import Path
from typing import List, Tuple

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parent
DETAIL_PATH = ROOT / "output" / "pl_mapping_report.xlsx"
TOKEN_PATH = ROOT / "xero_token.json"


def _read_tenant_id() -> str:
    env_path = ROOT / ".env"
    if not env_path.exists():
        raise SystemExit(".env not found")
    for line in env_path.read_text().splitlines():
        if line.startswith("XERO_TENANT_ID="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("XERO_TENANT_ID not found in .env")


def _get_access_token() -> str:
    if not TOKEN_PATH.exists():
        raise SystemExit("xero_token.json not found")
    token = json.loads(TOKEN_PATH.read_text())
    if "access_token" not in token:
        raise SystemExit("access_token not found in xero_token.json")
    return token["access_token"]


def _find_rent_sales_from_report() -> Tuple[List[str], List[str]]:
    rent_ids: List[str] = []
    sales_ids: List[str] = []
    if not DETAIL_PATH.exists():
        return rent_ids, sales_ids

    df = pd.read_excel(DETAIL_PATH)
    for col in ["AccountName", "Description", "MappedCategory", "InvoiceNumber"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    rent = df[
        df["AccountName"].str.contains("rent", case=False)
        | df["Description"].str.contains("rent", case=False)
        | df["MappedCategory"].str.contains("rent", case=False)
    ]
    sales = df[
        df["AccountName"].str.contains("sales", case=False)
        | df["MappedCategory"].str.contains("sales", case=False)
        | df["MappedCategory"].str.contains("income", case=False)
    ]

    rent_ids = rent["InvoiceNumber"].dropna().astype(str).unique().tolist()
    sales_ids = sales["InvoiceNumber"].dropna().astype(str).unique().tolist()
    return rent_ids, sales_ids


def _find_gst_from_api() -> List[str]:
    access_token = _get_access_token()
    tenant_id = _read_tenant_id()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Xero-tenant-id": tenant_id,
        "Accept": "application/json",
    }
    url = "https://api.xero.com/api.xro/2.0/Invoices"
    params = {"where": 'Type=="ACCREC"', "page": 1}

    resp = requests.get(url, headers=headers, params=params, timeout=60)
    resp.raise_for_status()
    invoices = resp.json().get("Invoices", [])

    gst_ids: List[str] = []
    for invoice in invoices:
        inv_num = invoice.get("InvoiceNumber") or invoice.get("InvoiceID")
        for li in invoice.get("LineItems", []) or []:
            tax_type = (li.get("TaxType") or "").upper()
            tax_amount = float(li.get("TaxAmount", 0) or 0)
            if tax_amount > 0 or "GST" in tax_type:
                gst_ids.append(inv_num)
                break
    return [i for i in gst_ids if i]


def main() -> None:
    rent_ids, sales_ids = _find_rent_sales_from_report()
    print("Rent invoice IDs (from report):", rent_ids[:5])
    print("Sales invoice IDs (from report):", sales_ids[:5])

    try:
        gst_ids = _find_gst_from_api()
        print("GST invoice IDs (from API):", gst_ids[:5])
    except Exception as exc:  # noqa: BLE001
        print("GST lookup failed:", exc)
        print("Tip: ensure network/proxy is set so Xero API can be reached.")


if __name__ == "__main__":
    main()
