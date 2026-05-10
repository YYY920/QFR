from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class Settings:
    xero_client_id: str
    xero_client_secret: str
    xero_redirect_uri: str
    xero_tenant_id: str | None
    gemini_api_key: str | None
    openai_api_key: str | None
    openai_api_key_qfr: str | None


def load_settings() -> Settings:
    """
    Central place to load configuration from environment/.env so that
    login_xero.py and run_mvp.py always share the same config.
    """
    load_dotenv()

    client_id = os.environ.get("XERO_CLIENT_ID") or ""
    client_secret = os.environ.get("XERO_CLIENT_SECRET") or ""
    redirect_uri = os.environ.get("XERO_REDIRECT_URI", "http://localhost:51789/callback")
    tenant_id = os.environ.get("XERO_TENANT_ID") or None
    gemini_key = os.environ.get("GEMINI_API_KEY") or None
    openai_key = os.environ.get("OPENAI_API_KEY") or None
    openai_key_qfr = os.environ.get("OPENAI_API_KEY_QFR") or None

    return Settings(
        xero_client_id=client_id,
        xero_client_secret=client_secret,
        xero_redirect_uri=redirect_uri,
        xero_tenant_id=tenant_id,
        gemini_api_key=gemini_key,
        openai_api_key=openai_key,
        openai_api_key_qfr=openai_key_qfr,
    )

