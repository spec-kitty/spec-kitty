"""Test oracle: the holder record a machine lock leaves in its sidecar file."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def record_on_disk(lock_path: Path) -> dict[str, Any] | None:
    """Return the JSON holder record at ``lock_path``, or ``None`` when absent or cleared."""
    try:
        raw = lock_path.read_bytes()
    except OSError:
        return None
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None
