"""``uv.lock``-derived install pins for test venvs (#6666)."""

from __future__ import annotations

import tomllib
from pathlib import Path


def lock_pin_constraints(lock_path: Path) -> list[str]:
    """``name==version`` pins for every registry package ``uv.lock`` resolves to exactly one version.

    #6666: ``pip install -e`` resolves the ``pyproject.toml`` ranges and so installed the NEWEST
    allowed ``spec-kitty-events`` into the shared venv, not the locked one; subprocess tests then ran a
    different reducer than the in-process tests (seen in #6245). A package the lock forks across
    environments (several versions) is left unpinned, and the editable project itself is skipped.
    """
    if not lock_path.is_file():
        return []
    versions: dict[str, set[str]] = {}
    for package in tomllib.loads(lock_path.read_text(encoding="utf-8")).get("package", []):
        if "registry" in (package.get("source") or {}):
            versions.setdefault(str(package["name"]), set()).add(str(package["version"]))
    return sorted(f"{name}=={next(iter(found))}" for name, found in versions.items() if len(found) == 1)
