import json
import os
from typing import Any, Dict, List

from google import genai

from ai.prompts import MAPPING_PROMPT
from ai.memory_store import lookup_mapping, store_mapping


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
    # 1) Try memory/cache first
    cached = lookup_mapping(contact, description)
    if cached:
        return cached

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
        model="gemini-2.5-flash",
        contents=prompt,
    )
    text = (resp.text or "").strip()

    result: Dict[str, Any]
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        # Fallback structure
        result = {
            "category": "Unmapped",
            "confidence": 0.0,
            "reason": "Failed to parse JSON from model output.",
            "raw": text,
        }

    # Ensure minimal structure
    result.setdefault("category", "Unmapped")
    result.setdefault("confidence", 0.0)
    result.setdefault("reason", "No reason provided.")

    # Store into memory for next time
    store_mapping(contact, description, result)
    return result
