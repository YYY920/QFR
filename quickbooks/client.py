from __future__ import annotations

import re
from typing import Any, Mapping

import requests

SANDBOX_BASE_URL = "https://sandbox-quickbooks.api.intuit.com/v3"
PRODUCTION_BASE_URL = "https://quickbooks.api.intuit.com/v3"
_RESOURCE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")


class QuickBooksAPIError(RuntimeError):
    def __init__(self, status_code: int, url: str, detail: str) -> None:
        self.status_code = status_code
        self.url = url
        self.detail = detail
        super().__init__(f"QuickBooks API returned HTTP {status_code} for {url}: {detail}")


class QuickBooksClient:
    """Small read-only client for the QuickBooks Online Accounting API."""

    def __init__(
        self,
        access_token: str,
        realm_id: str,
        environment: str = "sandbox",
        minor_version: int = 75,
        timeout_seconds: int = 60,
        session: requests.Session | None = None,
    ) -> None:
        if environment not in {"sandbox", "production"}:
            raise ValueError("environment must be 'sandbox' or 'production'.")
        if not realm_id:
            raise ValueError("realm_id is required.")
        if minor_version < 75:
            raise ValueError("minor_version must be at least 75.")

        self.access_token = access_token
        self.realm_id = realm_id
        self.environment = environment
        self.minor_version = minor_version
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.base_url = SANDBOX_BASE_URL if environment == "sandbox" else PRODUCTION_BASE_URL

    def _request(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        query_params = dict(params or {})
        query_params.setdefault("minorversion", self.minor_version)
        url = f"{self.base_url}/company/{self.realm_id}/{path.lstrip('/')}"
        response = self.session.request(
            "GET",
            url,
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            },
            params=query_params,
            timeout=self.timeout_seconds,
        )
        if not response.ok:
            try:
                payload = response.json()
                detail = _fault_detail(payload)
            except (ValueError, TypeError):
                detail = response.text[:1000] or response.reason
            raise QuickBooksAPIError(response.status_code, url, detail)

        payload = response.json()
        if not isinstance(payload, dict):
            raise QuickBooksAPIError(response.status_code, url, "Expected a JSON object response")
        return payload

    def get_company_info(self) -> dict[str, Any]:
        return self._request(f"companyinfo/{self.realm_id}")

    def query(self, statement: str) -> dict[str, Any]:
        return self._request("query", {"query": statement})

    def query_all(
        self,
        entity_name: str,
        *,
        where: str | None = None,
        page_size: int = 1000,
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        if not _RESOURCE_NAME.fullmatch(entity_name):
            raise ValueError(f"Invalid QuickBooks entity name: {entity_name!r}")
        if not 1 <= page_size <= 1000:
            raise ValueError("page_size must be between 1 and 1000.")
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1.")

        records: list[dict[str, Any]] = []
        start_position = 1
        for _ in range(max_pages):
            statement = f"SELECT * FROM {entity_name}"
            if where:
                statement += f" WHERE {where}"
            statement += f" STARTPOSITION {start_position} MAXRESULTS {page_size}"
            payload = self.query(statement)
            query_response = payload.get("QueryResponse", {})
            if not isinstance(query_response, dict):
                raise QuickBooksAPIError(200, "query", "QueryResponse is not a JSON object")
            page = query_response.get(entity_name, [])
            if isinstance(page, dict):
                page = [page]
            if not isinstance(page, list):
                raise QuickBooksAPIError(200, "query", f"{entity_name} result is not a list")
            records.extend(item for item in page if isinstance(item, dict))
            if len(page) < page_size:
                return records
            start_position += page_size

        raise RuntimeError(
            f"Stopped {entity_name} pagination at max_pages={max_pages}; "
            "increase --max-pages to fetch the remaining rows."
        )

    def get_report(
        self,
        report_name: str,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not _RESOURCE_NAME.fullmatch(report_name):
            raise ValueError(f"Invalid QuickBooks report name: {report_name!r}")
        return self._request(f"reports/{report_name}", params)


def _fault_detail(payload: Any) -> str:
    if not isinstance(payload, dict):
        return str(payload)[:1000]
    fault = payload.get("Fault")
    if not isinstance(fault, dict):
        return str(payload)[:1000]
    errors = fault.get("Error", [])
    if isinstance(errors, dict):
        errors = [errors]
    details: list[str] = []
    if isinstance(errors, list):
        for error in errors:
            if not isinstance(error, dict):
                continue
            code = error.get("code")
            message = error.get("Message") or error.get("message")
            detail = error.get("Detail") or error.get("detail")
            parts = [str(value) for value in (code, message, detail) if value]
            if parts:
                details.append(" - ".join(parts))
    return "; ".join(details) or str(payload)[:1000]
