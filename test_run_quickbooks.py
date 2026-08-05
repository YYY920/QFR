from __future__ import annotations

import unittest
from unittest.mock import patch

from run_quickbooks import (
    QUICKBOOKS_MAPPING_POLICY_VERSION,
    _categories_for_role,
    _infer_line_role,
    _map_lines,
    _match_transaction_line,
    _rule_based_category,
    _source_parse_comparison,
    extract_account_priors,
    extract_company_prior,
    extract_detail_lines,
    extract_item_priors,
    extract_official_accounts,
    extract_transaction_line_evidence,
)


DETAIL_COLUMNS = [
    "tx_date",
    "txn_type",
    "doc_num",
    "name",
    "memo",
    "split_acc",
    "subt_nat_amount",
    "rbal_nat_amount",
]


def _columns() -> dict[str, list[dict[str, object]]]:
    return {
        "Column": [
            {
                "ColTitle": key,
                "MetaData": [{"Name": "ColKey", "Value": key}],
            }
            for key in DETAIL_COLUMNS
        ]
    }


class QuickBooksBlindRebuildTests(unittest.TestCase):
    def test_prior_extractors_add_account_metadata_without_contact_details(self) -> None:
        account_list = {
            "Columns": {
                "Column": [
                    {
                        "ColTitle": key,
                        "MetaData": [{"Name": "ColKey", "Value": key}],
                    }
                    for key in (
                        "account_name",
                        "account_type",
                        "detail_acc_type",
                        "account_desc",
                    )
                ]
            },
            "Rows": {
                "Row": [
                    {
                        "ColData": [
                            {"value": "Automobile:Fuel"},
                            {"value": "Expenses"},
                            {"value": "Auto"},
                            {"value": "Vehicle fuel"},
                        ],
                        "type": "Data",
                    }
                ]
            },
        }
        company_info = {
            "CompanyInfo": {
                "CompanyName": "Sandbox",
                "Country": "US",
                "Email": {"Address": "private@example.com"},
                "CompanyAddr": {"Line1": "Private address"},
                "NameValue": [
                    {
                        "Name": "QBOIndustryType",
                        "Value": "Landscaping Services",
                    }
                ],
            }
        }

        accounts = extract_account_priors(account_list)
        company = extract_company_prior(company_info)

        self.assertEqual(accounts["Automobile:Fuel"]["detail_type"], "Auto")
        self.assertEqual(
            company["features"]["QBOIndustryType"],
            "Landscaping Services",
        )
        self.assertNotIn("Email", company)
        self.assertNotIn("CompanyAddr", company)

    def test_item_priors_remove_account_answers_and_keep_business_context(self) -> None:
        items = [
            {
                "Id": "5",
                "Name": "Rock Fountain",
                "Description": "Rock Fountain",
                "Type": "Inventory",
                "UnitPrice": 275,
                "PurchaseCost": 125,
                "IncomeAccountRef": {
                    "value": "79",
                    "name": "Sales of Product Income",
                },
                "ExpenseAccountRef": {
                    "value": "80",
                    "name": "Cost of Goods Sold",
                },
                "AssetAccountRef": {
                    "value": "81",
                    "name": "Inventory Asset",
                },
                "MetaData": {"CreateTime": "2026-01-01T00:00:00Z"},
            }
        ]

        priors = extract_item_priors(items)
        serialized = str(priors)

        self.assertIn("Rock Fountain", serialized)
        self.assertIn("PurchaseCost", serialized)
        self.assertNotIn("AccountRef", serialized)
        self.assertNotIn("Sales of Product Income", serialized)
        self.assertNotIn("MetaData", serialized)

    def test_transaction_matching_identifies_inventory_cogs_without_account_refs(
        self,
    ) -> None:
        entities = {
            "Invoice": [
                {
                    "Id": "130",
                    "DocNumber": "1037",
                    "TxnDate": "2026-07-09",
                    "CustomerRef": {
                        "value": "24",
                        "name": "Customer",
                    },
                    "Line": [
                        {
                            "Description": "Rock Fountain",
                            "Amount": 275,
                            "DetailType": "SalesItemLineDetail",
                            "SalesItemLineDetail": {
                                "ItemRef": {
                                    "value": "5",
                                    "name": "Rock Fountain",
                                },
                                "ItemAccountRef": {
                                    "value": "79",
                                    "name": "Sales of Product Income",
                                },
                                "UnitPrice": 275,
                                "Qty": 1,
                            },
                        }
                    ],
                }
            ]
        }
        detail_line = {
            "Date": "2026-07-09",
            "TransactionType": "Invoice",
            "DocumentNumber": "1037",
            "Contact": "Customer",
            "Description": "Rock Fountain",
            "Amount": 125,
        }
        item = {
            "Id": "5",
            "Name": "Rock Fountain",
            "Type": "Inventory",
            "UnitPrice": 275,
            "PurchaseCost": 125,
        }

        evidence = extract_transaction_line_evidence(entities)
        matched, score = _match_transaction_line(detail_line, evidence)
        role, reason = _infer_line_role(detail_line, matched, item)

        self.assertGreaterEqual(score, 20)
        self.assertEqual(matched["ItemRefId"], "5")
        self.assertNotIn("AccountRef", str(matched["SafeLine"]))
        self.assertEqual(role, "cost_of_goods_sold")
        self.assertIn("PurchaseCost", reason)

    def test_role_filter_keeps_refund_in_item_income_family(self) -> None:
        categories = [
            {
                "name": "Income > Pest Control Services",
                "type": "income",
                "description": "Pest control.",
            },
            {
                "name": "Income > Discounts given",
                "type": "income",
                "description": "General discounts.",
            },
            {
                "name": "Expenses > Maintenance and Repair",
                "type": "expense",
                "description": "Repairs.",
            },
            {
                "name": "Unmapped",
                "type": "fallback",
                "description": "Review.",
            },
        ]

        filtered = _categories_for_role(
            categories,
            "income",
            "Refund",
            {"Name": "Pest Control", "Description": "Pest Control Services"},
        )

        self.assertEqual(
            {category["name"] for category in filtered},
            {"Income > Pest Control Services", "Unmapped"},
        )

    def test_visible_leaf_rule_prefers_equipment_repairs(self) -> None:
        categories = [
            {
                "name": "Expenses > Maintenance and Repair",
                "type": "expense",
                "description": "Repairs.",
            },
            {
                "name": "Expenses > Maintenance and Repair > Equipment Repairs",
                "type": "expense",
                "description": "Equipment repairs.",
            },
            {
                "name": "Unmapped",
                "type": "fallback",
                "description": "Review.",
            },
        ]
        result = _rule_based_category(
            {
                "Contact": "Diego's Road Warrior Bodyshop",
                "Description": "Repairs on the truck",
                "AIInputDescription": "Repairs on the truck",
            },
            "expense",
            categories,
        )

        self.assertEqual(
            result,
            (
                "Expenses > Maintenance and Repair > Equipment Repairs",
                "visible-equipment-repair",
            ),
        )

    def test_current_inventory_sale_uses_product_income_but_history_does_not(
        self,
    ) -> None:
        categories = [
            {
                "name": "Income > Sales of Product Income",
                "type": "income",
                "description": "Product income.",
            },
            {
                "name": (
                    "Income > Landscaping Services > Job Materials > "
                    "Fountains and Garden Lighting"
                ),
                "type": "income",
                "description": "Fountain materials.",
            },
            {
                "name": "Unmapped",
                "type": "fallback",
                "description": "Review.",
            },
        ]
        line = {
            "Contact": "Customer",
            "Description": "Rock Fountain",
            "AIInputDescription": "Rock Fountain",
            "Amount": 275,
        }
        item = {
            "Name": "Rock Fountain",
            "Description": "Rock Fountain",
            "Type": "Inventory",
        }

        current = _rule_based_category(
            line,
            "income",
            categories,
            item,
            temporal_ambiguity=False,
        )
        historical = _rule_based_category(
            line,
            "income",
            categories,
            item,
            temporal_ambiguity=True,
        )

        self.assertEqual(
            current,
            ("Income > Sales of Product Income", "current-inventory-product-sale"),
        )
        self.assertIsNone(historical)

    def test_detail_parser_reconciles_to_official_account(self) -> None:
        summary = {
            "Rows": {
                "Row": [
                    {
                        "Header": {"ColData": [{"value": "Income"}, {"value": ""}]},
                        "Rows": {
                            "Row": [
                                {
                                    "ColData": [
                                        {"value": "Design income", "id": "82"},
                                        {"value": "100.00"},
                                    ],
                                    "type": "Data",
                                }
                            ]
                        },
                        "group": "Income",
                        "type": "Section",
                    }
                ]
            }
        }
        detail = {
            "Columns": _columns(),
            "Rows": {
                "Row": [
                    {
                        "Header": {
                            "ColData": [{"value": "Ordinary Income/Expenses"}]
                        },
                        "Rows": {
                            "Row": [
                                {
                                    "Header": {"ColData": [{"value": "Income"}]},
                                    "Rows": {
                                        "Row": [
                                            {
                                                "Header": {
                                                    "ColData": [
                                                        {"value": "Design income"}
                                                    ]
                                                },
                                                "Rows": {
                                                    "Row": [
                                                        {
                                                            "ColData": [
                                                                {"value": "2026-01-01"},
                                                                {"value": "Invoice"},
                                                                {"value": "1001"},
                                                                {"value": "Customer"},
                                                                {"value": "Custom Design"},
                                                                {
                                                                    "value": (
                                                                        "Accounts Receivable "
                                                                        "(A/R)"
                                                                    )
                                                                },
                                                                {"value": "100.00"},
                                                                {"value": "100.00"},
                                                            ],
                                                            "type": "Data",
                                                        }
                                                    ]
                                                },
                                                "type": "Section",
                                            }
                                        ]
                                    },
                                    "type": "Section",
                                }
                            ]
                        },
                        "type": "Section",
                    }
                ]
            },
        }

        accounts = extract_official_accounts(summary)
        lines = extract_detail_lines(detail)
        comparison = _source_parse_comparison(accounts, lines, tolerance=0.01)

        self.assertEqual(accounts[0].category, "Income > Design income")
        self.assertEqual(lines[0]["SourceAccountForAudit"], "Income > Design income")
        self.assertTrue((comparison["Status"] == "Match").all())

    @patch("run_quickbooks.map_description")
    def test_mapper_does_not_receive_source_or_split_account(self, mapper) -> None:
        mapper.return_value = {
            "category": "Income > Design income",
            "confidence": 0.9,
            "reason": "Design service revenue.",
        }
        line = {
            "LineNumber": 1,
            "Date": "2026-01-01",
            "TransactionType": "Invoice",
            "DocumentNumber": "1001",
            "Contact": "Customer",
            "Description": "Custom Design",
            "SplitAccountForAudit": "Accounts Receivable (A/R)",
            "Amount": 100.0,
            "SourceAccountForAudit": "Income > Design income",
            "SourceSectionForAudit": "Income",
            "AIInputDescription": "Custom Design; Document 1001",
            "AccountHiddenFromAI": True,
        }
        allowed = [
            {
                "name": "Income > Design income",
                "type": "income",
                "description": "Design revenue.",
            },
            {
                "name": "Unmapped",
                "type": "fallback",
                "description": "Review required.",
            },
        ]

        mapped = _map_lines(
            [line],
            allowed,
            company_prior={
                "company_name": "Sandbox",
                "features": {"QBOIndustryType": "Landscaping Services"},
            },
            item_priors=[
                {
                    "Id": "4",
                    "Name": "Design",
                    "Description": "Custom Design",
                    "UnitPrice": 75,
                }
            ],
            transaction_evidence=[
                {
                    "EntityType": "Invoice",
                    "ReportTransactionTypes": ("Invoice",),
                    "TransactionId": "200",
                    "Date": "2026-01-01",
                    "DocumentNumber": "1001",
                    "Contact": "Customer",
                    "Description": "Custom Design",
                    "Amount": 100.0,
                    "ItemRefId": "4",
                    "ItemRefName": "Design",
                    "Qty": 1.0,
                    "UnitPrice": 100.0,
                    "SafeLine": {
                        "Description": "Custom Design",
                        "Amount": 100.0,
                        "ItemRef": {"value": "4", "name": "Design"},
                    },
                }
            ],
            workers=1,
            timeout_seconds=10,
            review_threshold=0.7,
        )

        kwargs = mapper.call_args.kwargs
        self.assertIsNone(kwargs["account_code"])
        self.assertIsNone(kwargs["account_name"])
        self.assertNotIn("Income > Design income", kwargs["description"])
        self.assertNotIn("Accounts Receivable", kwargs["description"])
        self.assertIn("Landscaping Services", kwargs["prompt_template"])
        self.assertIn("Custom Design", kwargs["prompt_template"])
        self.assertNotIn("AccountRef", kwargs["prompt_template"])
        self.assertNotIn("{company_context}", kwargs["prompt_template"])
        self.assertEqual(
            kwargs["mapping_policy_version"],
            QUICKBOOKS_MAPPING_POLICY_VERSION,
        )
        self.assertEqual(mapped[0]["SourceAccountForAudit"], "Income > Design income")
        self.assertEqual(mapped[0]["InferredRole"], "income")
        self.assertEqual(mapped[0]["MatchedItemName"], "Design")
        self.assertFalse(mapped[0]["ReviewRequired"])

    @patch("run_quickbooks.map_description")
    def test_missing_item_and_description_enters_hitl(self, mapper) -> None:
        mapper.return_value = {
            "category": "Expenses > Insurance",
            "confidence": 0.9,
            "reason": "Insurance vendor.",
        }
        line = {
            "LineNumber": 1,
            "Date": "2026-07-02",
            "TransactionType": "Bill",
            "DocumentNumber": "",
            "Contact": "Insurance Agency",
            "Description": "",
            "SplitAccountForAudit": "Accounts Payable",
            "Amount": 2000.0,
            "SourceAccountForAudit": "Other Expenses > Miscellaneous",
            "SourceSectionForAudit": "Other Expenses",
            "AIInputDescription": "Bill involving Insurance Agency",
            "AccountHiddenFromAI": True,
        }
        mapped = _map_lines(
            [line],
            [
                {
                    "name": "Expenses > Insurance",
                    "type": "expense",
                    "description": "Insurance.",
                },
                {
                    "name": "Unmapped",
                    "type": "fallback",
                    "description": "Review.",
                },
            ],
            company_prior={"company_name": "Sandbox", "features": {}},
            item_priors=[],
            transaction_evidence=[
                {
                    "EntityType": "Bill",
                    "ReportTransactionTypes": ("Bill",),
                    "TransactionId": "1",
                    "Date": "2026-07-02",
                    "DocumentNumber": "",
                    "Contact": "Insurance Agency",
                    "Description": "",
                    "Amount": 2000.0,
                    "ItemRefId": "",
                    "ItemRefName": "",
                    "Qty": 0.0,
                    "UnitPrice": 0.0,
                    "SafeLine": {"Amount": 2000.0},
                }
            ],
            workers=1,
            timeout_seconds=10,
            review_threshold=0.7,
        )

        self.assertTrue(mapped[0]["ReviewRequired"])
        self.assertIn("No matched Item", mapped[0]["ReviewReason"])
        self.assertEqual(mapped[0]["AutoAcceptedCategory"], "")


if __name__ == "__main__":
    unittest.main()
