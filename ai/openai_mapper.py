from __future__ import annotations

import json
import os
import threading
from hashlib import sha256
from typing import Any, Dict, List

import requests

from ai.mapping_validation import (
    FALLBACK_CATEGORY,
    allowed_category_names,
    rejected_mapping,
    validate_mapping_result,
)
from ai.memory_store import lookup_mapping, store_mapping
from ai.prompts import MAPPING_PROMPT
from config import load_settings


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
MODEL_NAME = "gpt-4o-mini"
MAPPING_POLICY_VERSION = "qfr-openai-v2"
DEFAULT_TIMEOUT_SECONDS = 30.0

_REQUEST_LOCKS: dict[str, threading.Lock] = {}
_REQUEST_LOCKS_GUARD = threading.Lock()


def _fallback_mapping(
    allowed_categories: List[Any],
    account_name: str | None,
    reason: str,
) -> Dict[str, Any]:
    allowed_names = allowed_category_names(allowed_categories)
    if account_name and account_name in allowed_names:
        return {
            "category": account_name,
            "confidence": 0.85,
            "reason": f"{reason}; fallback used matching Xero account name.",
            "rule_id": "FALLBACK_ACCOUNT_NAME_MATCH",
        }
    return {
        "category": FALLBACK_CATEGORY,
        "confidence": 0.0,
        "reason": reason,
        "rule_id": "FALLBACK_MODEL_UNAVAILABLE",
    }


def _get_api_key() -> str:
    settings = load_settings()
    api_key = settings.openai_api_key_qfr or settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY_QFR or OPENAI_API_KEY must be set in environment/.env")
    return api_key


def _request_timeout(request_timeout_seconds: float | None) -> float:
    if request_timeout_seconds is not None:
        timeout = float(request_timeout_seconds)
    else:
        try:
            timeout = float(os.environ.get("OPENAI_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS)))
        except ValueError:
            timeout = DEFAULT_TIMEOUT_SECONDS
    if not 1.0 <= timeout <= 120.0:
        return DEFAULT_TIMEOUT_SECONDS
    return timeout


def _cache_context(
    amount: float,
    allowed_categories: List[Any],
    account_code: str | None,
    account_name: str | None,
    tx_type: str | None,
    mapping_policy_version: str,
) -> Dict[str, Any]:
    taxonomy_json = json.dumps(allowed_categories, sort_keys=True, separators=(",", ":"), default=str)
    return {
        "mapper": mapping_policy_version,
        "model": MODEL_NAME,
        "amount": float(amount),
        "account_code": (account_code or "").strip(),
        "account_name": (account_name or "").strip(),
        "tx_type": (tx_type or "").strip(),
        "taxonomy_sha256": sha256(taxonomy_json.encode("utf-8")).hexdigest(),
    }


def _singleflight_lock(contact: str, description: str, context: Dict[str, Any]) -> threading.Lock:
    identity = json.dumps(
        {
            "contact": (contact or "").strip().lower(),
            "description": (description or "").strip().lower(),
            "context": context,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    key = sha256(identity.encode("utf-8")).hexdigest()
    with _REQUEST_LOCKS_GUARD:
        return _REQUEST_LOCKS.setdefault(key, threading.Lock())


def _parse_json_object(text: str) -> Any:
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None


def map_description(
    contact: str,
    description: str,
    amount: float,
    allowed_categories: List[Any],
    account_code: str | None = None,
    account_name: str | None = None,
    tx_type: str | None = None,
    request_timeout_seconds: float | None = None,
    prompt_template: str = MAPPING_PROMPT,
    mapping_policy_version: str = MAPPING_POLICY_VERSION,
) -> Dict[str, Any]:
    policy_version = mapping_policy_version.strip() or MAPPING_POLICY_VERSION
    context = _cache_context(
        amount,
        allowed_categories,
        account_code,
        account_name,
        tx_type,
        policy_version,
    )

    cached = lookup_mapping(contact, description, context=context)
    if cached:
        validated_cached, is_valid = validate_mapping_result(cached, allowed_categories)
        if is_valid:
            return validated_cached

    # Prevent duplicate concurrent API requests for identical mapping context.
    with _singleflight_lock(contact, description, context):
        cached = lookup_mapping(contact, description, context=context)
        if cached:
            validated_cached, is_valid = validate_mapping_result(cached, allowed_categories)
            if is_valid:
                return validated_cached

        try:
            api_key = _get_api_key()
        except RuntimeError as exc:
            return _fallback_mapping(allowed_categories, account_name, str(exc))

        prompt = prompt_template.format(
            allowed_categories=json.dumps(allowed_categories, indent=2),
            contact=contact or "Unknown",
            description=description or "",
            amount=amount,
            account_code=account_code or "",
            account_name=account_name or "",
            tx_type=tx_type or "",
        )
        payload: Dict[str, Any] = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a precise accounting assistant. "
                        "Return one valid JSON object only, no code fences, no extra text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "max_tokens": 256,
        }

        try:
            response = requests.post(
                OPENAI_CHAT_COMPLETIONS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=_request_timeout(request_timeout_seconds),
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            reason = (
                "OpenAI rate limit reached during mapping"
                if status_code == 429
                else f"OpenAI mapping request failed: {exc}"
            )
            return _fallback_mapping(allowed_categories, account_name, reason)

        try:
            response_payload = response.json()
            text = (
                response_payload.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
        except (ValueError, AttributeError, IndexError, TypeError) as exc:
            return rejected_mapping(
                f"Rejected model response: invalid OpenAI response envelope ({exc}).",
                "VALIDATION_INVALID_RESPONSE_ENVELOPE",
            )

        if not isinstance(text, str):
            return rejected_mapping(
                "Rejected model response: message content must be a string.",
                "VALIDATION_INVALID_RESPONSE_CONTENT",
            )

        candidate = _parse_json_object(text)
        if candidate is None:
            return rejected_mapping(
                "Rejected model output: failed to parse a JSON object.",
                "VALIDATION_JSON_PARSE_FAILED",
            )

        result, is_valid = validate_mapping_result(candidate, allowed_categories)
        if not is_valid:
            return result

        store_mapping(contact, description, result, context=context)
        return result
