from __future__ import annotations

from typing import Any, Iterable

from .client import QuickBooksClient

# Broad, read-only coverage of the accounting lists and transactions most useful
# to the existing QFR evidence pipeline. Region/SKU-specific failures are recorded
# by the downloader instead of aborting all other downloads.
DEFAULT_ENTITIES = (
    "Account",
    "Attachable",
    "Bill",
    "BillPayment",
    "Budget",
    "Class",
    "CreditMemo",
    "Customer",
    "Department",
    "Deposit",
    "Employee",
    "Estimate",
    "Invoice",
    "Item",
    "JournalEntry",
    "Payment",
    "PaymentMethod",
    "Purchase",
    "PurchaseOrder",
    "RefundReceipt",
    "SalesReceipt",
    "TaxCode",
    "TaxAgency",
    "TaxRate",
    "Term",
    "TimeActivity",
    "Transfer",
    "Vendor",
    "VendorCredit",
)

# QBO list queries otherwise commonly omit inactive records. Transactions do
# not use this filter.
ACTIVE_AND_INACTIVE_ENTITIES = {
    "Account",
    "Class",
    "Customer",
    "Department",
    "Employee",
    "Item",
    "PaymentMethod",
    "Term",
    "Vendor",
}


def default_where(entity_name: str) -> str | None:
    if entity_name in ACTIVE_AND_INACTIVE_ENTITIES:
        return "Active IN (true, false)"
    return None


def fetch_entities(
    client: QuickBooksClient,
    entity_names: Iterable[str] = DEFAULT_ENTITIES,
    *,
    page_size: int = 1000,
    max_pages: int = 100,
) -> dict[str, list[dict[str, Any]]]:
    return {
        entity_name: client.query_all(
            entity_name,
            where=default_where(entity_name),
            page_size=page_size,
            max_pages=max_pages,
        )
        for entity_name in entity_names
    }
