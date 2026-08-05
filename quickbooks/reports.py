from __future__ import annotations

from typing import Any, Iterable

from .client import QuickBooksClient

DEFAULT_REPORTS = (
    "ProfitAndLoss",
    "ProfitAndLossDetail",
    "BalanceSheet",
    "CashFlow",
    "TrialBalance",
    "GeneralLedger",
    "AccountList",
    "AgedReceivables",
    "AgedPayables",
    "CustomerBalance",
    "VendorBalance",
)

PERIOD_REPORTS = {
    "ProfitAndLoss",
    "ProfitAndLossDetail",
    "BalanceSheet",
    "CashFlow",
    "TrialBalance",
    "GeneralLedger",
    "CustomerIncome",
    "SalesByClass",
    "SalesByCustomer",
    "SalesByDepartment",
    "SalesByProduct",
    "TransactionList",
    "VendorExpenses",
}

AS_OF_REPORTS = {
    "AgedPayables",
    "AgedPayablesDetail",
    "AgedReceivables",
    "AgedReceivablesDetail",
    "CustomerBalance",
    "CustomerBalanceDetail",
    "VendorBalance",
    "VendorBalanceDetail",
}

ACCOUNTING_METHOD_REPORTS = PERIOD_REPORTS | AS_OF_REPORTS


def build_report_params(
    report_name: str,
    *,
    from_date: str,
    to_date: str,
    accounting_method: str = "Accrual",
) -> dict[str, str]:
    params: dict[str, str] = {}
    if report_name in PERIOD_REPORTS:
        params.update({"start_date": from_date, "end_date": to_date})
    elif report_name in AS_OF_REPORTS:
        params["report_date"] = to_date
    if report_name in ACCOUNTING_METHOD_REPORTS:
        params["accounting_method"] = accounting_method
    return params


def fetch_reports(
    client: QuickBooksClient,
    report_names: Iterable[str] = DEFAULT_REPORTS,
    *,
    from_date: str,
    to_date: str,
    accounting_method: str = "Accrual",
) -> dict[str, dict[str, Any]]:
    return {
        report_name: client.get_report(
            report_name,
            build_report_params(
                report_name,
                from_date=from_date,
                to_date=to_date,
                accounting_method=accounting_method,
            ),
        )
        for report_name in report_names
    }
