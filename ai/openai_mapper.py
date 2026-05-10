import json
from typing import Any, Dict, List

import requests

from config import load_settings
from ai.prompts import MAPPING_PROMPT
from ai.memory_store import lookup_mapping, store_mapping


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


def _fallback_mapping(
    allowed_categories: List[Any],
    account_name: str | None,
    reason: str,
) -> Dict[str, Any]:
    allowed_names = [
        str(item.get("name") if isinstance(item, dict) else item)
        for item in allowed_categories
        if item
    ]
    if account_name and account_name in allowed_names:
        return {
            "category": account_name,
            "confidence": 0.85,
            "reason": f"{reason}; fallback used matching Xero account name.",
            "rule_id": "FALLBACK_ACCOUNT_NAME_MATCH",
        }
    fallback_category = "Unmapped" if "Unmapped" in allowed_names else allowed_names[0] if allowed_names else "Unmapped"
    return {
        "category": fallback_category,
        "confidence": 0.0,
        "reason": reason,
        "rule_id": "FALLBACK_MODEL_UNAVAILABLE",
    }


def _get_api_key() -> str:
    settings = load_settings()
    # Always use OpenAI for mapping
    api_key = settings.openai_api_key_qfr or settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY_QFR or OPENAI_API_KEY must be set in environment/.env")

    return api_key


def map_description(
    contact: str,
    description: str,
    amount: float,
    allowed_categories: List[Any],
    account_code: str | None = None,
    account_name: str | None = None,
    tx_type: str | None = None,
) -> Dict[str, Any]:
    # 1) Check local memory cache first
    cached = lookup_mapping(contact, description)
    if cached:
        return cached

    api_key = _get_api_key()
    prompt = MAPPING_PROMPT.format(
        allowed_categories=json.dumps(allowed_categories, indent=2),
        contact=contact or "Unknown",
        description=description or "",
        amount=amount,
        account_code=account_code or "",
        account_name=account_name or "",
        tx_type=tx_type or "",
    )

    model_name = "gpt-4o-mini"

    payload: Dict[str, Any] = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a precise accounting assistant. "
                    "Return one valid JSON object only, no code fences, no extra text."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.1,
        # Enforce JSON-only responses for reliable parsing.
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
            timeout=60,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code == 429:
            reason = "OpenAI rate limit reached during mapping"
        else:
            reason = f"OpenAI mapping request failed: {exc}"
        return _fallback_mapping(allowed_categories, account_name, reason)

    response_payload = response.json()

    text = (
        response_payload.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )

    # Some models wrap JSON in ```json ... ``` fences – strip them if present
    if text.startswith("```"):
        parts = text.split("\n", 1)
        if len(parts) == 2:
            text = parts[1].strip()
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0].strip()

    try:
        result: Dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        # Try a minimal fallback: locate first { ... } block
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start : end + 1]
            try:
                result = json.loads(candidate)
            except json.JSONDecodeError:
                result = {
                    "category": "Unmapped",
                    "confidence": 0.0,
                    "reason": "Failed to parse JSON from model output.",
                    "raw": text[:500],
                }
        else:
            result = {
                "category": "Unmapped",
                "confidence": 0.0,
                "reason": "Failed to parse JSON from model output.",
                "raw": text[:500],
            }

    result.setdefault("category", "Unmapped")
    result.setdefault("confidence", 0.0)
    result.setdefault("reason", "No reason provided.")

    # Avoid caching failed parses so they can be retried
    if result.get("reason") != "Failed to parse JSON from model output.":
        store_mapping(contact, description, result)
    return result
