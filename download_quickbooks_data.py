from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from quickbooks.client import QuickBooksClient
from quickbooks.config import load_quickbooks_settings
from quickbooks.entities import DEFAULT_ENTITIES, default_where
from quickbooks.oauth import load_token, refresh_access_token, token_is_expired
from quickbooks.reports import DEFAULT_REPORTS, build_report_params

DEFAULT_OUTPUT_DIR = Path("output/quickbooks")


def _csv_names(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Date must use YYYY-MM-DD.") from exc


def parse_args() -> argparse.Namespace:
    today = date.today()
    parser = argparse.ArgumentParser(
        description="Download raw QuickBooks Online entities and standard reports as JSON."
    )
    parser.add_argument("--from-date", type=_parse_date, default=date(today.year, 1, 1))
    parser.add_argument("--to-date", type=_parse_date, default=today)
    parser.add_argument(
        "--opening-date",
        type=_parse_date,
        help=(
            "Balance Sheet opening snapshot date. Defaults to the day before "
            "--from-date."
        ),
    )
    parser.add_argument(
        "--entities",
        type=_csv_names,
        default=list(DEFAULT_ENTITIES),
        help="Comma-separated QBO entity names.",
    )
    parser.add_argument(
        "--reports",
        type=_csv_names,
        default=list(DEFAULT_REPORTS),
        help="Comma-separated QBO report names.",
    )
    parser.add_argument("--skip-entities", action="store_true")
    parser.add_argument("--skip-reports", action="store_true")
    parser.add_argument("--accounting-method", choices=("Accrual", "Cash"), default="Accrual")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Stop on the first API error instead of recording it in manifest.json.",
    )
    args = parser.parse_args()
    if args.from_date > args.to_date:
        parser.error("--from-date must be on or before --to-date.")
    if args.opening_date is None:
        args.opening_date = args.from_date - timedelta(days=1)
    if args.opening_date != args.from_date - timedelta(days=1):
        parser.error("--opening-date must be exactly one day before --from-date.")
    if not 1 <= args.page_size <= 1000:
        parser.error("--page-size must be between 1 and 1000.")
    if args.max_pages < 1:
        parser.error("--max-pages must be at least 1.")
    return args


def _safe_filename(name: str) -> str:
    separated = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return re.sub(r"[^a-z0-9_-]", "_", separated)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _get_access(
    client_id: str,
    client_secret: str,
    configured_realm_id: str | None,
) -> tuple[str, str]:
    token = load_token()
    if not token:
        raise SystemExit("No QuickBooks token found. Run `python login_quickbooks.py` first.")
    realm_id = str(token.get("realm_id") or configured_realm_id or "")
    if not realm_id:
        raise SystemExit("No QuickBooks realm ID found. Run `python login_quickbooks.py --force`.")
    if token_is_expired(token):
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise SystemExit("QuickBooks refresh token is missing. Reconnect with --force.")
        print("Refreshing the QuickBooks access token...")
        token = refresh_access_token(client_id, client_secret, str(refresh_token), realm_id)
    access_token = token.get("access_token")
    if not access_token:
        raise SystemExit("QuickBooks access token is missing. Reconnect with --force.")
    return str(access_token), realm_id


def _company_name(payload: dict[str, Any]) -> str | None:
    company = payload.get("CompanyInfo")
    if isinstance(company, dict) and company.get("CompanyName"):
        return str(company["CompanyName"])
    return None


def _download_names(
    names: Iterable[str],
    fetch: Any,
    target_dir: Path,
    kind: str,
    strict: bool,
    manifest: dict[str, Any],
) -> None:
    for name in names:
        print(f"Downloading {kind} {name}...")
        try:
            payload = fetch(name)
            path = target_dir / f"{_safe_filename(name)}.json"
            _write_json(path, payload)
            count = len(payload) if isinstance(payload, list) else None
            manifest[kind][name] = {"file": str(path), "count": count}
        except Exception as exc:  # noqa: BLE001
            if strict:
                raise
            message = f"{type(exc).__name__}: {exc}"
            print(f"  Skipped: {message}")
            manifest["errors"].append({"kind": kind, "name": name, "error": message})


def main() -> None:
    args = parse_args()
    settings = load_quickbooks_settings()
    if not settings.client_id or not settings.client_secret:
        raise SystemExit(
            "Set QUICKBOOKS_CLIENT_ID and QUICKBOOKS_CLIENT_SECRET in your environment/.env file."
        )
    access_token, realm_id = _get_access(
        settings.client_id,
        settings.client_secret,
        settings.realm_id,
    )
    client = QuickBooksClient(
        access_token,
        realm_id,
        settings.environment,
        settings.minor_version,
    )

    output_dir = args.output_dir
    company_info = client.get_company_info()
    _write_json(output_dir / "company_info.json", company_info)
    manifest: dict[str, Any] = {
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "environment": settings.environment,
        "realm_id": realm_id,
        "company_name": _company_name(company_info),
        "from_date": args.from_date.isoformat(),
        "to_date": args.to_date.isoformat(),
        "opening_date": args.opening_date.isoformat(),
        "accounting_method": args.accounting_method,
        "entity": {},
        "report": {},
        "errors": [],
    }

    if not args.skip_entities:
        _download_names(
            args.entities,
            lambda name: client.query_all(
                name,
                where=default_where(name),
                page_size=args.page_size,
                max_pages=args.max_pages,
            ),
            output_dir / "entities",
            "entity",
            args.strict,
            manifest,
        )

    if not args.skip_reports:
        _download_names(
            args.reports,
            lambda name: client.get_report(
                name,
                build_report_params(
                    name,
                    from_date=args.from_date.isoformat(),
                    to_date=args.to_date.isoformat(),
                    accounting_method=args.accounting_method,
                ),
            ),
            output_dir / "reports",
            "report",
            args.strict,
            manifest,
        )
        if "BalanceSheet" in args.reports:
            print(
                "Downloading report OpeningBalanceSheet "
                f"({args.opening_date.isoformat()})..."
            )
            try:
                opening_payload = client.get_report(
                    "BalanceSheet",
                    build_report_params(
                        "BalanceSheet",
                        from_date=args.opening_date.isoformat(),
                        to_date=args.opening_date.isoformat(),
                        accounting_method=args.accounting_method,
                    ),
                )
                opening_path = output_dir / "reports" / "opening_balance_sheet.json"
                _write_json(opening_path, opening_payload)
                manifest["report"]["OpeningBalanceSheet"] = {
                    "file": str(opening_path),
                    "date": args.opening_date.isoformat(),
                }
            except Exception as exc:  # noqa: BLE001
                if args.strict:
                    raise
                message = f"{type(exc).__name__}: {exc}"
                print(f"  Skipped: {message}")
                manifest["errors"].append(
                    {
                        "kind": "report",
                        "name": "OpeningBalanceSheet",
                        "error": message,
                    }
                )

    _write_json(output_dir / "manifest.json", manifest)
    print(f"Done. Raw QuickBooks JSON is under {output_dir}.")
    if manifest["errors"]:
        print(
            f"Completed with {len(manifest['errors'])} skipped endpoint(s); "
            f"see {output_dir / 'manifest.json'}."
        )


if __name__ == "__main__":
    main()
