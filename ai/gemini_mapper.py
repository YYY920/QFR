import json
import os
from hashlib import sha256
from typing import Any, Dict, List

from google import genai

from ai.prompts import MAPPING_PROMPT
from ai.memory_store import lookup_mapping, store_mapping
from ai.mapping_validation import rejected_mapping, validate_mapping_result


MODEL_NAME = "gemini-2.5-flash"
MAPPING_POLICY_VERSION = "qfr-gemini-v2"


def _get_client() -> "genai.Client":
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in environment.")
    return genai.Client(api_key=api_key)


def map_description(
    contact: str,
    description: str,
    amount: float,
    allowed_categories: List[Any],
    account_code: str | None = None,
    account_name: str | None = None,
    tx_type: str | None = None,
) -> Dict[str, Any]:
    taxonomy_json = json.dumps(allowed_categories, sort_keys=True, separators=(",", ":"), default=str)
    cache_context = {
        "mapper": MAPPING_POLICY_VERSION,
        "model": MODEL_NAME,
        "amount": float(amount),
        "account_code": (account_code or "").strip(),
        "account_name": (account_name or "").strip(),
        "tx_type": (tx_type or "").strip(),
        "taxonomy_sha256": sha256(taxonomy_json.encode("utf-8")).hexdigest(),
    }

    cached = lookup_mapping(contact, description, context=cache_context)
    if cached:
        validated_cached, is_valid = validate_mapping_result(cached, allowed_categories)
        if is_valid:
            return validated_cached

    client = _get_client()
    prompt = MAPPING_PROMPT.format(
        allowed_categories=json.dumps(allowed_categories, indent=2),
        contact=contact or "Unknown",
        description=description or "",
        amount=amount,
        account_code=account_code or "",
        account_name=account_name or "",
        tx_type=tx_type or "",
    )

    resp = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
    )
    text = (resp.text or "").strip()

    try:
        candidate = json.loads(text)
    except json.JSONDecodeError:
        return rejected_mapping(
            "Rejected Gemini output: failed to parse a JSON object.",
            "VALIDATION_JSON_PARSE_FAILED",
        )

    result, is_valid = validate_mapping_result(candidate, allowed_categories)
    if not is_valid:
        return result

    store_mapping(contact, description, result, context=cache_context)
    return result
