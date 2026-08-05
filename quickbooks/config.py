from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class QuickBooksSettings:
    client_id: str
    client_secret: str
    redirect_uri: str
    realm_id: str | None
    environment: str
    minor_version: int


def load_quickbooks_settings() -> QuickBooksSettings:
    """Load QuickBooks settings without changing the existing Xero config."""

    load_dotenv()

    environment = os.environ.get("QUICKBOOKS_ENVIRONMENT", "sandbox").strip().lower()
    if environment not in {"sandbox", "production"}:
        raise ValueError("QUICKBOOKS_ENVIRONMENT must be 'sandbox' or 'production'.")

    raw_minor_version = os.environ.get("QUICKBOOKS_MINOR_VERSION", "75").strip()
    try:
        minor_version = int(raw_minor_version)
    except ValueError as exc:
        raise ValueError("QUICKBOOKS_MINOR_VERSION must be an integer.") from exc
    if minor_version < 75:
        raise ValueError("QUICKBOOKS_MINOR_VERSION must be at least 75.")

    return QuickBooksSettings(
        client_id=os.environ.get("QUICKBOOKS_CLIENT_ID", "").strip(),
        client_secret=os.environ.get("QUICKBOOKS_CLIENT_SECRET", "").strip(),
        redirect_uri=os.environ.get(
            "QUICKBOOKS_REDIRECT_URI", "http://localhost:51790/callback"
        ).strip(),
        realm_id=os.environ.get("QUICKBOOKS_REALM_ID", "").strip() or None,
        environment=environment,
        minor_version=minor_version,
    )
