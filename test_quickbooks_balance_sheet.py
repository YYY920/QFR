from __future__ import annotations

import unittest

from quickbooks.balance_sheet import (
    NET_INCOME_KEY,
    add_running_balances,
    extract_balance_sheet_accounts,
    extract_general_ledger_movements,
    load_account_metadata,
    rebuild_balance_sheet,
)


def _accounts() -> list[dict[str, object]]:
    return [
        {
            "Id": "1",
            "Name": "Checking",
            "FullyQualifiedName": "Checking",
            "Classification": "Asset",
            "AccountType": "Bank",
        },
        {
            "Id": "2",
            "Name": "Accounts Payable",
            "FullyQualifiedName": "Accounts Payable",
            "Classification": "Liability",
            "AccountType": "Accounts Payable",
        },
        {
            "Id": "3",
            "Name": "Retained Earnings",
            "FullyQualifiedName": "Retained Earnings",
            "Classification": "Equity",
            "AccountType": "Equity",
        },
        {
            "Id": "4",
            "Name": "Sales",
            "FullyQualifiedName": "Sales",
            "Classification": "Revenue",
            "AccountType": "Income",
        },
        {
            "Id": "5",
            "Name": "Office Supplies",
            "FullyQualifiedName": "Office Supplies",
            "Classification": "Expense",
            "AccountType": "Expense",
        },
    ]


def _balance_sheet(checking: float, payable: float, equity: float) -> dict[str, object]:
    return {
        "Rows": {
            "Row": [
                {
                    "Header": {"ColData": [{"value": "Assets"}, {"value": ""}]},
                    "Rows": {
                        "Row": [
                            {
                                "ColData": [
                                    {"value": "Checking", "id": "1"},
                                    {"value": str(checking)},
                                ],
                                "type": "Data",
                            }
                        ]
                    },
                    "type": "Section",
                },
                {
                    "Header": {
                        "ColData": [
                            {"value": "Liabilities and Equity"},
                            {"value": ""},
                        ]
                    },
                    "Rows": {
                        "Row": [
                            {
                                "Header": {
                                    "ColData": [
                                        {"value": "Liabilities"},
                                        {"value": ""},
                                    ]
                                },
                                "Rows": {
                                    "Row": [
                                        {
                                            "ColData": [
                                                {
                                                    "value": "Accounts Payable",
                                                    "id": "2",
                                                },
                                                {"value": str(payable)},
                                            ],
                                            "type": "Data",
                                        }
                                    ]
                                },
                                "type": "Section",
                            },
                            {
                                "Header": {
                                    "ColData": [
                                        {"value": "Equity"},
                                        {"value": ""},
                                    ]
                                },
                                "Rows": {
                                    "Row": [
                                        {
                                            "ColData": [
                                                {
                                                    "value": "Retained Earnings",
                                                    "id": "3",
                                                },
                                                {"value": str(equity)},
                                            ],
                                            "type": "Data",
                                        }
                                    ]
                                },
                                "type": "Section",
                            },
                        ]
                    },
                    "type": "Section",
                },
            ]
        }
    }


def _general_ledger() -> dict[str, object]:
    keys = [
        "tx_date",
        "txn_type",
        "doc_num",
        "name",
        "memo",
        "split_acc",
        "debt_amt",
        "credit_amt",
    ]

    def line(date: str, debit: str, credit: str) -> dict[str, object]:
        return {
            "type": "Data",
            "ColData": [
                {"value": date},
                {"value": "Journal Entry"},
                {"value": "1"},
                {"value": "Counterparty"},
                {"value": "Movement"},
                {"value": "Split"},
                {"value": debit},
                {"value": credit},
            ],
        }

    return {
        "Columns": {
            "Column": [
                {
                    "ColTitle": key,
                    "MetaData": [{"Name": "ColKey", "Value": key}],
                }
                for key in keys
            ]
        },
        "Rows": {
            "Row": [
                {
                    "Header": {
                        "ColData": [{"value": "Checking", "id": "1"}]
                    },
                    "Rows": {
                        "Row": [
                            {
                                "type": "Data",
                                "ColData": [
                                    {"value": ""},
                                    {"value": "Beginning Balance"},
                                    {"value": ""},
                                    {"value": ""},
                                    {"value": ""},
                                    {"value": ""},
                                    {"value": "1000"},
                                    {"value": ""},
                                ],
                            },
                            line("2026-01-02", "100", ""),
                            line("2026-01-03", "", "20"),
                        ]
                    },
                    "type": "Section",
                },
                {
                    "Header": {
                        "ColData": [{"value": "Accounts Payable", "id": "2"}]
                    },
                    "Rows": {
                        "Row": [
                            line("2026-01-02", "", "50"),
                            line("2026-01-03", "10", ""),
                        ]
                    },
                    "type": "Section",
                },
                {
                    "Header": {
                        "ColData": [{"value": "Retained Earnings", "id": "3"}]
                    },
                    "Rows": {"Row": [line("2026-01-03", "", "20")]},
                    "type": "Section",
                },
            ]
        },
    }


def _add_net_income(
    payload: dict[str, object],
    amount: float,
) -> dict[str, object]:
    equity_rows = payload["Rows"]["Row"][1]["Rows"]["Row"][1]["Rows"]["Row"]
    equity_rows.append(
        {
            "ColData": [
                {"value": "Net Income"},
                {"value": str(amount)},
            ],
            "type": "Data",
        }
    )
    return payload


def _profit_and_loss_ledger() -> dict[str, object]:
    columns = ["tx_date", "txn_type", "subt_nat_amount"]

    def section(account_id: str, name: str, date: str, amount: str) -> dict[str, object]:
        return {
            "Header": {"ColData": [{"value": name, "id": account_id}]},
            "Rows": {
                "Row": [
                    {
                        "type": "Data",
                        "ColData": [
                            {"value": date},
                            {"value": "Journal Entry"},
                            {"value": amount},
                        ],
                    }
                ]
            },
            "type": "Section",
        }

    return {
        "Columns": {
            "Column": [
                {
                    "ColTitle": key,
                    "MetaData": [{"Name": "ColKey", "Value": key}],
                }
                for key in columns
            ]
        },
        "Rows": {
            "Row": [
                section("4", "Sales", "2026-01-02", "100"),
                section("5", "Office Supplies", "2026-01-03", "30"),
            ]
        },
    }


class QuickBooksBalanceSheetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.metadata = load_account_metadata(_accounts())

    def test_extracts_only_balance_sheet_accounts(self) -> None:
        accounts = extract_balance_sheet_accounts(
            _balance_sheet(1000, 300, 700),
            self.metadata,
        )

        self.assertEqual({account.account_id for account in accounts}, {"1", "2", "3"})
        self.assertEqual(
            {account.section for account in accounts},
            {"Assets", "Liabilities", "Equity"},
        )

    def test_general_ledger_records_use_natural_balance_signs(self) -> None:
        movements = extract_general_ledger_movements(
            _general_ledger(),
            self.metadata,
        )
        totals: dict[str, float] = {}
        for row in movements:
            totals[str(row["AccountID"])] = totals.get(str(row["AccountID"]), 0.0) + float(
                row["SignedMovement"]
            )

        self.assertEqual(totals, {"1": 80.0, "2": 40.0, "3": 20.0})

    def test_natural_amount_is_not_reversed_for_liabilities(self) -> None:
        ledger = _general_ledger()
        ledger["Columns"] = {
            "Column": [
                {"ColType": "txn_type", "ColTitle": "Transaction Type"},
                {"ColType": "subt_nat_amount", "ColTitle": "Amount"},
            ]
        }
        ledger["Rows"] = {
            "Row": [
                {
                    "Header": {
                        "ColData": [{"value": "Accounts Payable", "id": "2"}]
                    },
                    "Rows": {
                        "Row": [
                            {
                                "type": "Data",
                                "ColData": [
                                    {"value": "Bill"},
                                    {"value": "75.00"},
                                ],
                            }
                        ]
                    },
                    "type": "Section",
                }
            ]
        }

        movements = extract_general_ledger_movements(ledger, self.metadata)

        self.assertEqual(movements[0]["SignedMovement"], 75.0)

    def test_opening_plus_each_record_reaches_official_endpoint(self) -> None:
        opening = extract_balance_sheet_accounts(
            _balance_sheet(1000, 300, 700),
            self.metadata,
        )
        ending = extract_balance_sheet_accounts(
            _balance_sheet(1080, 340, 720),
            self.metadata,
        )
        movements = extract_general_ledger_movements(
            _general_ledger(),
            self.metadata,
        )
        running = add_running_balances(movements, opening)
        rebuilt = rebuild_balance_sheet(opening, ending, running)

        checking_records = [row for row in running if row["AccountID"] == "1"]
        self.assertEqual(checking_records[0]["BalanceBeforeRecord"], 1000.0)
        self.assertEqual(checking_records[0]["BalanceAfterRecord"], 1100.0)
        self.assertEqual(checking_records[1]["BalanceAfterRecord"], 1080.0)
        self.assertTrue(all(row["Status"] == "Match" for row in rebuilt))

    def test_profit_and_loss_records_roll_into_balance_sheet_net_income(self) -> None:
        opening = extract_balance_sheet_accounts(
            _add_net_income(_balance_sheet(1000, 300, 700), 200),
            self.metadata,
        )
        ending = extract_balance_sheet_accounts(
            _add_net_income(_balance_sheet(1000, 300, 700), 270),
            self.metadata,
        )
        movements = extract_general_ledger_movements(
            _profit_and_loss_ledger(),
            self.metadata,
        )
        running = add_running_balances(movements, opening)
        rebuilt = rebuild_balance_sheet(opening, ending, running)

        net_income_lines = [
            row for row in running if row["ComparisonKey"] == NET_INCOME_KEY
        ]
        net_income_result = next(
            row for row in rebuilt if row["ComparisonKey"] == NET_INCOME_KEY
        )
        self.assertEqual([row["SignedMovement"] for row in net_income_lines], [100.0, -30.0])
        self.assertEqual(net_income_lines[0]["OpeningBalance"], 200.0)
        self.assertEqual(net_income_lines[-1]["BalanceAfterRecord"], 270.0)
        self.assertEqual(net_income_result["Status"], "Match")


if __name__ == "__main__":
    unittest.main()
