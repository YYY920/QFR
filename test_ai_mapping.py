from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from ai import memory_store
from ai.mapping_validation import validate_mapping_result
from ai.openai_mapper import _parse_json_object, map_description
from run_mvp import _map_profit_loss_rows, prepare_category_lists


ALLOWED = [
    {"name": "Sales", "type": "income", "description": "Revenue"},
    {"name": "Unmapped", "type": "fallback", "description": "Review required"},
]


class MappingValidationTests(unittest.TestCase):
    def test_configured_payloads_include_explicit_unmapped_fallback(self) -> None:
        definitions = prepare_category_lists()
        for key in ("allowed_payload", "income_payload", "payroll_payload"):
            self.assertIn("Unmapped", [item["name"] for item in definitions[key]])

    def test_accepts_complete_valid_mapping(self) -> None:
        result, valid = validate_mapping_result(
            {"category": "Sales", "confidence": 0.91, "reason": "Revenue line."},
            ALLOWED,
        )
        self.assertTrue(valid)
        self.assertEqual(result["category"], "Sales")
        self.assertEqual(result["confidence"], 0.91)

    def test_rejects_category_outside_taxonomy(self) -> None:
        result, valid = validate_mapping_result(
            {"category": "Invented Revenue", "confidence": 0.9, "reason": "Guess."},
            ALLOWED,
        )
        self.assertFalse(valid)
        self.assertEqual(result["category"], "Unmapped")
        self.assertEqual(result["rule_id"], "VALIDATION_INVALID_CATEGORY")

    def test_rejects_non_numeric_boolean_and_out_of_range_confidence(self) -> None:
        for confidence in ("0.9", True, -0.01, 1.01, float("nan")):
            with self.subTest(confidence=confidence):
                result, valid = validate_mapping_result(
                    {"category": "Sales", "confidence": confidence, "reason": "Guess."},
                    ALLOWED,
                )
                self.assertFalse(valid)
                self.assertEqual(result["rule_id"], "VALIDATION_INVALID_CONFIDENCE")

    def test_rejects_empty_reason(self) -> None:
        result, valid = validate_mapping_result(
            {"category": "Sales", "confidence": 0.9, "reason": "  "},
            ALLOWED,
        )
        self.assertFalse(valid)
        self.assertEqual(result["rule_id"], "VALIDATION_INVALID_REASON")


class MemoryStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_memory_file = memory_store.MEMORY_FILE
        memory_store.MEMORY_FILE = Path(self.temp_dir.name) / "mapping_memory.json"

    def tearDown(self) -> None:
        memory_store.MEMORY_FILE = self.original_memory_file
        self.temp_dir.cleanup()

    def test_migrates_v1_cache_without_reusing_contextless_entries(self) -> None:
        memory_store.MEMORY_FILE.write_text(
            json.dumps(
                {
                    "legacy-key": {
                        "category": "Sales",
                        "confidence": 0.9,
                        "reason": "Legacy mapping",
                    }
                }
            ),
            encoding="utf-8",
        )

        self.assertIsNone(memory_store.lookup_mapping("Acme", "Consulting", context={"model": "v2"}))
        migrated = json.loads(memory_store.MEMORY_FILE.read_text(encoding="utf-8"))
        self.assertEqual(migrated["_meta"]["schema_version"], 2)
        self.assertEqual(migrated["_meta"]["legacy_entry_count"], 1)
        self.assertIn("legacy_entries", migrated)

    def test_cache_key_includes_mapping_context(self) -> None:
        mapping = {"category": "Sales", "confidence": 0.9, "reason": "Revenue"}
        memory_store.store_mapping("Acme", "Service", mapping, context={"account_code": "200"})

        self.assertEqual(
            memory_store.lookup_mapping("Acme", "Service", context={"account_code": "200"}),
            mapping,
        )
        self.assertIsNone(
            memory_store.lookup_mapping("Acme", "Service", context={"account_code": "453"})
        )

    def test_concurrent_writes_remain_valid_and_complete(self) -> None:
        def write(index: int) -> None:
            memory_store.store_mapping(
                f"Contact {index}",
                "Service",
                {"category": "Sales", "confidence": 0.9, "reason": f"Row {index}"},
                context={"row": index},
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(write, range(40)))

        payload = json.loads(memory_store.MEMORY_FILE.read_text(encoding="utf-8"))
        self.assertEqual(payload["_meta"]["schema_version"], 2)
        self.assertEqual(len(payload["entries"]), 40)


class OpenAIMapperTests(unittest.TestCase):
    def test_json_parser_rejects_fences_and_extra_commentary(self) -> None:
        self.assertIsNone(_parse_json_object('```json\n{"category":"Sales"}\n```'))
        self.assertIsNone(_parse_json_object('Result: {"category":"Sales"}'))

    @staticmethod
    def _response(content: str) -> Mock:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [{"message": {"content": content}}]
        }
        return response

    @patch("ai.openai_mapper.store_mapping")
    @patch("ai.openai_mapper.lookup_mapping", return_value=None)
    @patch("ai.openai_mapper._get_api_key", return_value="test-key")
    @patch("ai.openai_mapper.requests.post")
    def test_invalid_model_category_is_rejected_and_not_cached(
        self,
        post: Mock,
        _api_key: Mock,
        _lookup: Mock,
        store: Mock,
    ) -> None:
        post.return_value = self._response(
            json.dumps({"category": "Made Up", "confidence": 0.95, "reason": "Guess"})
        )
        result = map_description("Acme", "Service", 100, ALLOWED, account_code="200")
        self.assertEqual(result["category"], "Unmapped")
        self.assertEqual(result["rule_id"], "VALIDATION_INVALID_CATEGORY")
        store.assert_not_called()

    @patch("ai.openai_mapper.store_mapping")
    @patch("ai.openai_mapper.lookup_mapping", return_value=None)
    @patch("ai.openai_mapper._get_api_key", return_value="test-key")
    @patch("ai.openai_mapper.requests.post")
    def test_valid_model_result_is_normalized_and_cached(
        self,
        post: Mock,
        _api_key: Mock,
        _lookup: Mock,
        store: Mock,
    ) -> None:
        post.return_value = self._response(
            json.dumps({"category": "Sales", "confidence": 1, "reason": " Revenue line. "})
        )
        result = map_description(
            "Acme",
            "Service",
            100,
            ALLOWED,
            account_code="200",
            request_timeout_seconds=12,
        )
        self.assertEqual(result, {"category": "Sales", "confidence": 1.0, "reason": "Revenue line."})
        self.assertEqual(post.call_args.kwargs["timeout"], 12)
        store.assert_called_once()


class ConcurrentMappingTests(unittest.TestCase):
    def test_concurrent_mapping_preserves_source_order(self) -> None:
        rows = [
            {
                "Type": "Invoice",
                "InvoiceNumber": str(index),
                "Date": "2026-01-01",
                "Contact": "Acme",
                "AccountCode": "200",
                "AccountName": "Sales",
                "Description": str(index),
                "Amount": 100.0,
            }
            for index in range(8)
        ]
        category_defs = {
            "fallback": "Unmapped",
            "allowed_payload": ALLOWED,
            "income_payload": ALLOWED,
            "payroll_payload": ALLOWED,
        }
        active = 0
        peak = 0
        counter_lock = threading.Lock()

        def fake_map_description(**kwargs):
            nonlocal active, peak
            with counter_lock:
                active += 1
                peak = max(peak, active)
            time.sleep((8 - int(kwargs["description"])) * 0.002)
            with counter_lock:
                active -= 1
            return {"category": "Sales", "confidence": 0.9, "reason": "Revenue"}

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("run_mvp.map_description", side_effect=fake_map_description):
                result = _map_profit_loss_rows(
                    rows,
                    category_defs,
                    worker_count=4,
                    request_timeout_seconds=10,
                    progress_path=Path(temp_dir) / "progress.html",
                    progress_json_path=Path(temp_dir) / "progress.json",
                    write_progress=False,
                )

        self.assertGreater(peak, 1)
        self.assertEqual([row["InvoiceNumber"] for row in result], [str(i) for i in range(8)])


if __name__ == "__main__":
    unittest.main()
