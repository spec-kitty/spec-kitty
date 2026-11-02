"""Address the existing collection-policy cache by its exact input content.

The workflow may restore this cache ONLY in the trusted default-branch cache
namespace, never on PR events. The HMAC authority key is stored alongside the
result, so its purpose is corruption/local-reuse checking, NOT authentication
against a malicious cache writer. Actions' ref scoping supplies that boundary.
The scanner still reads all sources, validates its digest/HMAC, and rescans on
an invalid result. There is no skip-policy flag or PR verdict artifact.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys

from tests._support.wall_clock_assertions import (
    _wall_clock_scan_digest,
    find_test_python_paths,
)


def cache_key(root: Path, *, runtime: str | None = None) -> str:
    """Return a runtime-specific key covering all scanner sources and settings."""
    paths = find_test_python_paths(root / "tests")
    if not paths:
        raise ValueError("refusing a policy-cache key for an empty test tree")
    sources = {path: path.read_text(encoding="utf-8") for path in paths}
    config = tuple(root / name for name in ("pytest.ini", "pyproject.toml", "uv.lock"))
    for path in config:
        if not path.is_file():
            raise ValueError(f"missing policy-cache input: {path}")
    content = _wall_clock_scan_digest(paths, sources, config)
    interpreter = runtime if runtime is not None else f"{sys.platform}:{sys.version}"
    digest = hashlib.sha256(f"{interpreter}\0{content}".encode()).hexdigest()
    return f"wall-clock-policy-v1-{digest}"


if __name__ == "__main__":
    print(cache_key(Path.cwd()))
