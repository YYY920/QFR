from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from quickbooks.balance_sheet import (
    BalanceSheetAccount,
    add_running_balances,
    extract_balance_sheet_accounts,
    extract_general_ledger_movements,
    load_account_metadata,
    rebuild_balance_sheet,
)


DEFAULT_OPENING_BALANCE_SHEET = Path(
    "output/quickbooks/reports/opening_balance_sheet.json"
)
DEFAULT_ENDING_BALANCE_SHEET = Path("output/quickbooks/reports/balance_sheet.json")
DEFAULT_GENERAL_LEDGER = Path("output/quickbooks/reports/general_ledger.json")
DEFAULT_ACCOUNTS = Path("output/quickbooks/entities/account.json")
DEFAULT_OUTPUT_DIR = Path("output/quickbooks/balance_sheet_rebuild")


def _load_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Missing QuickBooks input: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"QuickBooks report must contain one JSON object: {path}")
    return payload


def _load_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Missing QuickBooks input: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise SystemExit(f"QuickBooks entity file must contain one JSON array: {path}")
    return [row for row in payload if isinstance(row, dict)]


def _write_dataframe(df: pd.DataFrame, base_path: Path) -> None:
    df.to_csv(base_path.with_suffix(".csv"), index=False)
    df.to_excel(base_path.with_suffix(".xlsx"), index=False)


def _account_rows(accounts: list[BalanceSheetAccount]) -> list[dict[str, Any]]:
    return [
        {
            "ComparisonKey": account.comparison_key,
            "AccountID": account.account_id,
            "BalanceSheetSection": account.section,
            "BalanceSheetCategory": account.category,
            "AccountName": account.account_name,
            "Amount": account.amount,
        }
        for account in accounts
    ]


def _report_date(payload: dict[str, Any], field: str) -> str:
    header = payload.get("Header", {})
    return str(header.get(field) or "") if isinstance(header, dict) else ""


def _validate_report_periods(
    opening_payload: dict[str, Any],
    ending_payload: dict[str, Any],
    ledger_payload: dict[str, Any],
) -> None:
    opening_end = _report_date(opening_payload, "EndPeriod")
    ledger_start = _report_date(ledger_payload, "StartPeriod")
    ledger_end = _report_date(ledger_payload, "EndPeriod")
    ending_end = _report_date(ending_payload, "EndPeriod")
    if not all((opening_end, ledger_start, ledger_end, ending_end)):
        raise SystemExit("QuickBooks reports are missing required period headers.")
    try:
        expected_ledger_start = date.fromisoformat(opening_end) + timedelta(days=1)
    except ValueError as exc:
        raise SystemExit("QuickBooks report dates must use YYYY-MM-DD.") from exc
    if ledger_start != expected_ledger_start.isoformat():
        raise SystemExit(
            "GeneralLedger must start one day after the opening Balance Sheet date."
        )
    if ledger_end != ending_end:
        raise SystemExit(
            "GeneralLedger end date must match the official ending Balance Sheet date."
        )
    opening_basis = _report_date(opening_payload, "ReportBasis")
    ending_basis = _report_date(ending_payload, "ReportBasis")
    ledger_basis = _report_date(ledger_payload, "ReportBasis")
    populated_bases = {value for value in (opening_basis, ending_basis, ledger_basis) if value}
    if len(populated_bases) > 1:
        raise SystemExit("QuickBooks reports use different accounting methods.")
    currencies = {
        _report_date(payload, "Currency")
        for payload in (opening_payload, ending_payload, ledger_payload)
        if _report_date(payload, "Currency")
    }
    if len(currencies) > 1:
        raise SystemExit("QuickBooks reports use different currencies.")


def _equation(rows: pd.DataFrame, amount_column: str) -> dict[str, float]:
    if rows.empty:
        return {"assets": 0.0, "liabilities": 0.0, "equity": 0.0, "difference": 0.0}
    totals = rows.groupby("BalanceSheetSection")[amount_column].sum()
    assets = float(totals.get("Assets", 0.0))
    liabilities = float(totals.get("Liabilities", 0.0))
    equity = float(totals.get("Equity", 0.0))
    return {
        "assets": assets,
        "liabilities": liabilities,
        "equity": equity,
        "difference": assets - liabilities - equity,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild a QuickBooks Balance Sheet from an official opening balance "
            "plus signed General Ledger records, then compare with the official endpoint."
        )
    )
    parser.add_argument("--opening-balance-sheet", type=Path, default=DEFAULT_OPENING_BALANCE_SHEET)
    parser.add_argument("--ending-balance-sheet", type=Path, default=DEFAULT_ENDING_BALANCE_SHEET)
    parser.add_argument("--general-ledger", type=Path, default=DEFAULT_GENERAL_LEDGER)
    parser.add_argument("--accounts", type=Path, default=DEFAULT_ACCOUNTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--tolerance", type=float, default=0.01)
    args = parser.parse_args()
    if args.tolerance < 0:
        parser.error("--tolerance must be non-negative.")
    return args


def main() -> None:
    args = parse_args()
    opening_payload = _load_object(args.opening_balance_sheet)
    ending_payload = _load_object(args.ending_balance_sheet)
    ledger_payload = _load_object(args.general_ledger)
    account_rows = _load_array(args.accounts)
    _validate_report_periods(opening_payload, ending_payload, ledger_payload)
    account_metadata = load_account_metadata(account_rows)

    opening_accounts = extract_balance_sheet_accounts(opening_payload, account_metadata)
    ending_accounts = extract_balance_sheet_accounts(ending_payload, account_metadata)
    movement_rows = extract_general_ledger_movements(ledger_payload, account_metadata)
    running_rows = add_running_balances(movement_rows, opening_accounts)
    rebuild_rows = rebuild_balance_sheet(
        opening_accounts,
        ending_accounts,
        running_rows,
        tolerance=args.tolerance,
    )

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    opening_df = pd.DataFrame(_account_rows(opening_accounts))
    ending_df = pd.DataFrame(_account_rows(ending_accounts))
    movement_df = pd.DataFrame(running_rows)
    rebuild_df = pd.DataFrame(rebuild_rows)

    _write_dataframe(opening_df, output_dir / "quickbooks_bs_opening_balances")
    _write_dataframe(ending_df, output_dir / "quickbooks_bs_official_ending_balances")
    _write_dataframe(movement_df, output_dir / "quickbooks_bs_movement_lines")
    _write_dataframe(rebuild_df, output_dir / "quickbooks_bs_rebuild_diff")

    mismatches = rebuild_df[rebuild_df["AbsDifference"] > args.tolerance]
    summary = {
        "report": {
            "opening_date": _report_date(opening_payload, "EndPeriod"),
            "movement_from": _report_date(ledger_payload, "StartPeriod"),
            "movement_to": _report_date(ledger_payload, "EndPeriod"),
            "ending_date": _report_date(ending_payload, "EndPeriod"),
            "accounting_method": _report_date(ledger_payload, "ReportBasis"),
            "currency": _report_date(ledger_payload, "Currency"),
        },
        "method": {
            "opening_source": "QuickBooks BalanceSheet at the selected opening date",
            "movement_source": "QuickBooks GeneralLedger detail records",
            "ending_source": "QuickBooks BalanceSheet at the selected ending date",
            "asset_movement": "debit minus credit",
            "liability_and_equity_movement": "credit minus debit",
            "net_income_movement": (
                "revenue and expense GeneralLedger lines rolled into the "
                "Balance Sheet Net Income row"
            ),
        },
        "counts": {
            "opening_account_count": len(opening_accounts),
            "ending_account_count": len(ending_accounts),
            "movement_record_count": len(running_rows),
            "comparison_account_count": len(rebuild_rows),
            "mismatch_account_count": int(len(mismatches)),
        },
        "reconciliation": {
            "tolerance": args.tolerance,
            "accounts_within_tolerance": int(
                (rebuild_df["AbsDifference"] <= args.tolerance).sum()
            ),
            "total_absolute_difference": float(rebuild_df["AbsDifference"].sum()),
            "maximum_absolute_difference": float(rebuild_df["AbsDifference"].max()),
        },
        "balance_sheet_equation": {
            "opening": _equation(opening_df, "Amount"),
            "rebuilt_ending": _equation(rebuild_df, "RebuiltEndingBalance"),
            "official_ending": _equation(rebuild_df, "OfficialEndingBalance"),
        },
    }
    (output_dir / "quickbooks_bs_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    print("=== QuickBooks Balance Sheet rebuild ===")
    print(
        f"Opening accounts: {len(opening_accounts)}; "
        f"movement records: {len(running_rows)}; "
        f"ending accounts: {len(ending_accounts)}."
    )
    print(
        f"Accounts within tolerance: "
        f"{summary['reconciliation']['accounts_within_tolerance']}/{len(rebuild_rows)}; "
        f"total absolute difference: "
        f"{summary['reconciliation']['total_absolute_difference']:,.2f}."
    )
    print(f"Outputs written to {output_dir}.")


if __name__ == "__main__":
    main()
