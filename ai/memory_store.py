import json
import os
from hashlib import sha256
from typing import Any, Dict, Optional


MEMORY_FILE = "mapping_memory.json"


def _load_memory() -> Dict[str, Any]:
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_memory(mem: Dict[str, Any]) -> None:
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mem, f, indent=2)


def _make_key(contact: str, description: str) -> str:
    base = f"{contact.strip().lower()}|{description.strip().lower()}"
    return sha256(base.encode("utf-8")).hexdigest()


def lookup_mapping(contact: str, description: str) -> Optional[Dict[str, Any]]:
    mem = _load_memory()
    key = _make_key(contact, description)
    return mem.get(key)


def store_mapping(contact: str, description: str, mapping: Dict[str, Any]) -> None:
    mem = _load_memory()
    key = _make_key(contact, description)
    mem[key] = mapping
    _save_memory(mem)

