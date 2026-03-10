"""Load JSON schemas from package data."""

from __future__ import annotations

import json
from pathlib import Path
from functools import lru_cache

_SCHEMA_DIR = Path(__file__).parent.parent / "data" / "schemas"

SCHEMA_NAMES = [
    "agent-identity",
    "negotiation-contract",
    "settlement-intent",
    "execution-receipt",
    "verity-receipt",
    "registry-query",
    "registry-response",
]


@lru_cache(maxsize=16)
def load_schema(name: str) -> dict:
    """Load a JSON schema by name (without .json extension)."""
    path = _SCHEMA_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {name} (looked at {path})")
    with open(path) as f:
        return json.load(f)


def load_all_schemas() -> dict[str, dict]:
    """Load all XAP schemas. Returns {name: schema_dict}."""
    return {name: load_schema(name) for name in SCHEMA_NAMES}
