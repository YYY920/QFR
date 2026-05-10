from config import load_settings
from xero.oauth import (
    build_auth_url,
    exchange_code_for_token,
    load_token,
    refresh_access_token,
    get_connections,
    run_local_callback_server,
)


def main() -> None:
    settings = load_settings()
    client_id = settings.xero_client_id
    client_secret = settings.xero_client_secret
    redirect_uri = settings.xero_redirect_uri

    if not client_id or not client_secret:
        raise SystemExit("Please set XERO_CLIENT_ID and XERO_CLIENT_SECRET in your environment/.env file.")

    # Try existing token + refresh token first
    token = load_token()
    if token and token.get("refresh_token"):
        print("Existing token found. Trying to refresh...")
        token = refresh_access_token(client_id, client_secret, token["refresh_token"])
        access_token = token["access_token"]
    else:
        # No token yet, run full auth code flow
        auth_url = build_auth_url(client_id, redirect_uri)
        print("Open this URL in your browser to login to Xero Demo Company and approve access:")
        print(auth_url)
        print()
        print("Waiting for redirect at:", redirect_uri)

        code, error = run_local_callback_server(port=int(redirect_uri.split(":")[-1].split("/")[0]))
        if error:
            raise SystemExit(f"Error returned from Xero auth: {error}")
        if not code:
            raise SystemExit("Did not receive an auth code from Xero (timeout).")

        token = exchange_code_for_token(client_id, client_secret, redirect_uri, code)
        access_token = token["access_token"]

    # Discover tenant (Demo Company) and store tenant id
    connections = get_connections(access_token)
    if not connections:
        raise SystemExit("No Xero connections found for this user.")

    # For MVP: just pick the first connection (typically Demo Company if you used it)
    tenant_id = connections[0]["tenantId"]
    print("Using tenant:", connections[0].get("tenantName"), "-", tenant_id)

    # Persist tenant id into environment file if .env exists
    if __import__("os").path.exists(".env"):
        # append or replace XERO_TENANT_ID
        import os

        with open(".env", "r", encoding="utf-8") as f:
            lines = f.readlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith("XERO_TENANT_ID="):
                lines[i] = f"XERO_TENANT_ID={tenant_id}\n"
                found = True
                break
        if not found:
            lines.append(f"XERO_TENANT_ID={tenant_id}\n")
        with open(".env", "w", encoding="utf-8") as f:
            f.writelines(lines)
        print("Saved XERO_TENANT_ID into .env")

    print("Login complete. You can now run `python run_mvp.py`.")


if __name__ == "__main__":
    main()

