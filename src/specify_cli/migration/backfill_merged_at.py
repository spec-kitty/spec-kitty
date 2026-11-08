"""Backfill the ``merged_at`` landing marker for Missions that landed before #4090 (#7433).

The one "has this Mission landed" signal (:func:`mission_runtime.mission_has_landed`, ADR
``2026-11-06-2``) reads the reopen-aware ``merged_at`` marker in the PRIMARY ``meta.json``.
Consolidation stamps it beside ``baseline_merge_commit`` since #4090; a Mission that landed
before that carries ``mission_number`` (assigned at landing) but no ``merged_at``. The status
read door then treats it as not landed, and a coordination-topology one, whose coordination
branch consolidation tore down, refuses with ``COORDINATION_BRANCH_DELETED`` (#7335, #7431).

``mission_number`` is deliberately not a second landed signal: a reopen keeps it. This backfill
turns it into the one signal instead, once, from git evidence:

* **Selected:** ``meta.json`` has an assigned ``mission_number``
  (:func:`~specify_cli.consolidation.mission_number.is_assigned_mission_number`), no
  ``merged_at``, and the Mission's lifecycle log holds no ``MissionReopened`` event. A reopened
  Mission is never stamped: its reopen is the newer fact.
* **Date:** the committer date of ``baseline_merge_commit`` when that commit resolves, else the
  committer date of the oldest commit that set ``mission_number`` to an assigned integer in
  ``meta.json``. With neither, the Mission is reported unresolved and left alone.
* **Write:** ``merged_at`` only, as an aware-UTC ISO-8601 string (the form
  :func:`kernel.clock.now_utc_iso` produces), through the canonical meta writer
  :func:`~specify_cli.mission_metadata.locked_update_meta`. Nothing is committed here; the
  upgrade auto-commit or the operator owns that.

Idempotent: a stamped Mission has ``merged_at`` and is no longer selected, so a second run
writes nothing.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from kernel.clock import from_epoch
from kernel.git import GitCommandError, run_git

logger = logging.getLogger(__name__)

__all__ = [
    "MergedAtBackfillAction",
    "MergedAtBackfillResult",
    "SOURCE_BASELINE_MERGE_COMMIT",
    "SOURCE_MISSION_NUMBER_COMMIT",
    "backfill_merged_at",
    "has_merged_at_to_backfill",
]

MergedAtBackfillAction = Literal["stamped", "reopened", "unresolved", "error"]

#: Where a backfilled ``merged_at`` date came from (reported, never written to ``meta.json``).
SOURCE_BASELINE_MERGE_COMMIT = "baseline_merge_commit"
SOURCE_MISSION_NUMBER_COMMIT = "mission_number commit"

_META_JSON = "meta.json"
_MERGED_AT = "merged_at"

#: ``git log -G`` pattern for a ``meta.json`` line that assigns an integer ``mission_number``
#: (``>= 1``, the only assigned form). Basic and extended regex read it the same way.
_ASSIGNED_MISSION_NUMBER_LINE = '"mission_number": *[1-9]'

#: Seconds before one git probe is abandoned (a probe that cannot answer is "no evidence").
_GIT_TIMEOUT = 60.0


@dataclass(frozen=True)
class MergedAtBackfillResult:
    """The outcome for one selected-or-refused Mission."""

    slug: str
    action: MergedAtBackfillAction
    merged_at: str | None = None
    source: str | None = None
    reason: str = ""


def _mission_dirs(repo_root: Path) -> list[Path]:
    kitty_specs = repo_root / "kitty-specs"
    if not kitty_specs.is_dir():
        return []
    return sorted(entry for entry in kitty_specs.iterdir() if entry.is_dir() and (entry / _META_JSON).is_file())


def _needs_marker(meta: dict[str, Any]) -> bool:
    from specify_cli.consolidation.mission_number import is_assigned_mission_number

    return is_assigned_mission_number(meta.get("mission_number")) and not str(meta.get(_MERGED_AT) or "").strip()


def _has_reopen(feature_dir: Path) -> bool:
    """True when the Mission's lifecycle log records any ``MissionReopened`` event."""
    from specify_cli.status import MISSION_REOPENED, mission_event_log_path, read_lifecycle_events

    log_path = mission_event_log_path(feature_dir)
    if not log_path.is_file():
        return False
    return any(event.get("event_type") == MISSION_REOPENED for event in read_lifecycle_events(log_path))


def _epoch_to_iso(raw: bytes) -> str | None:
    """The aware-UTC ISO-8601 form of a ``%ct`` epoch line, or ``None`` when it is not one."""
    text = raw.decode("ascii", "replace").strip()
    if not text.isdigit():
        return None
    return from_epoch(float(text)).isoformat()


def _is_commit_id(value: str) -> bool:
    """A full or abbreviated hex object id (never an option or a revision expression)."""
    return 4 <= len(value) <= 64 and all(char in "0123456789abcdefABCDEF" for char in value)


def _baseline_commit_date(repo_root: Path, baseline: str) -> str | None:
    if not _is_commit_id(baseline):
        return None
    try:
        result = run_git(repo_root, "show", "-s", "--format=%ct", f"{baseline}^{{commit}}", "--", check=False, timeout=_GIT_TIMEOUT)
    except GitCommandError:
        return None
    if result.returncode != 0:
        return None
    return _epoch_to_iso(result.stdout)


def _mission_number_commit_date(repo_root: Path, feature_dir: Path) -> str | None:
    """Committer date of the oldest commit that assigned ``mission_number`` in this ``meta.json``."""
    try:
        meta_rel = (feature_dir / _META_JSON).relative_to(repo_root).as_posix()
    except ValueError:
        return None
    try:
        result = run_git(repo_root, "log", "--format=%ct", f"-G{_ASSIGNED_MISSION_NUMBER_LINE}", "--", meta_rel, check=False, timeout=_GIT_TIMEOUT)
    except GitCommandError:
        return None
    lines = result.stdout.split() if result.returncode == 0 else []
    # ``git log`` lists newest first; the oldest match is the commit that first assigned it.
    return _epoch_to_iso(lines[-1]) if lines else None


def _landing_date(repo_root: Path, feature_dir: Path, meta: dict[str, Any]) -> tuple[str, str] | None:
    """``(merged_at, source)`` from the best git evidence, or ``None`` when there is none."""
    baseline_date = _baseline_commit_date(repo_root, str(meta.get("baseline_merge_commit") or "").strip())
    if baseline_date is not None:
        return baseline_date, SOURCE_BASELINE_MERGE_COMMIT
    number_date = _mission_number_commit_date(repo_root, feature_dir)
    if number_date is not None:
        return number_date, SOURCE_MISSION_NUMBER_COMMIT
    return None


def _stamp(feature_dir: Path, repo_root: Path, merged_at: str) -> bool:
    """Write ``merged_at`` under the Mission write lock unless a writer got there first."""
    from specify_cli.mission_metadata import locked_update_meta

    wrote = False

    def mutate(fresh: dict[str, Any]) -> bool:
        nonlocal wrote
        if not _needs_marker(fresh):
            return False
        fresh[_MERGED_AT] = merged_at
        wrote = True
        return True

    locked_update_meta(feature_dir, mutate, validate=False, repo_root=repo_root, fallback_to_dir_name=True)
    return wrote


def _backfill_one(repo_root: Path, feature_dir: Path, *, dry_run: bool) -> MergedAtBackfillResult | None:
    """The result for one Mission dir, or ``None`` when it is not selected."""
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    slug = feature_dir.name
    try:
        meta = load_meta_fail_closed(feature_dir) or {}
    except MissionMetaReadError as exc:
        return MergedAtBackfillResult(slug, "error", reason=f"meta.json is unreadable: {exc}")
    if not _needs_marker(meta):
        return None
    if _has_reopen(feature_dir):
        return MergedAtBackfillResult(slug, "reopened", reason="a MissionReopened event is recorded; the Mission has not landed")
    landing = _landing_date(repo_root, feature_dir, meta)
    if landing is None:
        return MergedAtBackfillResult(
            slug,
            "unresolved",
            reason="no git evidence of the landing date (baseline_merge_commit does not resolve, and no commit assigned mission_number)",
        )
    merged_at, source = landing
    if not dry_run and not _stamp(feature_dir, repo_root, merged_at):
        return None
    return MergedAtBackfillResult(slug, "stamped", merged_at=merged_at, source=source)


def _iter_results(repo_root: Path, *, dry_run: bool) -> Iterator[MergedAtBackfillResult]:
    for feature_dir in _mission_dirs(repo_root):
        result = _backfill_one(repo_root, feature_dir, dry_run=dry_run)
        if result is not None:
            yield result


def has_merged_at_to_backfill(repo_root: Path) -> bool:
    """True when at least one Mission would be stamped (stops at the first; writes nothing)."""
    return any(result.action == "stamped" for result in _iter_results(repo_root, dry_run=True))


def backfill_merged_at(repo_root: Path, *, dry_run: bool = False) -> list[MergedAtBackfillResult]:
    """Stamp ``merged_at`` on every selected pre-#4090 Mission under ``kitty-specs/``.

    Returns one result per Mission that needs the marker (stamped, reopened, unresolved) or
    whose ``meta.json`` cannot be read; Missions that already carry ``merged_at`` or never
    landed are not listed. With *dry_run* nothing is written and ``stamped`` means "would be".
    """
    return list(_iter_results(repo_root, dry_run=dry_run))
