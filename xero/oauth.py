import base64
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Any, Optional, Tuple

import requests

AUTH_URL = "https://login.xero.com/identity/connect/authorize"
TOKEN_URL = "https://identity.xero.com/connect/token"
CONNECTIONS_URL = "https://api.xero.com/connections"

SCOPES = [
    "offline_access",
    "accounting.reports.read",
    "accounting.transactions",
    "accounting.journals.read",
    "accounting.settings",
    "accounting.contacts",
    "accounting.attachments.read",
    # Payroll scopes (will be ignored if tenant has no payroll)
    "payroll.employees",
    "payroll.payruns",
    "payroll.payslip",
]

TOKEN_FILE = "xero_token.json"


def _build_basic_auth_header(client_id: str, client_secret: str) -> str:
    token = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    return f"Basic {token}"


def build_auth_url(client_id: str, redirect_uri: str, state: str = "qfr-demo") -> str:
    scope = "%20".join(SCOPES)
    return (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
        f"&state={state}"
    )


def exchange_code_for_token(
    client_id: str, client_secret: str, redirect_uri: str, code: str
) -> Dict[str, Any]:
    headers = {
        "Authorization": _build_basic_auth_header(client_id, client_secret),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    resp = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
    resp.raise_for_status()
    token_data = resp.json()
    _save_token(token_data)
    return token_data


def refresh_access_token(
    client_id: str, client_secret: str, refresh_token: str
) -> Dict[str, Any]:
    headers = {
        "Authorization": _build_basic_auth_header(client_id, client_secret),
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    resp = requests.post(TOKEN_URL, headers=headers, data=data, timeout=30)
    resp.raise_for_status()
    token_data = resp.json()
    _save_token(token_data)
    return token_data


def _save_token(token_data: Dict[str, Any]) -> None:
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(token_data, f, indent=2)


def load_token() -> Optional[Dict[str, Any]]:
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_connections(access_token: str) -> Any:
    resp = requests.get(
        CONNECTIONS_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


class _CallbackHandler(BaseHTTPRequestHandler):
    """Simple local HTTP handler to capture Xero auth code."""

    # These will be set before server starts (class-level shared state)
    auth_code: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self):  # type: ignore[override]
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        if "error" in qs:
            _CallbackHandler.error = qs.get("error", ["unknown"])[0]
        elif "code" in qs:
            # Only set auth_code when we actually receive a code parameter
            _CallbackHandler.auth_code = qs.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h2>Xero auth received.</h2>You can close this tab and return to the terminal.</body></html>"
        )


def run_local_callback_server(port: int = 51789, timeout_seconds: int = 300) -> Tuple[Optional[str], Optional[str]]:
    """Start a local HTTP server to wait for the OAuth redirect and capture ?code=."""

    server = HTTPServer(("localhost", port), _CallbackHandler)

    # Reset shared state before starting
    _CallbackHandler.auth_code = None
    _CallbackHandler.error = None

    def _serve_until_code():
        # Loop handling requests until we either get a code/error or hit the timeout
        server.timeout = 1.0  # seconds per request wait
        deadline = threading.Event()
        # We don't have wall-clock here, we'll just loop up to timeout_seconds times (1s each)
        for _ in range(timeout_seconds):
            if _CallbackHandler.auth_code is not None or _CallbackHandler.error is not None:
                break
            server.handle_request()
        server.server_close()

    thread = threading.Thread(target=_serve_until_code, daemon=True)
    thread.start()
    thread.join(timeout_seconds + 5)
    return _CallbackHandler.auth_code, _CallbackHandler.error


