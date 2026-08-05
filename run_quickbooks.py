from __future__ import annotations

import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from ai.openai_mapper import map_description
from config import load_settings


DEFAULT_PROFIT_AND_LOSS = Path("output/quickbooks/reports/profit_and_loss.json")
DEFAULT_PROFIT_AND_LOSS_DETAIL = Path(
    "output/quickbooks/reports/profit_and_loss_detail.json"
)
DEFAULT_ACCOUNT_LIST = Path("output/quickbooks/reports/account_list.json")
DEFAULT_COMPANY_INFO = Path("output/quickbooks/company_info.json")
DEFAULT_ITEMS = Path("output/quickbooks/entities/item.json")
DEFAULT_ENTITIES_DIR = Path("output/quickbooks/entities")
DEFAULT_OUTPUT_DIR = Path("output/quickbooks/ai_rebuild")
FALLBACK_CATEGORY = "Unmapped"
QUICKBOOKS_MAPPING_POLICY_VERSION = "qfr-quickbooks-line-by-line-role-first-v4"
QUICKBOOKS_MAPPING_PROMPT = """
You are reconstructing a QuickBooks Online profit and loss report from
transaction-level evidence. The source P&L account and split account have been
deliberately hidden.

Return one JSON object only with:
- category: exactly one allowed account path
- confidence: a number between 0 and 1
- reason: a short explanation

Allowed QuickBooks P&L account paths:
{allowed_categories}

QuickBooks company profile:
{company_context}

Inferred P&L line role:
{line_role}

Matched QuickBooks Item/ProductService for this line only (all account
references removed):
{item_context}

Matched raw transaction-line evidence (all account references removed):
{transaction_context}

Visible transaction context:
- counterparty: {contact}
- description: {description}
- amount as displayed in the P&L detail report: {amount}
- transaction type: {tx_type}

Classify this one line only. Stay inside the inferred P&L line role because the
allowed paths have already been restricted to that section. For an inventory
Item, an Invoice line near quantity times PurchaseCost is COGS, while a line
near quantity times UnitPrice is income. A Refund or Credit Memo reverses the
matched Item's normal category; it does not become Discounts given unless the
Item itself represents a discount, refund, or allowance.

Use the counterparty, matched Item, raw line evidence, description, amount, and
full account hierarchy. Prefer the most specific child account only when direct
evidence supports it; otherwise retain the supported parent. Choose Unmapped
with low confidence when the visible evidence is insufficient. Do not invent an
account and do not return commentary outside the JSON object.
"""

SECTION_BY_GROUP = {
    "Income": "Income",
    "COGS": "Cost of Goods Sold",
    "Expenses": "Expenses",
    "OtherIncome": "Other Income",
    "OtherExpenses": "Other Expenses",
}
SECTION_BY_LABEL = {
    "Income": "Income",
    "Cost of Goods Sold": "Cost of Goods Sold",
    "Expenses": "Expenses",
    "Other Income": "Other Income",
    "Other Expense": "Other Expenses",
    "Other Expenses": "Other Expenses",
}
SECTION_TYPE = {
    "Income": "income",
    "Cost of Goods Sold": "cost_of_goods_sold",
    "Expenses": "expense",
    "Other Income": "other_income",
    "Other Expenses": "other_expense",
}
SECTION_NET_MULTIPLIER = {
    "Income": 1.0,
    "Cost of Goods Sold": -1.0,
    "Expenses": -1.0,
    "Other Income": 1.0,
    "Other Expenses": -1.0,
}
DETAIL_CONTAINERS = {
    "Ordinary Income/Expenses",
    "Other Income/Expense",
}


@dataclass(frozen=True)
class ProfitAndLossAccount:
    category: str
    section: str
    hierarchy: tuple[str, ...]
    account_id: str
    official_amount: float


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing QuickBooks report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"QuickBooks report must contain one JSON object: {path}")
    return payload


def _load_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Missing QuickBooks entity file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit(f"QuickBooks entity file must contain one JSON array: {path}")
    return [item for item in payload if isinstance(item, dict)]


def _nested_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("Rows", {})
    if not isinstance(rows, dict):
        return []
    result = rows.get("Row", [])
    return [row for row in result if isinstance(row, dict)] if isinstance(result, list) else []


def _child_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    rows = row.get("Rows", {})
    if not isinstance(rows, dict):
        return []
    result = rows.get("Row", [])
    return [child for child in result if isinstance(child, dict)] if isinstance(result, list) else []


def _cells(block: Any) -> list[dict[str, Any]]:
    if not isinstance(block, dict):
        return []
    cells = block.get("ColData", [])
    return [cell for cell in cells if isinstance(cell, dict)] if isinstance(cells, list) else []


def _cell_value(block: Any, index: int) -> str:
    cells = _cells(block)
    if index >= len(cells):
        return ""
    return str(cells[index].get("value") or "").strip()


def _first_cell_id(block: Any) -> str:
    cells = _cells(block)
    if not cells:
        return ""
    return str(cells[0].get("id") or "").strip()


def _money(value: Any) -> float:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0.0
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Invalid QuickBooks money value: {value!r}") from exc


def _category_name(section: str, hierarchy: Iterable[str]) -> str:
    parts = [section, *(part for part in hierarchy if part)]
    return " > ".join(parts)


def _sanitize_without_account_refs(
    value: Any,
    *,
    drop_technical_fields: bool = False,
) -> Any:
    technical_fields = {"domain", "sparse", "SyncToken", "MetaData"}
    if isinstance(value, dict):
        return {
            key: _sanitize_without_account_refs(
                child,
                drop_technical_fields=drop_technical_fields,
            )
            for key, child in value.items()
            if not key.lower().endswith("accountref")
            and (not drop_technical_fields or key not in technical_fields)
        }
    if isinstance(value, list):
        return [
            _sanitize_without_account_refs(
                child,
                drop_technical_fields=drop_technical_fields,
            )
            for child in value
        ]
    return value


def extract_official_accounts(
    payload: dict[str, Any],
) -> list[ProfitAndLossAccount]:
    accounts: dict[str, ProfitAndLossAccount] = {}

    def add_account(
        section: str,
        hierarchy: tuple[str, ...],
        block: dict[str, Any],
    ) -> None:
        account_id = _first_cell_id(block)
        if not account_id:
            return
        category = _category_name(section, hierarchy)
        account = ProfitAndLossAccount(
            category=category,
            section=section,
            hierarchy=hierarchy,
            account_id=account_id,
            official_amount=_money(_cell_value(block, 1)),
        )
        existing = accounts.get(category)
        if existing and existing != account:
            raise ValueError(f"Duplicate QuickBooks P&L account path: {category}")
        accounts[category] = account

    def walk(
        rows: list[dict[str, Any]],
        section: str | None = None,
        hierarchy: tuple[str, ...] = (),
    ) -> None:
        for row in rows:
            current_section = SECTION_BY_GROUP.get(str(row.get("group") or ""), section)
            child_hierarchy = hierarchy
            header = row.get("Header")
            header_label = _cell_value(header, 0)

            if header_label in SECTION_BY_LABEL and not _first_cell_id(header):
                current_section = SECTION_BY_LABEL[header_label]
                child_hierarchy = ()
            elif header_label and current_section and _first_cell_id(header):
                child_hierarchy = (*hierarchy, header_label)
                add_account(current_section, child_hierarchy, header)

            if "ColData" in row and current_section and _first_cell_id(row):
                label = _cell_value(row, 0)
                if label:
                    add_account(current_section, (*hierarchy, label), row)

            walk(_child_rows(row), current_section, child_hierarchy)

    walk(_nested_rows(payload))
    if not accounts:
        raise ValueError("No account rows were found in the QuickBooks ProfitAndLoss report.")
    return list(accounts.values())


def _report_column_keys(payload: dict[str, Any]) -> list[str]:
    columns = payload.get("Columns", {})
    raw_columns = columns.get("Column", []) if isinstance(columns, dict) else []
    keys: list[str] = []
    for index, column in enumerate(raw_columns if isinstance(raw_columns, list) else []):
        if not isinstance(column, dict):
            continue
        key = ""
        metadata = column.get("MetaData", [])
        for item in metadata if isinstance(metadata, list) else []:
            if isinstance(item, dict) and item.get("Name") == "ColKey":
                key = str(item.get("Value") or "").strip()
                break
        keys.append(key or str(column.get("ColTitle") or f"column_{index}"))
    return keys


def extract_account_priors(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    column_keys = _report_column_keys(payload)
    required = {
        "account_name",
        "account_type",
        "detail_acc_type",
        "account_desc",
    }
    missing = required - set(column_keys)
    if missing:
        raise ValueError(f"AccountList is missing columns: {sorted(missing)}")

    priors: dict[str, dict[str, str]] = {}
    for row in _nested_rows(payload):
        if row.get("type") != "Data" or "ColData" not in row:
            continue
        values = [_cell_value(row, index) for index in range(len(column_keys))]
        record = dict(zip(column_keys, values))
        name = str(record.get("account_name") or "").strip()
        if not name:
            continue
        priors[name] = {
            "account_type": str(record.get("account_type") or "").strip(),
            "detail_type": str(record.get("detail_acc_type") or "").strip(),
            "description": str(record.get("account_desc") or "").strip(),
        }
    if not priors:
        raise ValueError("No account metadata was found in AccountList.")
    return priors


def extract_company_prior(payload: dict[str, Any]) -> dict[str, Any]:
    company = payload.get("CompanyInfo")
    if not isinstance(company, dict):
        raise ValueError("CompanyInfo payload does not contain a CompanyInfo object.")

    name_values: dict[str, str] = {}
    raw_name_values = company.get("NameValue", [])
    for item in raw_name_values if isinstance(raw_name_values, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name") or "").strip()
        value = str(item.get("Value") or "").strip()
        if name and value:
            name_values[name] = value

    # Direct contact details, street addresses, IDs, and API metadata are not
    # useful for account classification, so they are intentionally excluded.
    prior = {
        "company_name": str(company.get("CompanyName") or "").strip(),
        "legal_name": str(company.get("LegalName") or "").strip(),
        "country": str(company.get("Country") or "").strip(),
        "company_start_date": str(company.get("CompanyStartDate") or "").strip(),
        "fiscal_year_start_month": str(
            company.get("FiscalYearStartMonth") or ""
        ).strip(),
        "supported_languages": str(company.get("SupportedLanguages") or "").strip(),
        "default_time_zone": str(company.get("DefaultTimeZone") or "").strip(),
        "features": name_values,
    }
    return prior


def extract_item_priors(payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priors = []
    for item in payload:
        prior = _sanitize_without_account_refs(item, drop_technical_fields=True)
        metadata = item.get("MetaData")
        if isinstance(metadata, dict):
            prior["CreatedTime"] = str(metadata.get("CreateTime") or "")
            prior["LastUpdatedTime"] = str(metadata.get("LastUpdatedTime") or "")
        priors.append(prior)
    priors = [item for item in priors if isinstance(item, dict) and item.get("Name")]
    if not priors:
        raise ValueError("No usable Item/ProductService metadata was found.")
    return priors


def load_transaction_entities(
    entities_dir: Path,
) -> dict[str, list[dict[str, Any]]]:
    files = {
        "Invoice": "invoice.json",
        "SalesReceipt": "sales_receipt.json",
        "CreditMemo": "credit_memo.json",
        "RefundReceipt": "refund_receipt.json",
        "Bill": "bill.json",
        "Purchase": "purchase.json",
    }
    payloads: dict[str, list[dict[str, Any]]] = {}
    for entity_type, filename in files.items():
        path = entities_dir / filename
        if path.exists():
            payloads[entity_type] = _load_json_array(path)
    return payloads


def extract_transaction_line_evidence(
    entity_payloads: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    report_types = {
        "Invoice": ("Invoice",),
        "SalesReceipt": ("Sales Receipt",),
        "CreditMemo": ("Credit Memo",),
        "RefundReceipt": ("Refund",),
        "Bill": ("Bill",),
        "Purchase": (
            "Expense",
            "Check",
            "Cash Expense",
            "Credit Card Expense",
        ),
    }
    evidence: list[dict[str, Any]] = []

    for entity_type, transactions in entity_payloads.items():
        for transaction in transactions:
            contact = ""
            for ref_name in ("CustomerRef", "VendorRef", "EntityRef"):
                reference = transaction.get(ref_name)
                if isinstance(reference, dict) and reference.get("name"):
                    contact = str(reference["name"]).strip()
                    break

            raw_lines = transaction.get("Line", [])
            for raw_line in raw_lines if isinstance(raw_lines, list) else []:
                if not isinstance(raw_line, dict):
                    continue
                detail = {}
                for detail_name in (
                    "SalesItemLineDetail",
                    "ItemBasedExpenseLineDetail",
                    "AccountBasedExpenseLineDetail",
                ):
                    candidate = raw_line.get(detail_name)
                    if isinstance(candidate, dict):
                        detail = candidate
                        break

                item_ref = detail.get("ItemRef")
                safe_item_ref = (
                    _sanitize_without_account_refs(item_ref)
                    if isinstance(item_ref, dict)
                    else {}
                )
                safe_line = _sanitize_without_account_refs(
                    {
                        "DetailType": raw_line.get("DetailType"),
                        "Description": raw_line.get("Description"),
                        "Amount": raw_line.get("Amount"),
                        "ItemRef": safe_item_ref,
                        "UnitPrice": detail.get("UnitPrice"),
                        "Qty": detail.get("Qty"),
                        "BillableStatus": detail.get("BillableStatus"),
                    }
                )
                evidence.append(
                    {
                        "EntityType": entity_type,
                        "ReportTransactionTypes": report_types.get(entity_type, ()),
                        "TransactionId": str(transaction.get("Id") or "").strip(),
                        "Date": str(transaction.get("TxnDate") or "").strip(),
                        "DocumentNumber": str(
                            transaction.get("DocNumber") or ""
                        ).strip(),
                        "Contact": contact,
                        "Description": str(
                            raw_line.get("Description") or ""
                        ).strip(),
                        "Amount": float(raw_line.get("Amount") or 0.0),
                        "ItemRefId": str(
                            safe_item_ref.get("value") or ""
                            if safe_item_ref
                            else ""
                        ).strip(),
                        "ItemRefName": str(
                            safe_item_ref.get("name") or ""
                            if safe_item_ref
                            else ""
                        ).strip(),
                        "Qty": float(detail.get("Qty") or 0.0),
                        "UnitPrice": float(detail.get("UnitPrice") or 0.0),
                        "SafeLine": safe_line,
                    }
                )
    return evidence


def extract_detail_lines(payload: dict[str, Any]) -> list[dict[str, Any]]:
    column_keys = _report_column_keys(payload)
    required = {
        "tx_date",
        "txn_type",
        "doc_num",
        "name",
        "memo",
        "split_acc",
        "subt_nat_amount",
    }
    missing = required - set(column_keys)
    if missing:
        raise ValueError(f"ProfitAndLossDetail is missing columns: {sorted(missing)}")

    lines: list[dict[str, Any]] = []

    def walk(
        rows: list[dict[str, Any]],
        section: str | None = None,
        hierarchy: tuple[str, ...] = (),
    ) -> None:
        for row in rows:
            current_section = section
            child_hierarchy = hierarchy
            header_label = _cell_value(row.get("Header"), 0)
            summary_label = _cell_value(row.get("Summary"), 0)

            if header_label in DETAIL_CONTAINERS:
                child_hierarchy = ()
            elif header_label in SECTION_BY_LABEL:
                current_section = SECTION_BY_LABEL[header_label]
                child_hierarchy = ()
            elif header_label and current_section:
                child_hierarchy = (*hierarchy, header_label)
            elif summary_label.startswith("Total for "):
                # QuickBooks nests direct parent-account transactions under a
                # synthetic "Total for <account>" container.
                child_hierarchy = hierarchy

            if row.get("type") == "Data" and "ColData" in row:
                values = [_cell_value(row, index) for index in range(len(column_keys))]
                record = dict(zip(column_keys, values))
                source_hierarchy = hierarchy
                if current_section == "Cost of Goods Sold" and not source_hierarchy:
                    # QBO collapses a sole COGS account with the same name as
                    # its report section, so detail rows sit directly below it.
                    source_hierarchy = ("Cost of Goods Sold",)
                if not current_section or not source_hierarchy:
                    raise ValueError(
                        "Found a ProfitAndLossDetail transaction outside an account section."
                    )
                amount = _money(record.get("subt_nat_amount"))
                memo = str(record.get("memo") or "").strip()
                transaction_type = str(record.get("txn_type") or "").strip()
                document_number = str(record.get("doc_num") or "").strip()
                contact = str(record.get("name") or "").strip()
                ai_description_parts = []
                if memo:
                    ai_description_parts.append(memo)
                if document_number:
                    ai_description_parts.append(f"Document {document_number}")
                if not ai_description_parts:
                    ai_description_parts.append(
                        f"{transaction_type or 'QuickBooks transaction'} involving "
                        f"{contact or 'an unspecified counterparty'}"
                    )
                lines.append(
                    {
                        "LineNumber": len(lines) + 1,
                        "Date": str(record.get("tx_date") or "").strip(),
                        "TransactionType": transaction_type,
                        "DocumentNumber": document_number,
                        "Contact": contact,
                        "Description": memo,
                        "SplitAccountForAudit": str(record.get("split_acc") or "").strip(),
                        "Amount": amount,
                        "SourceAccountForAudit": _category_name(
                            current_section,
                            source_hierarchy,
                        ),
                        "SourceSectionForAudit": current_section,
                        "AIInputDescription": "; ".join(ai_description_parts),
                        "AccountHiddenFromAI": True,
                    }
                )

            walk(_child_rows(row), current_section, child_hierarchy)

    walk(_nested_rows(payload))
    if not lines:
        raise ValueError("No transaction rows were found in ProfitAndLossDetail.")
    return lines


def extract_net_income(payload: dict[str, Any]) -> float:
    def walk(rows: list[dict[str, Any]]) -> float | None:
        for row in rows:
            for block in (row.get("Summary"), row):
                if _cell_value(block, 0).strip().lower() == "net income":
                    return _money(_cell_value(block, 1))
            found = walk(_child_rows(row))
            if found is not None:
                return found
        return None

    result = walk(_nested_rows(payload))
    if result is None:
        raise ValueError("Net Income was not found in the QuickBooks ProfitAndLoss report.")
    return result


def _validate_report_headers(
    profit_and_loss: dict[str, Any],
    detail: dict[str, Any],
) -> dict[str, str]:
    summary_header = profit_and_loss.get("Header", {})
    detail_header = detail.get("Header", {})
    fields = ("ReportBasis", "StartPeriod", "EndPeriod", "Currency")
    metadata: dict[str, str] = {}
    for field in fields:
        summary_value = str(summary_header.get(field) or "")
        detail_value = str(detail_header.get(field) or "")
        if summary_value != detail_value:
            raise ValueError(
                f"QuickBooks report header mismatch for {field}: "
                f"{summary_value!r} != {detail_value!r}"
            )
        metadata[field] = summary_value
    return metadata


def _source_parse_comparison(
    accounts: list[ProfitAndLossAccount],
    detail_lines: list[dict[str, Any]],
    tolerance: float,
) -> pd.DataFrame:
    official = {account.category: account.official_amount for account in accounts}
    source_totals: dict[str, float] = {}
    for line in detail_lines:
        category = str(line["SourceAccountForAudit"])
        source_totals[category] = source_totals.get(category, 0.0) + float(line["Amount"])

    rows = []
    for category in sorted(set(official) | set(source_totals)):
        official_amount = official.get(category, 0.0)
        detail_amount = source_totals.get(category, 0.0)
        difference = detail_amount - official_amount
        rows.append(
            {
                "Account": category,
                "OfficialAmount": official_amount,
                "DetailAmount": detail_amount,
                "Difference": difference,
                "AbsDifference": abs(difference),
                "Status": "Match" if abs(difference) <= tolerance else "Mismatch",
            }
        )
    return pd.DataFrame(rows)


def _allowed_categories(
    accounts: list[ProfitAndLossAccount],
    account_priors: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    categories = []
    for account in accounts:
        account_list_name = ":".join(account.hierarchy)
        prior = account_priors.get(account_list_name, {})
        metadata = [
            f"QuickBooks report section: {account.section}",
            f"account hierarchy: {' > '.join(account.hierarchy)}",
        ]
        if prior.get("account_type"):
            metadata.append(f"AccountList type: {prior['account_type']}")
        if prior.get("detail_type"):
            metadata.append(f"AccountList detail type: {prior['detail_type']}")
        if prior.get("description"):
            metadata.append(f"AccountList description: {prior['description']}")
        categories.append(
            {
                "name": account.category,
                "type": SECTION_TYPE[account.section],
                "description": "; ".join(metadata) + ".",
            }
        )
    categories.append(
        {
            "name": FALLBACK_CATEGORY,
            "type": "fallback",
            "description": "Use only when the line cannot be assigned to a listed P&L account.",
        }
    )
    return categories


def _normalized_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _match_transaction_line(
    detail_line: dict[str, Any],
    transaction_evidence: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, int]:
    transaction_type = str(detail_line.get("TransactionType") or "")
    detail_date = str(detail_line.get("Date") or "")
    document_number = _normalized_text(detail_line.get("DocumentNumber"))
    contact = _normalized_text(detail_line.get("Contact"))
    description = _normalized_text(detail_line.get("Description"))
    amount = abs(float(detail_line.get("Amount") or 0.0))
    scored: list[tuple[int, dict[str, Any]]] = []

    for candidate in transaction_evidence:
        if transaction_type not in candidate.get("ReportTransactionTypes", ()):
            continue
        score = 0
        candidate_document = _normalized_text(candidate.get("DocumentNumber"))
        candidate_contact = _normalized_text(candidate.get("Contact"))
        candidate_description = _normalized_text(candidate.get("Description"))

        if detail_date and detail_date == candidate.get("Date"):
            score += 4
        if document_number and candidate_document:
            if document_number != candidate_document:
                continue
            score += 10
        if contact and candidate_contact and contact == candidate_contact:
            score += 4
        if description and candidate_description:
            if description == candidate_description:
                score += 10
            elif description in candidate_description or candidate_description in description:
                score += 6
        candidate_amount = abs(float(candidate.get("Amount") or 0.0))
        if abs(amount - candidate_amount) <= 0.01:
            score += 5
        if score >= 9:
            scored.append((score, candidate))

    if not scored:
        return None, 0
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score = scored[0][0]
    best = [candidate for score, candidate in scored if score == best_score]
    item_ids = {str(candidate.get("ItemRefId") or "") for candidate in best}
    if len(item_ids) > 1:
        return None, best_score
    return best[0], best_score


def _amount_matches(actual: float, expected: float) -> bool:
    tolerance = max(0.01, abs(expected) * 0.005)
    return expected > 0 and abs(abs(actual) - abs(expected)) <= tolerance


def _infer_line_role(
    line: dict[str, Any],
    matched_transaction: dict[str, Any] | None,
    matched_item: dict[str, Any] | None,
) -> tuple[str, str]:
    transaction_type = str(line.get("TransactionType") or "")
    expense_types = {
        "Bill",
        "Expense",
        "Check",
        "Cash Expense",
        "Credit Card Expense",
    }
    sales_types = {"Invoice", "Sales Receipt", "Credit Memo", "Refund"}

    amount = float(line.get("Amount") or 0.0)
    if transaction_type in expense_types and amount < 0:
        return (
            "unknown",
            f"Negative {transaction_type} is a reversal whose original section is ambiguous.",
        )
    if transaction_type in expense_types:
        return "expense", f"{transaction_type} is a purchase-side transaction."
    if transaction_type not in sales_types:
        return "unknown", "Transaction type does not establish a P&L section."

    if matched_item and str(matched_item.get("Type") or "") == "Inventory":
        quantity = float((matched_transaction or {}).get("Qty") or 0.0)
        quantity = quantity or 1.0
        purchase_cost = float(matched_item.get("PurchaseCost") or 0.0)
        raw_sale_amount = float((matched_transaction or {}).get("Amount") or 0.0)
        catalogue_unit_price = float(matched_item.get("UnitPrice") or 0.0)
        expected_cost = quantity * purchase_cost
        expected_sale = raw_sale_amount or quantity * catalogue_unit_price
        cost_match = _amount_matches(amount, expected_cost)
        sale_match = _amount_matches(amount, expected_sale)
        if cost_match and not sale_match:
            return (
                "cost_of_goods_sold",
                f"Inventory amount matches Qty x PurchaseCost ({quantity:g} x "
                f"{purchase_cost:g} = {expected_cost:g}).",
            )
        if sale_match:
            return (
                "income",
                f"Inventory amount matches the raw sales line ({expected_sale:g}).",
            )
        return (
            "unknown",
            "Inventory line did not uniquely match expected purchase cost or sales value.",
        )

    if matched_item or transaction_type in {"Credit Memo", "Refund"}:
        return "income", f"{transaction_type} is treated as an income-side reversal or sale."
    description = _normalized_text(line.get("Description"))
    if "discount" in description:
        return "income", "Visible description identifies an income-side discount."
    raw_amount = float((matched_transaction or {}).get("Amount") or 0.0)
    if _amount_matches(amount, raw_amount):
        return "income", "P&L amount matches the raw sales transaction line."
    return "unknown", "Sales transaction could also contain an unmatched inventory COGS line."


def _categories_for_role(
    allowed_categories: list[dict[str, str]],
    role: str,
    transaction_type: str,
    matched_item: dict[str, Any] | None,
) -> list[dict[str, str]]:
    if role == "unknown":
        selected = list(allowed_categories)
    else:
        selected = [
            category
            for category in allowed_categories
            if category["type"] in {role, "fallback"}
        ]

    item_text = _normalized_text(
        " ".join(
            str((matched_item or {}).get(field) or "")
            for field in ("Name", "Description", "PurchaseDesc")
        )
    )
    is_discount_item = any(
        token in item_text for token in ("discount", "refund", "allowance")
    )
    if transaction_type in {"Credit Memo", "Refund"} and not is_discount_item:
        selected = [
            category
            for category in selected
            if not category["name"].endswith(" > Discounts given")
        ]
    return selected


def _rule_based_category(
    line: dict[str, Any],
    role: str,
    allowed_categories: list[dict[str, str]],
    matched_item: dict[str, Any] | None = None,
    temporal_ambiguity: bool = False,
) -> tuple[str, str] | None:
    allowed_names = {category["name"] for category in allowed_categories}
    if role == "cost_of_goods_sold":
        cogs = [
            category["name"]
            for category in allowed_categories
            if category["type"] == "cost_of_goods_sold"
        ]
        if len(cogs) == 1:
            return cogs[0], "role-first-cogs"

    if role == "income" and matched_item:
        item_text = _normalized_text(
            " ".join(
                str(matched_item.get(field) or "")
                for field in ("Name", "Description", "PurchaseDesc")
            )
        )
        item_type = str(matched_item.get("Type") or "")
        semantic_rules = (
            (
                ("weekly gardening", "tree and shrub trimming"),
                "Income > Landscaping Services",
                "matched-general-landscaping-service",
            ),
            (
                ("concrete for fountain", "garden lighting", "garden rocks"),
                (
                    "Income > Landscaping Services > Job Materials > "
                    "Fountains and Garden Lighting"
                ),
                "matched-fountain-material",
            ),
            (
                ("sod", "2 cubic ft bag", "soil"),
                "Income > Landscaping Services > Job Materials > Plants and Soil",
                "matched-plant-soil-material",
            ),
        )
        for terms, category, rule_id in semantic_rules:
            if category in allowed_names and any(term in item_text for term in terms):
                return category, rule_id
        sales_product = "Income > Sales of Product Income"
        if (
            item_type == "Inventory"
            and not temporal_ambiguity
            and sales_product in allowed_names
        ):
            return sales_product, "current-inventory-product-sale"

    if role != "expense":
        return None
    visible = _normalized_text(
        " ".join(
            str(line.get(field) or "")
            for field in ("Contact", "Description", "AIInputDescription")
        )
    )
    amount = abs(float(line.get("Amount") or 0.0))
    if (
        "Expenses > Automobile > Fuel" in allowed_names
        and ("chin s gas and oil" in visible or "fuel" in visible)
        and amount < 100
    ):
        return "Expenses > Automobile > Fuel", "visible-fuel-supplier"

    rules = (
        (
            ("bodyshop", "repairs on the truck", "equipment repair"),
            "Expenses > Maintenance and Repair > Equipment Repairs",
            "visible-equipment-repair",
        ),
        (
            ("squeaky kleen car wash", "car wash"),
            "Expenses > Automobile",
            "visible-car-wash",
        ),
        (
            ("bob s burger joint", "restaurant"),
            "Expenses > Meals and Entertainment",
            "visible-meals-vendor",
        ),
        (
            ("pg e",),
            "Expenses > Utilities > Gas and Electric",
            "visible-electric-utility",
        ),
        (
            ("lumber",),
            "Expenses > Job Expenses > Job Materials > Decks and Patios",
            "visible-deck-material",
        ),
    )
    for terms, category, rule_id in rules:
        if category in allowed_names and any(term in visible for term in terms):
            return category, rule_id
    return None


def _item_has_temporal_ambiguity(
    line: dict[str, Any],
    matched_item: dict[str, Any] | None,
) -> bool:
    if not matched_item:
        return False
    try:
        transaction_date = date.fromisoformat(str(line.get("Date") or ""))
    except ValueError:
        return False

    timestamps = []
    for field in ("CreatedTime", "LastUpdatedTime"):
        value = str(matched_item.get(field) or "")
        if not value:
            continue
        try:
            timestamps.append(datetime.fromisoformat(value).date())
        except ValueError:
            continue
    if not timestamps:
        return False
    created = timestamps[0]
    last_updated = timestamps[-1]
    return transaction_date < created or (
        last_updated > created and transaction_date < last_updated
    )


def _map_lines(
    detail_lines: list[dict[str, Any]],
    allowed_categories: list[dict[str, str]],
    company_prior: dict[str, Any],
    item_priors: list[dict[str, Any]],
    transaction_evidence: list[dict[str, Any]],
    workers: int,
    timeout_seconds: float,
    review_threshold: float,
) -> list[dict[str, Any]]:
    mapped_rows: list[dict[str, Any] | None] = [None] * len(detail_lines)
    item_by_id = {
        str(item.get("Id") or ""): item
        for item in item_priors
        if str(item.get("Id") or "")
    }
    company_context = json.dumps(
        company_prior,
        sort_keys=True,
        ensure_ascii=True,
    )
    escaped_company_context = company_context.replace("{", "{{").replace("}", "}}")

    def map_one(index: int, line: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        matched_transaction, match_score = _match_transaction_line(
            line,
            transaction_evidence,
        )
        matched_item = item_by_id.get(
            str((matched_transaction or {}).get("ItemRefId") or "")
        )
        role, role_reason = _infer_line_role(line, matched_transaction, matched_item)
        line_categories = _categories_for_role(
            allowed_categories,
            role,
            str(line.get("TransactionType") or ""),
            matched_item,
        )
        temporal_ambiguity = _item_has_temporal_ambiguity(line, matched_item)
        rule_result = _rule_based_category(
            line,
            role,
            line_categories,
            matched_item,
            temporal_ambiguity,
        )

        if rule_result:
            category, rule_id = rule_result
            result = {
                "category": category,
                "confidence": 0.99,
                "reason": f"Visible-evidence rule {rule_id}; {role_reason}",
                "rule_id": rule_id,
            }
        else:
            item_context = json.dumps(
                matched_item or {"matched_item": None},
                sort_keys=True,
                ensure_ascii=True,
            )
            transaction_context = json.dumps(
                (
                    {
                        "EntityType": matched_transaction.get("EntityType"),
                        "TransactionId": matched_transaction.get("TransactionId"),
                        "Date": matched_transaction.get("Date"),
                        "DocumentNumber": matched_transaction.get("DocumentNumber"),
                        "Contact": matched_transaction.get("Contact"),
                        "SafeLine": matched_transaction.get("SafeLine"),
                    }
                    if matched_transaction
                    else {"matched_transaction_line": None}
                ),
                sort_keys=True,
                ensure_ascii=True,
            )
            if "AccountRef" in item_context or "AccountRef" in transaction_context:
                raise ValueError("An account reference reached the safe line context.")
            prompt_template = (
                QUICKBOOKS_MAPPING_PROMPT.replace(
                    "{company_context}",
                    escaped_company_context,
                )
                .replace(
                    "{line_role}",
                    role.replace("{", "{{").replace("}", "}}"),
                )
                .replace(
                    "{item_context}",
                    item_context.replace("{", "{{").replace("}", "}}"),
                )
                .replace(
                    "{transaction_context}",
                    transaction_context.replace("{", "{{").replace("}", "}}"),
                )
            )

            # SourceAccountForAudit and SplitAccountForAudit are deliberately
            # excluded. Each request receives only this line's safe evidence.
            result = map_description(
                contact=str(line.get("Contact") or ""),
                description=str(line.get("AIInputDescription") or ""),
                amount=float(line.get("Amount") or 0.0),
                allowed_categories=line_categories,
                account_code=None,
                account_name=None,
                tx_type=str(line.get("TransactionType") or ""),
                request_timeout_seconds=timeout_seconds,
                prompt_template=prompt_template,
                mapping_policy_version=QUICKBOOKS_MAPPING_POLICY_VERSION,
            )

        mapped_category = str(result.get("category") or FALLBACK_CATEGORY)
        confidence = float(result.get("confidence") or 0.0)
        rule_id = str(result.get("rule_id") or "")
        review_reasons = []
        if role == "unknown":
            review_reasons.append("P&L line role is ambiguous")
        if temporal_ambiguity:
            review_reasons.append("Item metadata changed after this transaction")
        if mapped_category == FALLBACK_CATEGORY:
            review_reasons.append("No supported account was proposed")
        if confidence <= review_threshold:
            review_reasons.append(
                f"Confidence {confidence:.2f} is below {review_threshold:.2f}"
            )
        if (
            not matched_item
            and not str(line.get("Description") or "").strip()
            and not rule_id
        ):
            review_reasons.append("No matched Item or line description")

        mapped = dict(line)
        mapped.update(
            {
                "MappedCategory": mapped_category,
                "Confidence": confidence,
                "Reason": str(result.get("reason") or ""),
                "RuleID": rule_id,
                "InferredRole": role,
                "RoleReason": role_reason,
                "MatchedEntityType": str(
                    (matched_transaction or {}).get("EntityType") or ""
                ),
                "MatchedTransactionId": str(
                    (matched_transaction or {}).get("TransactionId") or ""
                ),
                "TransactionMatchScore": match_score,
                "MatchedItemId": str((matched_item or {}).get("Id") or ""),
                "MatchedItemName": str((matched_item or {}).get("Name") or ""),
                "ReviewRequired": bool(review_reasons),
                "ReviewReason": "; ".join(review_reasons),
                "AutoAcceptedCategory": (
                    "" if review_reasons else mapped_category
                ),
            }
        )
        return index, mapped

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(map_one, index, line): index
            for index, line in enumerate(detail_lines)
        }
        for future in as_completed(futures):
            index, mapped = future.result()
            mapped_rows[index] = mapped
            completed += 1
            if completed == len(detail_lines) or completed % 10 == 0:
                print(f"Mapped {completed}/{len(detail_lines)} QuickBooks P&L lines.")

    return [row for row in mapped_rows if row is not None]


def _rebuild_comparison(
    accounts: list[ProfitAndLossAccount],
    mapped_rows: list[dict[str, Any]],
    tolerance: float,
) -> pd.DataFrame:
    account_by_category = {account.category: account for account in accounts}
    mapped_totals: dict[str, float] = {}
    mapped_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for row in mapped_rows:
        mapped_category = str(row["MappedCategory"])
        source_category = str(row["SourceAccountForAudit"])
        mapped_totals[mapped_category] = mapped_totals.get(mapped_category, 0.0) + float(
            row["Amount"]
        )
        mapped_counts[mapped_category] = mapped_counts.get(mapped_category, 0) + 1
        source_counts[source_category] = source_counts.get(source_category, 0) + 1

    rows = []
    categories = sorted(set(account_by_category) | set(mapped_totals))
    for category in categories:
        account = account_by_category.get(category)
        official_amount = account.official_amount if account else 0.0
        rebuilt_amount = mapped_totals.get(category, 0.0)
        difference = rebuilt_amount - official_amount
        rows.append(
            {
                "Account": category,
                "Section": account.section if account else FALLBACK_CATEGORY,
                "OfficialAmount": official_amount,
                "AIRebuiltAmount": rebuilt_amount,
                "Difference": difference,
                "AbsDifference": abs(difference),
                "OfficialLineCount": source_counts.get(category, 0),
                "AIRebuiltLineCount": mapped_counts.get(category, 0),
                "Status": "Match" if abs(difference) <= tolerance else "Mismatch",
            }
        )
    return pd.DataFrame(rows)


def _mapping_error_analysis(
    mapping_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    incorrect = mapping_df[
        mapping_df["MappedCategory"] != mapping_df["SourceAccountForAudit"]
    ].copy()

    def section(category: str) -> str:
        return FALLBACK_CATEGORY if category == FALLBACK_CATEGORY else category.split(" > ")[0]

    def relation(row: pd.Series) -> str:
        source = str(row["SourceAccountForAudit"])
        mapped = str(row["MappedCategory"])
        if mapped == FALLBACK_CATEGORY:
            return "Unmapped / insufficient evidence"
        if source.startswith(f"{mapped} > ") or mapped.startswith(f"{source} > "):
            return "Parent-child granularity"
        source_section = section(source)
        mapped_section = section(mapped)
        if source_section == mapped_section:
            return "Same-section sibling account"
        return f"Cross-section: {source_section} -> {mapped_section}"

    incorrect["ErrorClass"] = incorrect.apply(relation, axis=1)
    wrong_absolute_amount = float(incorrect["Amount"].abs().sum())
    breakdown = (
        incorrect.groupby("ErrorClass", as_index=False)
        .agg(
            LineCount=("Amount", "size"),
            AbsoluteLineAmount=("Amount", lambda values: values.abs().sum()),
        )
        .sort_values("AbsoluteLineAmount", ascending=False)
    )
    breakdown["ShareOfWrongLines"] = breakdown["LineCount"] / max(len(incorrect), 1)
    breakdown["ShareOfWrongAbsoluteAmount"] = (
        breakdown["AbsoluteLineAmount"] / max(wrong_absolute_amount, 1.0)
    )

    error_pairs = (
        incorrect.groupby(
            ["SourceAccountForAudit", "MappedCategory", "ErrorClass"],
            as_index=False,
        )
        .agg(
            LineCount=("Amount", "size"),
            NetAmount=("Amount", "sum"),
            AbsoluteLineAmount=("Amount", lambda values: values.abs().sum()),
        )
        .sort_values(["AbsoluteLineAmount", "LineCount"], ascending=False)
    )

    has_memo = mapping_df["Description"].fillna("").astype(str).str.strip().ne("")
    correct = mapping_df["MappedCategory"] == mapping_df["SourceAccountForAudit"]
    memo_metrics: dict[str, Any] = {}
    for label, mask in (("with_memo", has_memo), ("without_memo", ~has_memo)):
        subset = mapping_df[mask]
        subset_correct = correct[mask]
        subset_absolute_amount = float(subset["Amount"].abs().sum())
        correct_absolute_amount = float(subset.loc[subset_correct, "Amount"].abs().sum())
        memo_metrics[label] = {
            "line_count": int(len(subset)),
            "correct_line_count": int(subset_correct.sum()),
            "line_accuracy": float(subset_correct.mean()) if len(subset) else 0.0,
            "amount_weighted_accuracy": (
                correct_absolute_amount / subset_absolute_amount
                if subset_absolute_amount
                else 0.0
            ),
        }

    evidence = {
        "incorrect_line_count": int(len(incorrect)),
        "incorrect_absolute_line_amount": wrong_absolute_amount,
        "memo_availability": memo_metrics,
    }
    return breakdown, error_pairs, evidence


def _human_audit_exports(
    mapping_df: pd.DataFrame,
    rebuild: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    audit = mapping_df.copy()
    correct = audit["MappedCategory"] == audit["SourceAccountForAudit"]

    def difference_type(row: pd.Series) -> str:
        source = str(row["SourceAccountForAudit"])
        mapped = str(row["MappedCategory"])
        if source == mapped:
            return "Exact match"
        if mapped == FALLBACK_CATEGORY:
            return "Unmapped"
        if source.startswith(f"{mapped} > "):
            return "Classified to parent"
        if mapped.startswith(f"{source} > "):
            return "Classified to child"
        source_section = source.split(" > ")[0]
        mapped_section = mapped.split(" > ")[0]
        if source_section == mapped_section:
            return "Different account in same section"
        return f"Cross-section: {source_section} -> {mapped_section}"

    audit["ClassificationStatus"] = correct.map(
        {True: "Correct", False: "Misclassified"}
    )
    audit["DifferenceType"] = audit.apply(difference_type, axis=1)
    audit["WorkflowStatus"] = audit["ReviewRequired"].map(
        {True: "HITL review required", False: "Auto-accepted"}
    )
    audit["HumanDecision"] = ""
    audit["HumanCorrectAccount"] = ""
    audit["HumanNotes"] = ""
    audit = audit.rename(
        columns={
            "SourceAccountForAudit": "OriginalQuickBooksAccount",
            "SourceSectionForAudit": "OriginalQuickBooksSection",
            "MappedCategory": "ClassifiedAccount",
            "MatchedItemName": "MatchedItem",
            "Reason": "ClassificationReason",
        }
    )
    columns = [
        "LineNumber",
        "Date",
        "TransactionType",
        "DocumentNumber",
        "Contact",
        "Description",
        "Amount",
        "OriginalQuickBooksSection",
        "OriginalQuickBooksAccount",
        "ClassifiedAccount",
        "ClassificationStatus",
        "DifferenceType",
        "Confidence",
        "InferredRole",
        "MatchedItem",
        "WorkflowStatus",
        "ReviewReason",
        "RuleID",
        "ClassificationReason",
        "HumanDecision",
        "HumanCorrectAccount",
        "HumanNotes",
    ]
    all_lines = audit[columns].copy()
    misclassified = all_lines[
        all_lines["ClassificationStatus"] == "Misclassified"
    ].copy()

    account_audit = rebuild.rename(
        columns={
            "Account": "QuickBooksAccount",
            "OfficialAmount": "OriginalQuickBooksAmount",
            "AIRebuiltAmount": "ClassifiedAmount",
            "Difference": "ClassifiedMinusOriginal",
            "AbsDifference": "AbsoluteDifference",
            "OfficialLineCount": "OriginalLineCount",
            "AIRebuiltLineCount": "ClassifiedLineCount",
        }
    )[
        [
            "Section",
            "QuickBooksAccount",
            "OriginalQuickBooksAmount",
            "ClassifiedAmount",
            "ClassifiedMinusOriginal",
            "AbsoluteDifference",
            "OriginalLineCount",
            "ClassifiedLineCount",
            "Status",
        ]
    ].sort_values("AbsoluteDifference", ascending=False)
    return account_audit, all_lines, misclassified


def _rebuilt_net_income(
    mapped_rows: list[dict[str, Any]],
    accounts: list[ProfitAndLossAccount],
) -> float:
    section_by_category = {account.category: account.section for account in accounts}
    total = 0.0
    for row in mapped_rows:
        section = section_by_category.get(str(row["MappedCategory"]))
        if section:
            total += float(row["Amount"]) * SECTION_NET_MULTIPLIER[section]
    return total


def _write_dataframe(df: pd.DataFrame, base_path: Path) -> None:
    df.to_csv(base_path.with_suffix(".csv"), index=False)
    df.to_excel(base_path.with_suffix(".xlsx"), index=False)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Blindly classify QuickBooks ProfitAndLossDetail lines, rebuild the "
            "P&L by account, and compare it with the official ProfitAndLoss report."
        )
    )
    parser.add_argument("--profit-and-loss", type=Path, default=DEFAULT_PROFIT_AND_LOSS)
    parser.add_argument(
        "--profit-and-loss-detail",
        type=Path,
        default=DEFAULT_PROFIT_AND_LOSS_DETAIL,
    )
    parser.add_argument("--account-list", type=Path, default=DEFAULT_ACCOUNT_LIST)
    parser.add_argument("--company-info", type=Path, default=DEFAULT_COMPANY_INFO)
    parser.add_argument("--items", type=Path, default=DEFAULT_ITEMS)
    parser.add_argument(
        "--entities-dir",
        type=Path,
        default=DEFAULT_ENTITIES_DIR,
        help="Directory containing raw QuickBooks transaction entity JSON files.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--mapping-workers",
        type=int,
        default=_env_int("AI_MAPPING_WORKERS", 4),
    )
    parser.add_argument(
        "--ai-timeout",
        type=float,
        default=_env_float("OPENAI_TIMEOUT_SECONDS", 30.0),
    )
    parser.add_argument("--tolerance", type=float, default=0.01)
    parser.add_argument(
        "--review-threshold",
        type=float,
        default=0.70,
        help="Send proposed mappings below this confidence to HITL.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate report parsing without sending lines to OpenAI.",
    )
    args = parser.parse_args()
    if not 1 <= args.mapping_workers <= 32:
        parser.error("--mapping-workers must be between 1 and 32.")
    if not 1.0 <= args.ai_timeout <= 120.0:
        parser.error("--ai-timeout must be between 1 and 120 seconds.")
    if args.tolerance < 0:
        parser.error("--tolerance must be non-negative.")
    if not 0 <= args.review_threshold <= 1:
        parser.error("--review-threshold must be between 0 and 1.")
    return args


def main() -> None:
    args = parse_args()
    profit_and_loss = _load_json(args.profit_and_loss)
    detail = _load_json(args.profit_and_loss_detail)
    account_list = _load_json(args.account_list)
    company_info = _load_json(args.company_info)
    items = _load_json_array(args.items)
    report_metadata = _validate_report_headers(profit_and_loss, detail)
    accounts = extract_official_accounts(profit_and_loss)
    account_priors = extract_account_priors(account_list)
    company_prior = extract_company_prior(company_info)
    item_priors = extract_item_priors(items)
    entity_payloads = load_transaction_entities(args.entities_dir)
    transaction_evidence = extract_transaction_line_evidence(entity_payloads)
    detail_lines = extract_detail_lines(detail)
    official_net_income = extract_net_income(profit_and_loss)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    source_comparison = _source_parse_comparison(accounts, detail_lines, args.tolerance)
    _write_dataframe(
        source_comparison,
        output_dir / "quickbooks_pl_source_parse_diff",
    )
    source_max_difference = float(source_comparison["AbsDifference"].max())
    source_valid = bool((source_comparison["AbsDifference"] <= args.tolerance).all())
    matched_transaction_line_count = sum(
        _match_transaction_line(line, transaction_evidence)[0] is not None
        for line in detail_lines
    )
    print(
        f"Parsed {len(detail_lines)} detail lines across {len(accounts)} P&L accounts. "
        f"Loaded {len(account_priors)} AccountList entries and "
        f"{len(item_priors)} safe Item priors. Matched raw transaction evidence "
        f"for {matched_transaction_line_count}/{len(detail_lines)} lines. "
        f"Source parse max difference: {source_max_difference:,.6f}."
    )
    if not source_valid:
        raise SystemExit(
            "ProfitAndLossDetail does not reconcile to ProfitAndLoss after parsing. "
            "Review quickbooks_pl_source_parse_diff.csv before running AI."
        )
    if args.validate_only:
        print("Validation complete; no lines were sent to OpenAI.")
        return

    settings = load_settings()
    if not (settings.openai_api_key_qfr or settings.openai_api_key):
        raise SystemExit("Set OPENAI_API_KEY_QFR or OPENAI_API_KEY before running AI mapping.")

    allowed_categories = _allowed_categories(accounts, account_priors)
    mapped_rows = _map_lines(
        detail_lines,
        allowed_categories,
        company_prior,
        item_priors,
        transaction_evidence,
        args.mapping_workers,
        args.ai_timeout,
        args.review_threshold,
    )
    mapping_df = pd.DataFrame(mapped_rows)
    _write_dataframe(
        mapping_df,
        output_dir / "quickbooks_pl_blind_line_mapping",
    )
    hitl_queue = mapping_df[mapping_df["ReviewRequired"]].copy()
    _write_dataframe(
        hitl_queue,
        output_dir / "quickbooks_pl_hitl_queue",
    )
    auto_accepted_lines = mapping_df[~mapping_df["ReviewRequired"]].copy()
    _write_dataframe(
        auto_accepted_lines,
        output_dir / "quickbooks_pl_auto_accepted_lines",
    )

    rebuild = _rebuild_comparison(accounts, mapped_rows, args.tolerance)
    _write_dataframe(
        rebuild,
        output_dir / "quickbooks_pl_blind_rebuild_diff",
    )
    account_audit, all_line_audit, misclassified_line_audit = (
        _human_audit_exports(mapping_df, rebuild)
    )
    _write_dataframe(
        account_audit,
        output_dir / "quickbooks_pl_official_vs_classified_accounts",
    )
    _write_dataframe(
        all_line_audit,
        output_dir / "quickbooks_pl_all_lines_human_audit",
    )
    _write_dataframe(
        misclassified_line_audit,
        output_dir / "quickbooks_pl_misclassified_lines",
    )
    error_breakdown, error_pairs, error_evidence = _mapping_error_analysis(mapping_df)
    _write_dataframe(
        error_breakdown,
        output_dir / "quickbooks_pl_error_breakdown",
    )
    _write_dataframe(
        error_pairs,
        output_dir / "quickbooks_pl_error_pairs",
    )

    active_rebuild = rebuild[
        (rebuild["OfficialAmount"].abs() > args.tolerance)
        | (rebuild["AIRebuiltAmount"].abs() > args.tolerance)
    ].copy()
    exact_line_matches = int(
        (
            mapping_df["MappedCategory"]
            == mapping_df["SourceAccountForAudit"]
        ).sum()
    )
    correct_mask = (
        mapping_df["MappedCategory"] == mapping_df["SourceAccountForAudit"]
    )
    review_mask = mapping_df["ReviewRequired"].astype(bool)
    auto_accepted_mask = ~review_mask
    auto_accepted_correct = int((correct_mask & auto_accepted_mask).sum())
    incorrect_line_count = int((~correct_mask).sum())
    reviewed_incorrect = int((review_mask & ~correct_mask).sum())
    section_by_category = {
        account.category: account.section for account in accounts
    }
    auto_accepted_source_net_income = float(
        sum(
            float(row["Amount"])
            * SECTION_NET_MULTIPLIER[str(row["SourceSectionForAudit"])]
            for _, row in mapping_df[auto_accepted_mask].iterrows()
        )
    )
    auto_accepted_rebuilt_net_income = float(
        sum(
            float(row["Amount"])
            * SECTION_NET_MULTIPLIER[
                section_by_category[str(row["MappedCategory"])]
            ]
            for _, row in mapping_df[auto_accepted_mask].iterrows()
            if str(row["MappedCategory"]) in section_by_category
        )
    )
    absolute_line_amount = float(mapping_df["Amount"].abs().sum())
    matched_absolute_amount = float(
        mapping_df.loc[
            mapping_df["MappedCategory"] == mapping_df["SourceAccountForAudit"],
            "Amount",
        ]
        .abs()
        .sum()
    )
    rebuilt_net_income = _rebuilt_net_income(mapped_rows, accounts)
    net_income_difference = rebuilt_net_income - official_net_income
    summary = {
        "report": report_metadata,
        "experiment": {
            "blind_line_classification": True,
            "target_taxonomy": "Account paths extracted from QuickBooks ProfitAndLoss",
            "original_profit_and_loss_account_passed_to_ai": False,
            "split_account_passed_to_ai": False,
            "account_list_metadata_passed_to_ai": True,
            "company_profile_passed_to_ai": True,
            "item_business_metadata_passed_to_ai": True,
            "item_account_references_passed_to_ai": False,
            "line_by_line_mapping_requests": True,
            "single_matched_item_passed_per_line": True,
            "section_role_inferred_before_account_mapping": True,
            "raw_transaction_account_references_passed_to_ai": False,
            "company_contact_and_address_fields_excluded": True,
            "source_account_retained_in_output_for_post_mapping_audit": True,
        },
        "prior_knowledge": {
            "account_list_entry_count": len(account_priors),
            "matched_profit_and_loss_account_count": sum(
                ":".join(account.hierarchy) in account_priors for account in accounts
            ),
            "matched_accounts_with_nonempty_description": sum(
                bool(account_priors.get(":".join(account.hierarchy), {}).get("description"))
                for account in accounts
            ),
            "company_industry": company_prior["features"].get("QBOIndustryType", ""),
            "company_country": company_prior["country"],
            "company_fiscal_year_start_month": company_prior[
                "fiscal_year_start_month"
            ],
            "item_prior_count": len(item_priors),
            "raw_transaction_line_evidence_count": len(transaction_evidence),
            "detail_lines_with_matched_transaction_evidence": (
                matched_transaction_line_count
            ),
        },
        "source_parse": {
            "detail_line_count": len(detail_lines),
            "official_account_count": len(accounts),
            "all_accounts_within_tolerance": source_valid,
            "maximum_absolute_difference": source_max_difference,
            "tolerance": args.tolerance,
        },
        "classification": {
            "exact_line_matches": exact_line_matches,
            "line_count": len(mapped_rows),
            "line_accuracy": exact_line_matches / len(mapped_rows),
            "absolute_amount_weighted_accuracy": (
                matched_absolute_amount / absolute_line_amount
                if absolute_line_amount
                else 0.0
            ),
            "unmapped_line_count": int(
                (mapping_df["MappedCategory"] == FALLBACK_CATEGORY).sum()
            ),
            "low_confidence_line_count_below_0_80": int(
                (mapping_df["Confidence"] < 0.80).sum()
            ),
            "hitl_review_line_count": int(mapping_df["ReviewRequired"].sum()),
            "auto_accepted_line_count": int((~mapping_df["ReviewRequired"]).sum()),
            "auto_accepted_line_accuracy": (
                auto_accepted_correct / int(auto_accepted_mask.sum())
                if int(auto_accepted_mask.sum())
                else 0.0
            ),
            "auto_accepted_source_net_income": auto_accepted_source_net_income,
            "auto_accepted_rebuilt_net_income": auto_accepted_rebuilt_net_income,
            "auto_accepted_net_income_difference": (
                auto_accepted_rebuilt_net_income
                - auto_accepted_source_net_income
            ),
            "incorrect_lines_captured_by_hitl": reviewed_incorrect,
            "hitl_error_capture_rate": (
                reviewed_incorrect / incorrect_line_count
                if incorrect_line_count
                else 0.0
            ),
            "review_threshold": args.review_threshold,
        },
        "reconciliation": {
            "active_comparison_account_count": int(len(active_rebuild)),
            "accounts_within_tolerance": int(
                (active_rebuild["AbsDifference"] <= args.tolerance).sum()
            ),
            "total_absolute_account_difference": float(
                active_rebuild["AbsDifference"].sum()
            ),
            "maximum_absolute_account_difference": float(
                active_rebuild["AbsDifference"].max()
            ),
            "official_net_income": official_net_income,
            "ai_rebuilt_net_income_excluding_unmapped": rebuilt_net_income,
            "net_income_difference": net_income_difference,
            "tolerance": args.tolerance,
        },
        "error_analysis": error_evidence,
        "human_audit": {
            "account_comparison_row_count": len(account_audit),
            "all_line_audit_count": len(all_line_audit),
            "misclassified_line_audit_count": len(misclassified_line_audit),
            "review_columns": [
                "HumanDecision",
                "HumanCorrectAccount",
                "HumanNotes",
            ],
        },
    }
    _write_json(output_dir / "quickbooks_pl_blind_summary.json", summary)

    print()
    print("=== QuickBooks blind P&L rebuild ===")
    print(
        f"Line classification: {exact_line_matches}/{len(mapped_rows)} "
        f"({summary['classification']['line_accuracy']:.1%})"
    )
    print(
        "Amount-weighted line accuracy: "
        f"{summary['classification']['absolute_amount_weighted_accuracy']:.1%}"
    )
    print(
        "HITL review: "
        f"{summary['classification']['hitl_review_line_count']} lines; "
        "auto-accepted accuracy: "
        f"{summary['classification']['auto_accepted_line_accuracy']:.1%}"
    )
    print(
        "Accounts within tolerance: "
        f"{summary['reconciliation']['accounts_within_tolerance']}/"
        f"{summary['reconciliation']['active_comparison_account_count']}"
    )
    print(
        "Total absolute account difference: "
        f"{summary['reconciliation']['total_absolute_account_difference']:,.2f}"
    )
    print(
        f"Official net income: {official_net_income:,.2f}; "
        f"AI rebuilt: {rebuilt_net_income:,.2f}; "
        f"difference: {net_income_difference:,.2f}"
    )
    print(f"Outputs written to {output_dir}.")


if __name__ == "__main__":
    main()
