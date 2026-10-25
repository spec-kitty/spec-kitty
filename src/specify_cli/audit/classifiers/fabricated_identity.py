"""``FABRICATED_IDENTITY_SUSPECTED``: a committed ``meta.json`` that a baseline writer fabricated (#6668).

A folder is suspected only when all three signals hold (FR-010):

1. ``meta.json`` is git-tracked and the folder holds nothing outside the allow-list
   ``{meta.json, status.json, status.events.jsonl, decisions/**, *.lock}``.
2. ``meta.json``'s slug-derived fields equal :func:`baseline_slug_fields` of the slug.
3. The slug ends in a mid8 that differs from ``mission_id[:8]``.

Read-only: nothing is written or deleted (FR-011, C-001).
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from mission_runtime.identity import mid8_from_slug
from specify_cli.mission_metadata import baseline_slug_fields, load_meta

from ..models import FABRICATED_IDENTITY_SUSPECTED, MissionFinding, Severity

SIGNAL_TRACKED_ALLOWLIST = "tracked meta.json in an allow-listed folder"
SIGNAL_BASELINE_FIELDS = "slug-derived fields equal the baseline"
SIGNAL_MID8_MISMATCH = "slug mid8 differs from mission_id"

_META = "meta.json"
_ALLOWED_NAMES = frozenset({_META, "status.json", "status.events.jsonl"})
_ALLOWED_DIR = "decisions"
_ALLOWED_GLOB = "*.lock"
_NUMBER_KEY = "mission_number"

_REMEDY = "remove this folder's meta.json and status.json in a commit"


def _allowed(relative: str) -> bool:
    """Whether a folder-relative POSIX path is on the allow-list."""
    parts = relative.split("/")
    if parts[0] == _ALLOWED_DIR and len(parts) > 1:
        return True
    return len(parts) == 1 and (parts[0] in _ALLOWED_NAMES or fnmatchcase(parts[0], _ALLOWED_GLOB))


def _signal_tracked_allowlist(folder: Path, repo_root: Path, tracked: frozenset[str] | None) -> bool:
    if tracked is None:
        return False
    try:
        prefix = folder.resolve().relative_to(repo_root.resolve()).as_posix() + "/"
    except (OSError, ValueError):
        return False
    if prefix + _META not in tracked:
        return False
    on_disk = (p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())
    in_git = (t.removeprefix(prefix) for t in tracked if t.startswith(prefix))
    return all(_allowed(rel) for rel in (*on_disk, *in_git))


def _is_blank(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _number_matches(value: object, expected: str) -> bool:
    if not expected:
        return _is_blank(value)
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value == int(expected)
    return isinstance(value, str) and value.strip() == expected


def _signal_baseline_fields(slug: str, meta: dict[str, Any]) -> bool:
    for key, expected in baseline_slug_fields(slug).items():
        value = meta.get(key)
        matches = _number_matches(value, expected) if key == _NUMBER_KEY else value == expected
        if not matches:
            return False
    return True


def _signal_mid8_mismatch(slug: str, meta: dict[str, Any]) -> bool:
    mid8 = mid8_from_slug(slug)
    mission_id = meta.get("mission_id")
    return bool(mid8) and isinstance(mission_id, str) and bool(mission_id) and mission_id[:8] != mid8


def fabricated_identity_signals(
    folder: Path,
    *,
    repo_root: Path,
    tracked: frozenset[str] | None,
    meta: dict[str, Any] | None,
) -> tuple[str, ...] | None:
    """The matched signal names when all three signals hold, else ``None``."""
    if not meta or tracked is None:
        return None
    if not _signal_tracked_allowlist(folder, repo_root, tracked):
        return None
    if not _signal_baseline_fields(folder.name, meta):
        return None
    if not _signal_mid8_mismatch(folder.name, meta):
        return None
    return (SIGNAL_TRACKED_ALLOWLIST, SIGNAL_BASELINE_FIELDS, SIGNAL_MID8_MISMATCH)


def fabricated_identity_finding(folder: Path, *, repo_root: Path, tracked: frozenset[str] | None) -> list[MissionFinding]:
    """Zero or one WARNING finding for *folder*; never writes."""
    meta = load_meta(folder, on_malformed="none")
    signals = fabricated_identity_signals(folder, repo_root=repo_root, tracked=tracked, meta=meta)
    if signals is None:
        return []
    detail = f"signals matched: {'; '.join(signals)}. To fix: {_REMEDY}"
    return [MissionFinding(code=FABRICATED_IDENTITY_SUSPECTED, severity=Severity.WARNING, artifact_path=_META, detail=detail)]
