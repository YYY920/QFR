from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests

AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
ACCOUNTING_SCOPE = "com.intuit.quickbooks.accounting"
TOKEN_FILE = Path("quickbooks_token.json")


def generate_state() -> str:
    """Generate an anti-forgery value for one OAuth authorization attempt."""

    return secrets.token_urlsafe(32)


def build_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": ACCOUNTING_SCOPE,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _save_token(
    token_data: dict[str, Any],
    realm_id: str | None,
    token_file: Path = TOKEN_FILE,
) -> dict[str, Any]:
    stored = dict(token_data)
    if realm_id:
        stored["realm_id"] = realm_id
    stored["obtained_at"] = int(time.time())

    token_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = token_file.with_name(f".{token_file.name}.tmp")
    temporary_file.write_text(json.dumps(stored, indent=2), encoding="utf-8")
    try:
        os.chmod(temporary_file, 0o600)
    except OSError:
        pass
    temporary_file.replace(token_file)
    return stored


def load_token(token_file: Path = TOKEN_FILE) -> dict[str, Any] | None:
    if not token_file.exists():
        return None
    payload = json.loads(token_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Token file must contain a JSON object: {token_file}")
    return payload


def token_is_expired(token_data: dict[str, Any], leeway_seconds: int = 60) -> bool:
    obtained_at = token_data.get("obtained_at")
    expires_in = token_data.get("expires_in")
    if not isinstance(obtained_at, (int, float)) or not isinstance(expires_in, (int, float)):
        return True
    return time.time() >= obtained_at + expires_in - leeway_seconds


def _token_request(
    client_id: str,
    client_secret: str,
    data: dict[str, str],
) -> dict[str, Any]:
    response = requests.post(
        TOKEN_URL,
        auth=(client_id, client_secret),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "x-include-refresh-token-hard-expires-in": "true",
        },
        data=data,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("Intuit token endpoint returned a non-object response.")
    return payload


def exchange_code_for_token(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    realm_id: str,
    token_file: Path = TOKEN_FILE,
) -> dict[str, Any]:
    token_data = _token_request(
        client_id,
        client_secret,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )
    return _save_token(token_data, realm_id, token_file)


def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
    realm_id: str | None,
    token_file: Path = TOKEN_FILE,
) -> dict[str, Any]:
    token_data = _token_request(
        client_id,
        client_secret,
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    return _save_token(token_data, realm_id, token_file)


@dataclass
class OAuthCallback:
    code: str | None = None
    realm_id: str | None = None
    state: str | None = None
    error: str | None = None

    @property
    def complete(self) -> bool:
        return self.code is not None or self.error is not None


class _CallbackServer(HTTPServer):
    callback: OAuthCallback
    callback_path: str


class _CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        server = self.server
        if not isinstance(server, _CallbackServer) or parsed.path != server.callback_path:
            self.send_error(404)
            return

        query = parse_qs(parsed.query)
        server.callback = OAuthCallback(
            code=query.get("code", [None])[0],
            realm_id=query.get("realmId", [None])[0],
            state=query.get("state", [None])[0],
            error=query.get("error_description", query.get("error", [None]))[0],
        )
        body = (
            b"<html><body><h2>QuickBooks authorization received.</h2>"
            b"You can close this tab and return to the terminal.</body></html>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_local_callback_server(
    redirect_uri: str,
    timeout_seconds: int = 300,
) -> OAuthCallback:
    parsed = urlparse(redirect_uri)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError("Local login requires an http://localhost or http://127.0.0.1 redirect URI.")
    if parsed.port is None:
        raise ValueError("QUICKBOOKS_REDIRECT_URI must include a port.")

    callback_path = parsed.path or "/"
    server = _CallbackServer((parsed.hostname, parsed.port), _CallbackHandler)
    server.callback = OAuthCallback()
    server.callback_path = callback_path
    server.timeout = 1.0
    deadline = time.monotonic() + timeout_seconds
    try:
        while not server.callback.complete and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    return server.callback
