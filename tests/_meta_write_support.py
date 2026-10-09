"""Test-only helper that seeds a ``meta.json`` in the canonical sorted-key form (no lock: fixtures are single-threaded)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_meta_canonical(meta_path: Path, meta: dict[str, Any]) -> None:
    """Persist ``meta`` as sorted-key, 2-space-indented JSON with a trailing newline."""
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
