"""Helpers for feature metadata repair during upgrades.

``load_feature_meta`` and ``write_feature_meta`` are thin compatibility
wrappers that delegate to the canonical single-writer module
:mod:`specify_cli.feature_metadata`.  All other functions in this module
(``infer_*``, ``build_baseline_feature_meta``, private helpers) are
upgrade-specific logic and remain implemented here.
"""

from __future__ import annotations

from kernel._safe_re import re
from kernel.clock import datetime, from_epoch, Clock, DEFAULT_CLOCK
from pathlib import Path
from typing import Any

from specify_cli.core.git_ops import resolve_primary_branch
from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed
from specify_cli.mission_metadata import write_meta
from specify_cli.status.mission_write import mission_write_lock

_BRANCH_PATTERNS = (
    re.compile(r"(?im)^\*\*target branch\*\*:\s*`?([^\n`]+)`?\s*$"),
    re.compile(r"(?im)^\*\*base branch\*\*:\s*`?([^\n`]+)`?\s*$"),
    re.compile(r"(?im)^target repo branch:\s*`?([^\n`]+)`?\s*$"),
    re.compile(r"(?im)^branch:\s*`?([^\n`]+)`?\s*$"),
    re.compile(r"(?i)must be done on .*?`([^`]+)` branch"),
    re.compile(r"(?i)all work packages branch from and merge back to [`“]?([^`”\n]+)[`”]?"),
    re.compile(r"(?i)merge back to [`“]?([^`”\n]+)[`”]?"),
    re.compile(r"(?i)repository[^\n]*branch [`(]?([A-Za-z0-9._/-]+)"),
)


def load_feature_meta(feature_dir: Path) -> dict[str, Any] | None:
    """Load ``meta.json``.  Delegates to the ONE fail-closed reader.

    Kept for backward compatibility with migration code.
    Routed through :func:`specify_cli.core.paths.load_meta_fail_closed`
    (FR-007 / #3162): a corrupt or non-object ``meta.json`` raises the typed
    :class:`MissionMetaReadError` instead of a raw ``ValueError``.  This
    wrapper converts that typed read failure to ``None`` so callers that
    treat missing/unreadable meta as "needs repair" continue to work
    (frozen migrations catch ``json.JSONDecodeError`` and never saw the
    raw ``ValueError`` either).
    """
    try:
        return load_meta_fail_closed(feature_dir)
    except MissionMetaReadError:
        return None


def write_feature_meta(feature_dir: Path, meta: dict[str, Any]) -> None:
    """Write ``meta.json``.  Delegates to :func:`feature_metadata.write_meta`.

    Kept for backward compatibility with migration code.
    Note: ``write_meta()`` adds ``sort_keys=True`` which the original
    did not have.  This is a deliberate format improvement.

    Validation is disabled (``validate=False``) to match the original
    behaviour, which did not enforce required-field checks.

    The replace runs under the Mission write lock, so it is serialized with every
    other ``meta.json`` writer of the Mission.
    """
    with mission_write_lock(feature_dir, fallback_to_dir_name=True):
        write_meta(feature_dir, meta, validate=False)


def infer_target_branch(
    feature_dir: Path,
    repo_root: Path,
    *,
    fallback: str | None = None,
) -> str:
    """Infer ``target_branch`` from explicit feature docs or repo context."""
    fallback_branch = fallback or resolve_primary_branch(repo_root)
    candidates: list[str] = []

    for name in ("spec.md", "plan.md", "tasks.md", "quickstart.md"):
        doc = feature_dir / name
        if not doc.exists():
            continue
        content = doc.read_text(encoding="utf-8", errors="ignore")
        for pattern in _BRANCH_PATTERNS:
            for raw in pattern.findall(content):
                candidate = _normalize_branch_candidate(raw)
                if candidate and candidate not in candidates:
                    candidates.append(candidate)

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1 and fallback_branch in candidates:
        return fallback_branch
    return fallback_branch


def infer_mission(
    feature_dir: Path,
    *,
    existing_meta: dict[str, Any] | None = None,
) -> str:
    """Infer a feature mission when ``meta.json`` is missing."""
    if existing_meta:
        mission = str(existing_meta.get("mission_type", "")).strip()
        if mission:
            return mission

    if (feature_dir / "research").exists():
        return "research"
    return "software-dev"


def infer_created_at(
    feature_dir: Path,
    *,
    now: datetime | None = None,
    clock: Clock = DEFAULT_CLOCK,
) -> str:
    """Infer a stable ``created_at`` timestamp from the earliest file mtime.

    ``clock``: injectable :class:`kernel.clock.Clock` (kernel-clock-single-door
    FR-009); defaults to :data:`kernel.clock.DEFAULT_CLOCK`. Used only as the
    no-files fallback, and only when ``now`` (an explicit value) is omitted.
    """
    timestamps = [path.stat().st_mtime for path in feature_dir.rglob("*") if path.is_file()]
    if feature_dir.exists():
        timestamps.append(feature_dir.stat().st_mtime)

    if timestamps:
        created_at = from_epoch(min(timestamps))
    else:
        created_at = now if now is not None else clock.now()
    return created_at.isoformat()


def build_baseline_feature_meta(
    feature_dir: Path,
    repo_root: Path,
    *,
    existing_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the minimum viable ``meta.json`` payload for a feature."""
    feature_slug = feature_dir.name
    feature_number, _, slug_tail = feature_slug.partition("-")
    meta = dict(existing_meta or {})

    _set_if_blank(
        meta,
        "mission_number",
        feature_number if feature_number.isdigit() else "",
    )
    _set_if_blank(meta, "slug", feature_slug)
    _set_if_blank(meta, "mission_slug", feature_slug)
    _set_if_blank(
        meta,
        "friendly_name",
        slug_tail.replace("-", " ").strip() or feature_slug,
    )
    _set_if_blank(meta, "mission_type", infer_mission(feature_dir, existing_meta=meta))
    _set_if_blank(
        meta,
        "target_branch",
        infer_target_branch(feature_dir, repo_root),
    )
    _set_if_blank(meta, "created_at", infer_created_at(feature_dir))
    return meta


def _normalize_branch_candidate(value: str) -> str | None:
    """Normalize a branch candidate extracted from feature docs."""
    cleaned = value.strip()
    if not cleaned:
        return None
    if " or " in cleaned.lower():
        return None
    cleaned = cleaned.strip("`'\"*[]() ")
    match = re.search(r"[A-Za-z0-9._/-]+", cleaned)
    if match is None:
        return None
    result: str = match.group(0)
    return result


def _set_if_blank(meta: dict[str, Any], key: str, value: Any) -> None:
    """Populate a metadata field when it is missing or blank."""
    current = meta.get(key)
    if current is None:
        meta[key] = value
        return

    if isinstance(current, str) and not current.strip():
        meta[key] = value
