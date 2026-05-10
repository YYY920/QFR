from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import pandas as pd


DETAIL_PATH = Path("output/pl_mapping_report.xlsx")
SUMMARY_PATH = Path("output/pl_mapping_summary.xlsx")
TOLERANCE = 0.01


def _read_detail() -> pd.DataFrame:
    if not DETAIL_PATH.exists():
        raise SystemExit(f"Missing detail report: {DETAIL_PATH}")
    df = pd.read_excel(DETAIL_PATH)
    required = {"MappedCategory", "Amount"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Detail report missing columns: {sorted(missing)}")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    df["MappedCategory"] = df["MappedCategory"].fillna("Unmapped")
    return df


def _read_summary() -> pd.DataFrame:
    if not SUMMARY_PATH.exists():
        raise SystemExit(f"Missing summary report: {SUMMARY_PATH}")
    df = pd.read_excel(SUMMARY_PATH)
    required = {"MappedCategory", "Amount"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Summary report missing columns: {sorted(missing)}")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    df["MappedCategory"] = df["MappedCategory"].fillna("Unmapped")
    return df


def _compare_totals(detail_df: pd.DataFrame, summary_df: pd.DataFrame) -> Tuple[float, float, float]:
    detail_total = float(detail_df["Amount"].sum())
    summary_total = float(summary_df["Amount"].sum())
    diff = detail_total - summary_total
    return detail_total, summary_total, diff


def _compare_by_category(
    detail_df: pd.DataFrame, summary_df: pd.DataFrame
) -> Dict[str, float]:
    detail_by_cat = detail_df.groupby("MappedCategory")["Amount"].sum()
    summary_by_cat = summary_df.set_index("MappedCategory")["Amount"]
    cats = sorted(set(detail_by_cat.index) | set(summary_by_cat.index))
    diffs: Dict[str, float] = {}
    for cat in cats:
        detail_val = float(detail_by_cat.get(cat, 0.0))
        summary_val = float(summary_by_cat.get(cat, 0.0))
        diff = detail_val - summary_val
        if abs(diff) > TOLERANCE:
            diffs[cat] = diff
    return diffs


def main() -> None:
    detail_df = _read_detail()
    summary_df = _read_summary()

    detail_total, summary_total, diff = _compare_totals(detail_df, summary_df)
    per_cat_diffs = _compare_by_category(detail_df, summary_df)

    print("=== Mapping Consistency Test ===")
    print(f"Detail total:  {detail_total:,.2f}")
    print(f"Summary total: {summary_total:,.2f}")
    print(f"Total diff:    {diff:,.2f}")

    if per_cat_diffs:
        print("\nCategory mismatches (detail - summary):")
        for cat, d in per_cat_diffs.items():
            print(f"- {cat}: {d:,.2f}")
        raise SystemExit(1)

    print("\n✅ Detail and summary totals match within tolerance.")


if __name__ == "__main__":
    main()
