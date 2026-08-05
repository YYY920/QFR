from __future__ import annotations

import argparse

from quickbooks.client import QuickBooksClient
from quickbooks.config import load_quickbooks_settings
from quickbooks.oauth import (
    build_auth_url,
    exchange_code_for_token,
    generate_state,
    load_token,
    refresh_access_token,
    run_local_callback_server,
)


def _company_name(payload: dict[str, object]) -> str:
    company = payload.get("CompanyInfo")
    if isinstance(company, dict):
        name = company.get("CompanyName")
        if name:
            return str(name)
    return "Unknown company"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Connect QFR to a QuickBooks Online company.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore the saved token and authorize a company again.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_quickbooks_settings()
    if not settings.client_id or not settings.client_secret:
        raise SystemExit(
            "Set QUICKBOOKS_CLIENT_ID and QUICKBOOKS_CLIENT_SECRET in your environment/.env file."
        )

    token = None if args.force else load_token()
    if token and token.get("refresh_token"):
        realm_id = str(token.get("realm_id") or settings.realm_id or "")
        if not realm_id:
            raise SystemExit("The saved token has no realm ID. Run with --force to reconnect.")
        print("Existing QuickBooks token found. Refreshing it...")
        token = refresh_access_token(
            settings.client_id,
            settings.client_secret,
            str(token["refresh_token"]),
            realm_id,
        )
    else:
        state = generate_state()
        auth_url = build_auth_url(settings.client_id, settings.redirect_uri, state)
        print("Open this URL and choose your QuickBooks Online sandbox company:")
        print(auth_url)
        print()
        print(f"Waiting for the redirect at {settings.redirect_uri} ...")
        callback = run_local_callback_server(settings.redirect_uri)
        if callback.error:
            raise SystemExit(f"QuickBooks authorization failed: {callback.error}")
        if not callback.code or not callback.realm_id:
            raise SystemExit("QuickBooks did not return an authorization code and realmId before timeout.")
        if callback.state != state:
            raise SystemExit("QuickBooks OAuth state did not match; authorization was rejected.")
        token = exchange_code_for_token(
            settings.client_id,
            settings.client_secret,
            settings.redirect_uri,
            callback.code,
            callback.realm_id,
        )
        realm_id = callback.realm_id

    client = QuickBooksClient(
        str(token["access_token"]),
        realm_id,
        settings.environment,
        settings.minor_version,
    )
    company_info = client.get_company_info()
    print(f"Connected to: {_company_name(company_info)} (realmId={realm_id})")
    print("Token saved to quickbooks_token.json.")
    print("Next: python download_quickbooks_data.py")


if __name__ == "__main__":
    main()
