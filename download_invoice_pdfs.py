from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import load_settings
from xero.oauth import load_token
from xero.transactions import get_bills, get_invoices
from xero.invoice_files import (
    get_invoice_pdf,
    get_invoice_attachments,
    get_invoice_attachment_by_id,
)

OUTPUT_DIR = Path("output")


_XERO_DATE_RE = re.compile(r"/Date\((\d+)(?:[+-]\d+)?\)/")


def _parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_xero_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    if text.startswith("/Date("):
        match = _XERO_DATE_RE.search(text)
        if match:
            try:
                ms = int(match.group(1))
            except ValueError:
                return None
            return datetime.utcfromtimestamp(ms / 1000).date()

    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.date()
    except ValueError:
        pass

    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _normalize_xero_date(value: Any) -> Optional[date]:
    return _parse_xero_date(value)


def _in_date_range(value: Optional[date], start: date, end: date) -> bool:
    if value is None:
        return True
    return start <= value <= end


def _sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
    return cleaned or "invoice"


def _fetch_all_invoices(fetch_fn, access_token: str, tenant_id: str, max_pages: int) -> Dict[str, Any]:
    all_invoices: List[Dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        payload = fetch_fn(access_token, tenant_id, page=page, summary_only=False, order="Date ASC")
        invoices = payload.get("Invoices", [])
        if not invoices:
            break
        all_invoices.extend(invoices)
    return {"Invoices": all_invoices}


def _load_env_and_token() -> Dict[str, Any]:
    settings = load_settings()
    tenant_id = settings.xero_tenant_id
    if not tenant_id:
        raise SystemExit("XERO_TENANT_ID is not set. Please run login_xero.py first.")

    token = load_token()
    if not token or "access_token" not in token:
        raise SystemExit("No Xero access token found. Please run login_xero.py first.")

    return {"access_token": token["access_token"], "tenant_id": tenant_id}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Xero invoice PDFs/attachments.")
    parser.add_argument("--from-date", dest="from_date", help="YYYY-MM-DD")
    parser.add_argument("--to-date", dest="to_date", help="YYYY-MM-DD")
    parser.add_argument("--year", type=int, help="Shortcut for full-year report (YYYY)")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages to fetch")
    parser.add_argument("--include-bills", action="store_true", help="Also download bills (ACCPAY)")
    parser.add_argument("--attachments", action="store_true", help="Also download PDF attachments")
    parser.add_argument("--use-raw", action="store_true", help="Use output/raw_invoices.json if present")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    env = _load_env_and_token()
    access_token = env["access_token"]
    tenant_id = env["tenant_id"]

    if args.from_date or args.to_date:
        if not (args.from_date and args.to_date):
            raise SystemExit("Both --from-date and --to-date are required.")
        start_date = _parse_iso_date(args.from_date)
        end_date = _parse_iso_date(args.to_date)
    elif args.year:
        start_date = date(args.year, 1, 1)
        end_date = date(args.year, 12, 31)
    else:
        start_date = date(2025, 1, 1)
        end_date = date(2025, 12, 31)

    invoices_payload: Dict[str, Any] = {}
    raw_path = OUTPUT_DIR / "raw_invoices.json"
    if args.use_raw and raw_path.exists():
        invoices_payload = json.loads(raw_path.read_text(encoding="utf-8"))
    else:
        invoices_payload = _fetch_all_invoices(get_invoices, access_token, tenant_id, args.max_pages)

    bills_payload: Dict[str, Any] = {"Invoices": []}
    if args.include_bills:
        bills_payload = _fetch_all_invoices(get_bills, access_token, tenant_id, args.max_pages)

    invoice_pdfs_dir = OUTPUT_DIR / "invoice_pdfs"
    invoice_pdfs_dir.mkdir(parents=True, exist_ok=True)
    attachments_dir = OUTPUT_DIR / "invoice_attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    def handle_invoices(items: List[Dict[str, Any]], label: str) -> None:
        for inv in items:
            invoice_id = inv.get("InvoiceID")
            if not invoice_id:
                continue
            inv_date = _normalize_xero_date(inv.get("DateString") or inv.get("Date"))
            if not _in_date_range(inv_date, start_date, end_date):
                continue

            invoice_number = inv.get("InvoiceNumber") or invoice_id
            filename = _sanitize_filename(str(invoice_number)) + ".pdf"
            pdf_path = invoice_pdfs_dir / filename

            try:
                pdf_bytes = get_invoice_pdf(access_token, tenant_id, invoice_id)
                pdf_path.write_bytes(pdf_bytes)
            except Exception as exc:  # noqa: BLE001
                print(f"{label} {invoice_number}: failed to download PDF ({exc})")
                continue

            if not args.attachments:
                continue

            try:
                attachments = get_invoice_attachments(access_token, tenant_id, invoice_id)
            except Exception as exc:  # noqa: BLE001
                print(f"{label} {invoice_number}: failed to list attachments ({exc})")
                continue

            for att in attachments.get("Attachments", []):
                file_name = att.get("FileName") or att.get("Filename") or "attachment"
                mime_type = att.get("MimeType") or att.get("ContentType") or "application/octet-stream"
                if not file_name.lower().endswith(".pdf") and "pdf" not in mime_type.lower():
                    continue
                att_id = att.get("AttachmentID") or att.get("AttachmentId")
                if not att_id:
                    continue
                safe_name = _sanitize_filename(file_name)
                att_path = attachments_dir / f"{_sanitize_filename(str(invoice_number))}_{safe_name}"
                try:
                    att_bytes = get_invoice_attachment_by_id(
                        access_token,
                        tenant_id,
                        invoice_id,
                        att_id,
                        mime_type,
                    )
                    att_path.write_bytes(att_bytes)
                except Exception as exc:  # noqa: BLE001
                    print(f"{label} {invoice_number}: failed to download attachment {file_name} ({exc})")

    handle_invoices(invoices_payload.get("Invoices", []), "Invoice")
    if args.include_bills:
        handle_invoices(bills_payload.get("Invoices", []), "Bill")

    print("Done. PDFs saved under output/invoice_pdfs (and attachments in output/invoice_attachments).")


if __name__ == "__main__":
    main()
