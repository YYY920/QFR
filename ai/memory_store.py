from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None  # type: ignore[assignment]


MEMORY_FILE = Path("mapping_memory.json")
SCHEMA_VERSION = 2
_THREAD_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty_store() -> Dict[str, Any]:
    return {
        "_meta": {
            "schema_version": SCHEMA_VERSION,
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
        },
        "entries": {},
    }


def _canonical_context(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not context:
        return {}
    return {
        str(key): value
        for key, value in sorted(context.items(), key=lambda item: str(item[0]))
        if value is not None
    }


def _make_key(contact: str, description: str, context: Optional[Dict[str, Any]] = None) -> str:
    payload = {
        "contact": (contact or "").strip().lower(),
        "description": (description or "").strip().lower(),
        "context": _canonical_context(context),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(canonical.encode("utf-8")).hexdigest()


def _migrate_store(payload: Any) -> tuple[Dict[str, Any], bool]:
    meta = payload.get("_meta") if isinstance(payload, dict) else None
    if (
        isinstance(payload, dict)
        and isinstance(meta, dict)
        and meta.get("schema_version") == SCHEMA_VERSION
        and isinstance(payload.get("entries"), dict)
    ):
        return payload, False

    migrated = _empty_store()
    if isinstance(payload, dict) and payload:
        # Version 1 keyed only by contact + description. Preserve it for audit,
        # but do not reuse it because account/type/taxonomy context is unknown.
        migrated["legacy_entries"] = payload
        migrated["_meta"]["migrated_from_schema"] = 1
        migrated["_meta"]["legacy_entry_count"] = len(payload)
    return migrated, bool(payload)


def _load_memory_unlocked() -> tuple[Dict[str, Any], bool]:
    path = Path(MEMORY_FILE)
    if not path.exists():
        return _empty_store(), False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty_store(), False
    return _migrate_store(payload)


def _save_memory_unlocked(mem: Dict[str, Any]) -> None:
    path = Path(MEMORY_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    mem.setdefault("_meta", {})["schema_version"] = SCHEMA_VERSION
    mem["_meta"]["updated_at"] = _utc_now()

    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(mem, handle, indent=2, ensure_ascii=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


@contextmanager
def _memory_lock() -> Iterator[None]:
    """Serialize threads and, where supported, separate mapper processes."""
    path = Path(MEMORY_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(f"{path.name}.lock")
    with _THREAD_LOCK:
        with lock_path.open("a+", encoding="utf-8") as lock_handle:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def lookup_mapping(
    contact: str,
    description: str,
    context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    with _memory_lock():
        mem, migrated = _load_memory_unlocked()
        if migrated:
            _save_memory_unlocked(mem)
        entry = mem.get("entries", {}).get(_make_key(contact, description, context))
        if not isinstance(entry, dict) or not isinstance(entry.get("mapping"), dict):
            return None
        return dict(entry["mapping"])


def store_mapping(
    contact: str,
    description: str,
    mapping: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
) -> None:
    canonical_context = _canonical_context(context)
    with _memory_lock():
        mem, _ = _load_memory_unlocked()
        entries = mem.setdefault("entries", {})
        entries[_make_key(contact, description, canonical_context)] = {
            "mapping": dict(mapping),
            "context": canonical_context,
            "created_at": _utc_now(),
        }
        _save_memory_unlocked(mem)
