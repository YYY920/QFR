from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable


BALANCE_SHEET_CLASSES = {"ASSET", "LIABILITY", "EQUITY"}
PROFIT_AND_LOSS_CLASSES = {"REVENUE", "EXPENSE"}
NET_INCOME_KEY = "__quickbooks_net_income__"
NET_INCOME_LABELS = {"net income", "net profit", "current year earnings"}


@dataclass(frozen=True)
class BalanceSheetAccount:
    comparison_key: str
    category: str
    section: str
    hierarchy: tuple[str, ...]
    account_id: str
    account_name: str
    amount: float


def report_column_keys(payload: dict[str, Any]) -> list[str]:
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
        keys.append(
            key
            or str(column.get("ColType") or "").strip()
            or str(column.get("ColTitle") or f"column_{index}")
        )
    return keys


def nested_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("Rows", {})
    if not isinstance(rows, dict):
        return []
    result = rows.get("Row", [])
    return [row for row in result if isinstance(row, dict)] if isinstance(result, list) else []


def child_rows(row: dict[str, Any]) -> list[dict[str, Any]]:
    rows = row.get("Rows", {})
    if not isinstance(rows, dict):
        return []
    result = rows.get("Row", [])
    return [child for child in result if isinstance(child, dict)] if isinstance(result, list) else []


def cells(block: Any) -> list[dict[str, Any]]:
    if not isinstance(block, dict):
        return []
    raw_cells = block.get("ColData", [])
    return [cell for cell in raw_cells if isinstance(cell, dict)] if isinstance(raw_cells, list) else []


def cell_value(block: Any, index: int) -> str:
    row_cells = cells(block)
    if index >= len(row_cells):
        return ""
    return str(row_cells[index].get("value") or "").strip()


def first_cell_id(block: Any) -> str:
    row_cells = cells(block)
    if not row_cells:
        return ""
    return str(row_cells[0].get("id") or "").strip()


def money(value: Any) -> float:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0.0
    if text.startswith("(") and text.endswith(")"):
        text = f"-{text[1:-1]}"
    return float(text)


def normalize_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def load_account_metadata(
    rows: Iterable[dict[str, Any]],
) -> dict[str, dict[str, dict[str, str]]]:
    by_id: dict[str, dict[str, str]] = {}
    by_name: dict[str, dict[str, str]] = {}
    for row in rows:
        account_id = str(row.get("Id") or "").strip()
        name = str(row.get("Name") or "").strip()
        fully_qualified_name = str(row.get("FullyQualifiedName") or name).strip()
        classification = str(row.get("Classification") or "").strip().upper()
        if classification not in BALANCE_SHEET_CLASSES | PROFIT_AND_LOSS_CLASSES:
            continue
        metadata = {
            "account_id": account_id,
            "name": name or fully_qualified_name,
            "fully_qualified_name": fully_qualified_name or name,
            "classification": classification,
            "account_type": str(row.get("AccountType") or "").strip(),
            "account_sub_type": str(row.get("AccountSubType") or "").strip(),
        }
        if account_id:
            by_id[account_id] = metadata
        for candidate in {name, fully_qualified_name, fully_qualified_name.split(":")[-1]}:
            key = normalize_name(candidate)
            if key:
                by_name.setdefault(key, metadata)
    return {"by_id": by_id, "by_name": by_name}


def _section_for_classification(classification: str) -> str:
    return {
        "ASSET": "Assets",
        "LIABILITY": "Liabilities",
        "EQUITY": "Equity",
    }.get(classification.upper(), "Balance Sheet")


def _infer_section(path: Iterable[str]) -> str:
    joined = normalize_name(" ".join(path))
    if "asset" in joined or "bank" in joined or "receivable" in joined:
        return "Assets"
    if "liabilit" in joined or "payable" in joined or "credit card" in joined:
        return "Liabilities"
    if "equity" in joined or "retained earning" in joined:
        return "Equity"
    return "Balance Sheet"


def _clean_hierarchy(section: str, hierarchy: Iterable[str]) -> tuple[str, ...]:
    ignored = {
        "balance sheet",
        "assets",
        "total assets",
        "liabilities and equity",
        "liabilities",
        "total liabilities",
        "equity",
        "total equity",
    }
    result: list[str] = []
    for value in hierarchy:
        label = str(value or "").strip()
        if not label or normalize_name(label) in ignored:
            continue
        if label not in result:
            result.append(label)
    return tuple(result) or (section,)


def _metadata_for(
    account_id: str,
    account_name: str,
    account_metadata: dict[str, dict[str, dict[str, str]]],
) -> dict[str, str] | None:
    if account_id and account_id in account_metadata.get("by_id", {}):
        return account_metadata["by_id"][account_id]
    return account_metadata.get("by_name", {}).get(normalize_name(account_name))


def extract_balance_sheet_accounts(
    payload: dict[str, Any],
    account_metadata: dict[str, dict[str, dict[str, str]]],
) -> list[BalanceSheetAccount]:
    accounts: dict[str, BalanceSheetAccount] = {}

    def add_account(block: dict[str, Any], hierarchy: tuple[str, ...]) -> None:
        account_id = first_cell_id(block)
        displayed_name = cell_value(block, 0)
        if not account_id and not displayed_name:
            return
        metadata = _metadata_for(account_id, displayed_name, account_metadata)
        normalized_displayed_name = normalize_name(displayed_name)
        is_net_income = normalized_displayed_name in NET_INCOME_LABELS
        if metadata is None and not is_net_income:
            return
        if metadata is not None and metadata["classification"] not in BALANCE_SHEET_CLASSES:
            return
        section = (
            "Equity"
            if is_net_income
            else _section_for_classification(metadata["classification"])
        )
        account_name = (
            "Net Income"
            if is_net_income
            else metadata.get("fully_qualified_name")
            or metadata.get("name")
            or displayed_name
        )
        clean_hierarchy = _clean_hierarchy(section, (*hierarchy, displayed_name))
        category = " > ".join((section, *clean_hierarchy))
        comparison_key = (
            NET_INCOME_KEY
            if is_net_income
            else metadata.get("account_id") or normalize_name(category)
        )
        accounts[comparison_key] = BalanceSheetAccount(
            comparison_key=comparison_key,
            category=category,
            section=section,
            hierarchy=clean_hierarchy,
            account_id=(metadata.get("account_id") or account_id) if metadata else "",
            account_name=account_name,
            amount=money(cell_value(block, 1)),
        )

    def walk(rows: list[dict[str, Any]], hierarchy: tuple[str, ...] = ()) -> None:
        for row in rows:
            header = row.get("Header")
            header_label = cell_value(header, 0)
            header_has_account = bool(
                _metadata_for(first_cell_id(header), header_label, account_metadata)
            ) or normalize_name(header_label) in NET_INCOME_LABELS
            next_hierarchy = hierarchy
            if header_label:
                next_hierarchy = (*hierarchy, header_label)
                if header_has_account:
                    add_account(header, hierarchy)

            if "ColData" in row:
                add_account(row, hierarchy)

            summary = row.get("Summary")
            if normalize_name(cell_value(summary, 0)) in NET_INCOME_LABELS:
                add_account(summary, hierarchy)

            walk(child_rows(row), next_hierarchy)

    walk(nested_rows(payload))
    if not accounts:
        raise ValueError("No Balance Sheet account rows were found in the QuickBooks report.")
    return list(accounts.values())


def _record_value(record: dict[str, str], candidates: Iterable[str]) -> str:
    normalized = {normalize_name(key): value for key, value in record.items()}
    for candidate in candidates:
        value = normalized.get(normalize_name(candidate))
        if value not in {None, ""}:
            return str(value)
    return ""


def extract_general_ledger_movements(
    payload: dict[str, Any],
    account_metadata: dict[str, dict[str, dict[str, str]]],
) -> list[dict[str, Any]]:
    column_keys = report_column_keys(payload)
    if not column_keys:
        raise ValueError("GeneralLedger report has no column metadata.")

    movements: list[dict[str, Any]] = []

    def walk(
        rows: list[dict[str, Any]],
        inherited_account: dict[str, str] | None = None,
    ) -> None:
        for row in rows:
            header = row.get("Header")
            header_name = cell_value(header, 0)
            current_account = (
                _metadata_for(first_cell_id(header), header_name, account_metadata)
                or inherited_account
            )

            if row.get("type") == "Data" and "ColData" in row:
                values = [cell_value(row, index) for index in range(len(column_keys))]
                record = dict(zip(column_keys, values))
                explicit_name = _record_value(record, ("account_name", "account", "acct_name"))
                explicit_id = ""
                for index, key in enumerate(column_keys):
                    if normalize_name(key) in {"account name", "account", "acct name"}:
                        row_cells = cells(row)
                        if index < len(row_cells):
                            explicit_id = str(row_cells[index].get("id") or "").strip()
                        break
                line_account = (
                    _metadata_for(explicit_id, explicit_name, account_metadata)
                    or current_account
                )
                if line_account is not None:
                    source_classification = line_account["classification"]
                    debit_text = _record_value(
                        record,
                        (
                            "debt_amt",
                            "debt_home_amt",
                            "debit_amt",
                            "debit",
                            "debit_amount",
                        ),
                    )
                    credit_text = _record_value(
                        record,
                        ("credit_amt", "credit_home_amt", "credit", "credit_amount"),
                    )
                    amount_text = _record_value(
                        record,
                        (
                            "subt_nat_amount",
                            "subt_nat_home_amount",
                            "amount",
                            "net_amount",
                            "home_net_amount",
                            "txn_amount",
                        ),
                    )
                    debit = money(debit_text)
                    credit = money(credit_text)
                    if debit_text or credit_text:
                        debit_minus_credit = debit - credit
                        signed_movement = (
                            debit_minus_credit
                            if source_classification == "ASSET"
                            else -debit_minus_credit
                        )
                    else:
                        # subt_nat_amount is already expressed in the account's
                        # natural balance direction by the QBO report. Expense
                        # natural balances reduce Net Income, so only that class
                        # needs inversion when it is rolled into Equity.
                        signed_movement = money(amount_text)
                        if source_classification == "EXPENSE":
                            signed_movement = -signed_movement
                    transaction_type = _record_value(
                        record, ("txn_type", "transaction_type", "type")
                    )
                    transaction_date = _record_value(record, ("tx_date", "date"))
                    document_number = _record_value(
                        record, ("doc_num", "document_number", "num")
                    )
                    contact = _record_value(record, ("name", "contact", "entity"))
                    memo = _record_value(record, ("memo", "description"))
                    opening_labels = {
                        "beginning balance",
                        "opening balance",
                        "balance forward",
                        "brought forward",
                    }
                    is_opening_display_row = (
                        not any((transaction_type, document_number, contact, memo))
                        or normalize_name(transaction_type) in opening_labels
                        or (
                            not transaction_date
                            and normalize_name(memo) in opening_labels
                        )
                    )
                    if abs(signed_movement) > 0 and not is_opening_display_row:
                        source_account_name = (
                            line_account.get("fully_qualified_name")
                            or line_account.get("name")
                            or explicit_name
                        )
                        is_profit_and_loss = (
                            source_classification in PROFIT_AND_LOSS_CLASSES
                        )
                        section = (
                            "Equity"
                            if is_profit_and_loss
                            else _section_for_classification(source_classification)
                        )
                        account_name = "Net Income" if is_profit_and_loss else source_account_name
                        category = " > ".join(
                            (section, *[part for part in account_name.split(":") if part])
                        )
                        movements.append(
                            {
                                "LineNumber": len(movements) + 1,
                                "Date": transaction_date,
                                "TransactionType": transaction_type,
                                "DocumentNumber": document_number,
                                "Contact": contact,
                                "Memo": memo,
                                "SplitAccount": _record_value(record, ("split_acc", "split_account")),
                                "AccountID": (
                                    ""
                                    if is_profit_and_loss
                                    else line_account.get("account_id") or explicit_id
                                ),
                                "AccountName": account_name,
                                "SourceAccountID": line_account.get("account_id") or explicit_id,
                                "SourceAccountName": source_account_name,
                                "SourceAccountClassification": source_classification,
                                "BalanceSheetSection": section,
                                "BalanceSheetCategory": category,
                                "ComparisonKey": (
                                    NET_INCOME_KEY
                                    if is_profit_and_loss
                                    else line_account.get("account_id")
                                    or normalize_name(category)
                                ),
                                "Debit": debit,
                                "Credit": credit,
                                "SignedMovement": signed_movement,
                            }
                        )

            walk(child_rows(row), current_account)

    walk(nested_rows(payload))
    if not movements:
        raise ValueError("No Balance Sheet movement rows were found in GeneralLedger.")
    return movements


def add_running_balances(
    movement_rows: list[dict[str, Any]],
    opening_accounts: Iterable[BalanceSheetAccount],
) -> list[dict[str, Any]]:
    opening_by_key = {
        account.comparison_key: float(account.amount) for account in opening_accounts
    }
    running = dict(opening_by_key)
    ordered = sorted(
        movement_rows,
        key=lambda row: (
            str(row.get("Date") or ""),
            int(row.get("LineNumber") or 0),
        ),
    )
    result: list[dict[str, Any]] = []
    for row in ordered:
        key = str(row["ComparisonKey"])
        opening = opening_by_key.get(key, 0.0)
        before = running.get(key, opening)
        after = before + float(row.get("SignedMovement") or 0.0)
        running[key] = after
        result.append(
            {
                **row,
                "OpeningBalance": opening,
                "BalanceBeforeRecord": before,
                "BalanceAfterRecord": after,
            }
        )
    return result


def rebuild_balance_sheet(
    opening_accounts: Iterable[BalanceSheetAccount],
    ending_accounts: Iterable[BalanceSheetAccount],
    movement_rows: Iterable[dict[str, Any]],
    tolerance: float = 0.01,
) -> list[dict[str, Any]]:
    opening = {account.comparison_key: account for account in opening_accounts}
    ending = {account.comparison_key: account for account in ending_accounts}
    movement_totals: dict[str, float] = {}
    movement_counts: dict[str, int] = {}
    movement_metadata: dict[str, dict[str, Any]] = {}
    for row in movement_rows:
        key = str(row["ComparisonKey"])
        movement_totals[key] = movement_totals.get(key, 0.0) + float(
            row.get("SignedMovement") or 0.0
        )
        movement_counts[key] = movement_counts.get(key, 0) + 1
        movement_metadata[key] = row

    rebuilt: list[dict[str, Any]] = []
    for key in sorted(set(opening) | set(ending) | set(movement_totals)):
        opening_account = opening.get(key)
        ending_account = ending.get(key)
        movement_meta = movement_metadata.get(key, {})
        reference = ending_account or opening_account
        opening_amount = float(opening_account.amount) if opening_account else 0.0
        movement_amount = movement_totals.get(key, 0.0)
        official_ending = float(ending_account.amount) if ending_account else 0.0
        rebuilt_ending = opening_amount + movement_amount
        difference = rebuilt_ending - official_ending
        rebuilt.append(
            {
                "ComparisonKey": key,
                "AccountID": reference.account_id if reference else movement_meta.get("AccountID", ""),
                "BalanceSheetSection": reference.section if reference else movement_meta.get("BalanceSheetSection", ""),
                "BalanceSheetCategory": reference.category if reference else movement_meta.get("BalanceSheetCategory", ""),
                "AccountName": reference.account_name if reference else movement_meta.get("AccountName", ""),
                "OpeningBalance": opening_amount,
                "MovementAmount": movement_amount,
                "MovementRecordCount": movement_counts.get(key, 0),
                "RebuiltEndingBalance": rebuilt_ending,
                "OfficialEndingBalance": official_ending,
                "Difference": difference,
                "AbsDifference": abs(difference),
                "Status": "Match" if abs(difference) <= tolerance else "Mismatch",
            }
        )
    return rebuilt
