from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from quickbooks.client import QuickBooksClient
from quickbooks.entities import default_where
from quickbooks.oauth import (
    ACCOUNTING_SCOPE,
    build_auth_url,
    load_token,
    refresh_access_token,
    token_is_expired,
)
from quickbooks.reports import build_report_params


class QuickBooksOAuthTests(unittest.TestCase):
    def test_auth_url_contains_accounting_scope_and_state(self) -> None:
        url = build_auth_url("client", "http://localhost:51790/callback", "safe-state")
        params = parse_qs(urlparse(url).query)
        self.assertEqual(params["client_id"], ["client"])
        self.assertEqual(params["redirect_uri"], ["http://localhost:51790/callback"])
        self.assertEqual(params["scope"], [ACCOUNTING_SCOPE])
        self.assertEqual(params["state"], ["safe-state"])

    @patch("quickbooks.oauth.requests.post")
    def test_refresh_saves_rotated_token_and_realm(self, post: Mock) -> None:
        response = Mock()
        response.json.return_value = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
        }
        response.raise_for_status.return_value = None
        post.return_value = response

        with tempfile.TemporaryDirectory() as temporary_dir:
            token_file = Path(temporary_dir) / "token.json"
            refresh_access_token("id", "secret", "old-refresh", "123", token_file)
            stored = load_token(token_file)

        self.assertEqual(stored["access_token"], "new-access")
        self.assertEqual(stored["refresh_token"], "new-refresh")
        self.assertEqual(stored["realm_id"], "123")
        self.assertIn("obtained_at", stored)

    def test_token_without_timestamp_is_treated_as_expired(self) -> None:
        self.assertTrue(token_is_expired({"access_token": "old", "expires_in": 3600}))


class QuickBooksClientTests(unittest.TestCase):
    def test_query_all_paginates_and_preserves_raw_objects(self) -> None:
        session = Mock()
        page_one = Mock(ok=True, status_code=200)
        page_one.json.return_value = {
            "QueryResponse": {"Invoice": [{"Id": "1"}, {"Id": "2"}]}
        }
        page_two = Mock(ok=True, status_code=200)
        page_two.json.return_value = {"QueryResponse": {"Invoice": [{"Id": "3"}]}}
        session.request.side_effect = [page_one, page_two]
        client = QuickBooksClient("token", "realm", session=session)

        records = client.query_all("Invoice", page_size=2)

        self.assertEqual(records, [{"Id": "1"}, {"Id": "2"}, {"Id": "3"}])
        first_query = session.request.call_args_list[0].kwargs["params"]["query"]
        second_query = session.request.call_args_list[1].kwargs["params"]["query"]
        self.assertIn("STARTPOSITION 1 MAXRESULTS 2", first_query)
        self.assertIn("STARTPOSITION 3 MAXRESULTS 2", second_query)

    def test_environment_selects_sandbox_base_url(self) -> None:
        client = QuickBooksClient("token", "realm", environment="sandbox")
        self.assertEqual(client.base_url, "https://sandbox-quickbooks.api.intuit.com/v3")

    def test_list_entities_include_inactive_records(self) -> None:
        self.assertEqual(default_where("Account"), "Active IN (true, false)")
        self.assertIsNone(default_where("Invoice"))


class QuickBooksReportTests(unittest.TestCase):
    def test_period_report_parameters(self) -> None:
        params = build_report_params(
            "ProfitAndLoss",
            from_date="2026-01-01",
            to_date="2026-03-31",
            accounting_method="Cash",
        )
        self.assertEqual(
            params,
            {
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
                "accounting_method": "Cash",
            },
        )

    def test_as_of_report_parameters(self) -> None:
        params = build_report_params(
            "AgedReceivables",
            from_date="2026-01-01",
            to_date="2026-03-31",
        )
        self.assertEqual(
            params,
            {"report_date": "2026-03-31", "accounting_method": "Accrual"},
        )


if __name__ == "__main__":
    unittest.main()
