from __future__ import annotations

import math
from typing import Any, Dict, Iterable


FALLBACK_CATEGORY = "Unmapped"


def allowed_category_names(allowed_categories: Iterable[Any]) -> list[str]:
    """Return a de-duplicated list of configured category names."""
    names: list[str] = []
    for item in allowed_categories:
        value = item.get("name") if isinstance(item, dict) else item
        if not isinstance(value, str):
            continue
        name = value.strip()
        if name and name not in names:
            names.append(name)
    return names


def rejected_mapping(reason: str, rule_id: str) -> Dict[str, Any]:
    """Build a deterministic, reviewable result for rejected model output."""
    return {
        "category": FALLBACK_CATEGORY,
        "confidence": 0.0,
        "reason": reason,
        "rule_id": rule_id,
    }


def validate_mapping_result(
    candidate: Any,
    allowed_categories: Iterable[Any],
) -> tuple[Dict[str, Any], bool]:
    """
    Validate the complete model contract.

    Model categories must match the configured taxonomy exactly. Confidence
    must be a finite JSON number in the inclusive range [0, 1]; booleans and
    numeric strings are deliberately rejected instead of silently coerced.
    """
    if not isinstance(candidate, dict):
        return (
            rejected_mapping(
                "Rejected model output: expected one JSON object.",
                "VALIDATION_NOT_AN_OBJECT",
            ),
            False,
        )

    names = allowed_category_names(allowed_categories)
    category = candidate.get("category")
    if not isinstance(category, str) or category.strip() not in names:
        rendered = repr(category)[:160]
        return (
            rejected_mapping(
                f"Rejected model output: category {rendered} is not in the allowed taxonomy.",
                "VALIDATION_INVALID_CATEGORY",
            ),
            False,
        )

    confidence = candidate.get("confidence")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(float(confidence))
        or not 0.0 <= float(confidence) <= 1.0
    ):
        rendered = repr(confidence)[:160]
        return (
            rejected_mapping(
                f"Rejected model output: confidence {rendered} must be a finite number between 0 and 1.",
                "VALIDATION_INVALID_CONFIDENCE",
            ),
            False,
        )

    reason = candidate.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return (
            rejected_mapping(
                "Rejected model output: reason must be a non-empty string.",
                "VALIDATION_INVALID_REASON",
            ),
            False,
        )

    validated: Dict[str, Any] = {
        "category": category.strip(),
        "confidence": float(confidence),
        "reason": reason.strip(),
    }
    rule_id = candidate.get("rule_id")
    if isinstance(rule_id, str) and rule_id.strip():
        validated["rule_id"] = rule_id.strip()
    return validated, True
