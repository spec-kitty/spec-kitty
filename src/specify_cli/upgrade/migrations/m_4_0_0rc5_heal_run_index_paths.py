"""Migration: heal absolute ``run_dir`` paths in the run index to portable tokens.

Companion to the RunIndex port (mission runindex-feature-runs-port, #5390 / #5389):
the port persists ``.kittify/runtime/feature-runs.json`` ``run_dir`` values as
repo-relative tokens resolved against the invoking repo root. A project whose
index was written by an OLDER CLI still holds absolute ``run_dir`` paths — and if
that project was copied or moved, those absolute paths point at the ORIGINAL
folder, so ``spec-kitty next`` would refuse them (containment) until healed.

This migration rewrites every entry whose ``run_dir`` is absolute to the
canonical repo-relative token ``.kittify/runtime/runs/<run_id>`` (the run store is
always ``<repo>/.kittify/runtime/runs`` and the directory basename is the run id),
re-anchoring a relocated index to THIS repository. A relative token is already
portable and is left untouched, so re-running (or a fresh ``next``) converges to
zero further changes.

The leak classifier is shared with the ``doctor run-index`` sibling
(:func:`describe_leaks`) so "flagged by doctor" and "fixed by migrate" never
drift apart — mirroring the ``m_3_2_7_heal_provenance_paths`` / ``doctor
provenance`` precedent.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from runtime.next import run_index
from runtime.next.run_index import FEATURE_RUNS_FILENAME

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4_0_0rc5_heal_run_index_paths"
TARGET_VERSION = "4.0.0rc5"

_RUNS_TOKEN_PREFIX = PurePosixPath(".kittify") / "runtime" / "runs"


def _is_absolute(value: str) -> bool:
    """True for a POSIX or Windows absolute path (indexes may cross OSes)."""
    return Path(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _run_id_basename(value: str) -> str:
    """The trailing component (the run id) of an absolute ``run_dir``, cross-OS."""
    windows = PureWindowsPath(value)
    if windows.is_absolute():
        return windows.name
    return PurePosixPath(value).name


def _healed_token(value: str, project_path: Path, *, run_id: str | None) -> str:
    """The portable token an absolute ``run_dir`` should heal to.

    - An absolute path **inside** ``project_path`` (an in-place upgrade, possibly
      at a non-canonical subpath) is relativized by the port, **preserving its
      subpath** — never blindly re-anchored, so a currently-working project is not
      relocated to a nonexistent directory (pre-PR review IMPORTANT-1).
    - An absolute path **outside** ``project_path`` (a copied/moved index pointing
      at the original folder, or a foreign/cross-OS path) is re-anchored to this
      repo's canonical run store, keyed by the entry's own canonical ``run_id`` —
      the run store location (``.kittify/runtime/runs/<run_id>``) is fixed, so the
      copy/move carried the run directory to exactly that path. The ``run_dir``
      path's own trailing component is only a fallback for an entry that (legacy
      data) carries no ``run_id`` — trusting it as primary would re-anchor to the
      wrong directory whenever a foreign index's leaf diverged from its run id.
    """
    tokenized = run_index.serialize_run_dir(value, project_path)
    if _is_absolute(tokenized):
        # serialize_run_dir left an out-of-tree/foreign absolute unchanged (C2):
        # re-anchor it to this repo's run store by the entry's canonical run_id.
        anchor = run_id if isinstance(run_id, str) and run_id else _run_id_basename(value)
        return (_RUNS_TOKEN_PREFIX / anchor).as_posix()
    return tokenized


def _load_index(project_path: Path) -> dict[str, Any]:
    return run_index.read_index_file(run_index.feature_runs_path(project_path))


def _healable_entries(project_path: Path) -> list[tuple[str, str]]:
    """Return ``(key, absolute_run_dir)`` for every entry needing a heal."""
    healable: list[tuple[str, str]] = []
    for key, entry in _load_index(project_path).items():
        if not isinstance(entry, dict):
            continue
        run_dir = entry.get("run_dir")
        if isinstance(run_dir, str) and run_dir and _is_absolute(run_dir):
            healable.append((key, run_dir))
    return healable


def _planned_changes(index: dict[str, Any], project_path: Path) -> list[str]:
    """Heal every absolute ``run_dir`` entry in ``index`` in place; return the changelog.

    Shared by the dry-run preview and the real write so both compute the same
    healed values from the same entry data.
    """
    changes: list[str] = []
    for key, entry in index.items():
        if not isinstance(entry, dict):
            continue
        run_dir = entry.get("run_dir")
        if not (isinstance(run_dir, str) and run_dir and _is_absolute(run_dir)):
            continue
        new_value = _healed_token(run_dir, project_path, run_id=entry.get("run_id"))
        changes.append(f"{FEATURE_RUNS_FILENAME}[{key}].run_dir: {run_dir} -> {new_value}")
        entry["run_dir"] = new_value
    return changes


def describe_leaks(project_path: Path) -> list[str]:
    """Human-readable description of every absolute-``run_dir`` leak (read-only).

    The single source of truth the ``doctor run-index`` leak-check reads from,
    using the same classification :meth:`HealRunIndexPathsMigration.detect` uses.
    """
    return [f"{FEATURE_RUNS_FILENAME}[{key}].run_dir={run_dir!r} (absolute; not portable across copy/move)" for key, run_dir in _healable_entries(project_path)]


@MigrationRegistry.register
class HealRunIndexPathsMigration(BaseMigration):
    """Heal absolute ``run_dir`` values in the run index to portable tokens (#5390)."""

    migration_id = MIGRATION_ID
    description = (
        f"Rewrite absolute run_dir paths in .kittify/runtime/{FEATURE_RUNS_FILENAME} to "
        "portable repo-relative tokens (.kittify/runtime/runs/<run_id>), re-anchoring "
        "a copied or moved project's run index to itself."
    )
    target_version = TARGET_VERSION
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        return bool(_healable_entries(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, f"no absolute run_dir found in .kittify/runtime/{FEATURE_RUNS_FILENAME}"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        # dry-run is read-only — never take the single-locked-writer lock, never write.
        if dry_run:
            index = _load_index(project_path)
            return MigrationResult(success=True, changes_made=_planned_changes(index, project_path))

        # Real write: hold the index lock for the whole read-modify-write so a
        # `migrate`/`upgrade` racing a live `spec-kitty next` cannot clobber the
        # single locked writer invariant (#5389). Re-read under the lock.
        with run_index.index_lock(project_path):
            index = _load_index(project_path)
            changes = _planned_changes(index, project_path)
            if changes:
                run_index.write_index_file(run_index.feature_runs_path(project_path), index)
        return MigrationResult(success=True, changes_made=changes)
