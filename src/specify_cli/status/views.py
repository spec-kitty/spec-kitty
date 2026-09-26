"""Derived view generation from the canonical status event log.

Generates output-only views (status.json, board-summary.json) from the
event log snapshot. These views are never authoritative — the event log
is the sole source of truth.

Use these functions after emitting events or materializing a snapshot
when human-readable or machine-readable output is needed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from specify_cli.mission_metadata import resolve_mission_identity

from .lifecycle import DERIVED_LIFECYCLE_FILENAME, generate_lifecycle_json
from .models import Lane, StatusSnapshot
from .reducer import materialize, reduce
from .store import EVENTS_FILENAME, read_events

BOARD_SUMMARY_FILENAME = "board-summary.json"
DERIVED_STATUS_FILENAME = "status.json"
DERIVED_PROGRESS_FILENAME = "progress.json"

# Git-operation marker files/dirs that signal an in-progress operation during
# which tracked status MUST NOT be re-materialized (FR-005 / C-RT-1, #1789/#1062).
# These names are resolved against BOTH the per-worktree gitdir and the shared
# common gitdir, because a marker may live in either depending on the operation
# and whether the caller is in a linked worktree or the primary checkout.
_GIT_OP_MARKERS: tuple[str, ...] = (
    "rebase-merge",  # interactive / merge-backend rebase in progress
    "rebase-apply",  # am / apply-backend rebase in progress
    "MERGE_HEAD",  # merge in progress (conflicted or otherwise)
    "CHERRY_PICK_HEAD",  # cherry-pick in progress
    "REVERT_HEAD",  # revert in progress (same hazard class as cherry-pick)
    "sequencer",  # multi-commit cherry-pick/revert/rebase sequence in progress
    "index.lock",  # index is being mutated by another git process
)


def generate_status_view(feature_dir: Path) -> dict[str, Any]:
    """Read the event log and return the current snapshot as a dict.

    Reads events via ``read_events(feature_dir)``, reduces to a
    ``StatusSnapshot``, and returns its dict representation.

    Returns:
        Snapshot dict suitable for JSON serialisation.
        Returns an empty snapshot dict if the event log is missing
        or contains no events.
    """
    events = read_events(feature_dir)
    snapshot = reduce(events)
    identity = resolve_mission_identity(feature_dir)
    snapshot.mission_number = (
        str(identity.mission_number)
        if identity.mission_number is not None
        else None
    )
    snapshot.mission_type = identity.mission_type
    return snapshot.to_dict()


def write_derived_views(
    feature_dir: Path,
    derived_dir: Path,
) -> None:
    """Generate and write derived views from the event log.

    Produces two files under ``derived_dir / <mission_slug>/``:

    - ``status.json`` — full StatusSnapshot serialised as JSON.
    - ``board-summary.json`` — lane counts and WP lists per lane.

    Both files are written atomically (write-to-temp then os.replace).
    The output directory is created if it does not exist.

    These views are output-only and must never be consulted as
    authoritative state.

    Args:
        feature_dir: Path to the feature directory
            (e.g. ``kitty-specs/034-feature/``).
        derived_dir: Root directory for derived artefacts.
    """
    snapshot = materialize(feature_dir)
    mission_slug = snapshot.mission_slug or feature_dir.name

    output_dir = derived_dir / mission_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write status.json
    _atomic_write_json(
        output_dir / "status.json",
        snapshot.to_dict(),
    )

    # Write board-summary.json
    board_summary = _build_board_summary(snapshot)
    _atomic_write_json(
        output_dir / BOARD_SUMMARY_FILENAME,
        board_summary,
    )


def _build_board_summary(snapshot: Any) -> dict[str, Any]:
    """Build a compact board summary from a StatusSnapshot.

    Returns a dict with:
    - ``mission_slug``: feature identifier
    - ``total_wps``: total number of work packages
    - ``summary``: lane -> count mapping (9 active/display lanes; genesis excluded)
    - ``lanes``: lane -> list of wp_ids mapping
    - ``materialized_at``: ISO timestamp of snapshot

    Only lanes with at least one WP are included in ``lanes``.
    """
    lanes: dict[str, list[str]] = {}
    for wp_id, wp_state in sorted(snapshot.work_packages.items()):
        # Defensive default matches the write side (#1775 review M4); reduce()
        # always sets "lane", so this default is effectively unreachable.
        lane = wp_state.get("lane", Lane.GENESIS)
        if lane not in lanes:
            lanes[lane] = []
        lanes[lane].append(wp_id)

    mission_number = snapshot.mission_number
    if isinstance(mission_number, str) and mission_number.isdigit():
        mission_number = int(mission_number)

    return {
        "mission_slug": snapshot.mission_slug,
        "mission_number": mission_number,
        "mission_type": snapshot.mission_type,
        "total_wps": len(snapshot.work_packages),
        "summary": snapshot.summary,
        "lanes": lanes,
        "materialized_at": snapshot.materialized_at,
    }


def _resolve_git_dirs(repo_root: Path) -> tuple[Path, ...]:
    """Resolve the gitdir(s) to scan for in-progress git-operation markers.

    Returns the per-worktree gitdir and the shared common gitdir (deduplicated).
    Handles the three layouts:

    - **Primary checkout** — ``<repo_root>/.git`` is a directory; it is both the
      per-worktree gitdir and the common gitdir.
    - **Linked worktree** — ``<repo_root>/.git`` is a *file* of the form
      ``gitdir: /path/to/.git/worktrees/<name>``; the common gitdir is the
      parent of the ``worktrees/`` directory.
    - **Missing / non-repo** — returns an empty tuple; the caller treats an
      unresolvable repository conservatively (no git op detected, materialize
      proceeds as before — C-004).

    This is filesystem-only (no subprocess) so it is safe to call on every
    daemon/dashboard read without process-spawn overhead, and cannot itself
    perturb a concurrent git operation.
    """
    dirs: list[Path] = []
    git_path = repo_root / ".git"
    if not git_path.exists():
        return tuple(dirs)

    if git_path.is_dir():
        dirs.append(git_path)
        return tuple(dirs)

    # Linked worktree: .git is a file "gitdir: <per-worktree gitdir>".
    try:
        content = git_path.read_text(encoding="utf-8").strip()
    except OSError:
        return tuple(dirs)
    if not content.startswith("gitdir:"):
        return tuple(dirs)
    worktree_gitdir = Path(content.split(":", 1)[1].strip())
    if not worktree_gitdir.exists():
        # Conservative: cannot resolve the gitdir → report nothing rather than
        # guessing. materialize_if_stale will fall through to its normal path.
        return tuple(dirs)

    dirs.append(worktree_gitdir)
    # The common gitdir is the ancestor that contains the ``worktrees`` dir:
    #   <common-gitdir>/worktrees/<name>
    for ancestor in worktree_gitdir.parents:
        if ancestor.name == "worktrees":
            common = ancestor.parent
            if common not in dirs:
                dirs.append(common)
            break
    return tuple(dirs)


def git_operation_in_progress(repo_root: Path) -> bool:
    """Return ``True`` when a git operation is in progress for ``repo_root``.

    Detects rebase (merge- or apply-backend), merge, cherry-pick, revert, and a
    held ``index.lock`` by probing the enumerated :data:`_GIT_OP_MARKERS` against
    both the per-worktree gitdir and the shared common gitdir. During any such
    operation the working tree and tracked status files are in flux, so runtime
    writers MUST NOT re-materialize tracked status (FR-005 / C-RT-1, #1789/#1062).

    The detection is **conservative**: it is purely filesystem-based, never
    spawns a subprocess, and reports ``False`` only when no marker is found and
    the repository resolves cleanly. An unresolvable repository yields ``False``
    so that legitimate materialization is never blocked by a non-repo path
    (C-004); the hazardous direction (skip-when-unsure) is covered because every
    real in-progress operation leaves at least one of these markers on disk.

    Exposed as a reusable public helper: WP11 (dashboard) consumes the same
    detection so reads and the dashboard share one source of truth (IC-12 /
    FR-014(a)).
    """
    for git_dir in _resolve_git_dirs(repo_root):
        for marker in _GIT_OP_MARKERS:
            if (git_dir / marker).exists():
                return True
    return False


def _stale_check_slug(feature_dir: Path) -> str:
    """Resolve the context-aware staleness key for ``feature_dir`` (FR-012).

    The derived-view location is keyed on the *canonical* mission slug from the
    mission's ``meta.json`` (``resolve_mission_identity``), not on the literal
    ``feature_dir.name``. This makes the staleness key invariant across CWDs:
    the primary checkout and any lane/coordination worktree all resolve the same
    mission identity, so they target the same ``.kittify/derived/<slug>/``
    directory and the same mission is never falsely reported stale from a
    different CWD (FR-012, no false re-materialize across primary/lane/coord).

    Falls back to ``feature_dir.name`` when no canonical slug is recorded (legacy
    missions without ``meta.json``), preserving prior behaviour (C-004).
    """
    identity = resolve_mission_identity(feature_dir)
    return identity.mission_slug or feature_dir.name


def materialize_if_stale(feature_dir: Path, repo_root: Path) -> StatusSnapshot:
    """Regenerate derived views when the event log is newer than the derived files.

    Checks whether ``status.json``, ``progress.json``, and ``lifecycle.json`` exist in
    ``.kittify/derived/<mission_slug>/`` and whether the event log
    (``status.events.jsonl``) has a newer mtime than either derived file.
    If stale (or derived files are missing), regenerates all derived views.

    Returns the current snapshot (whether freshly generated or previously
    materialised on disk via the event log).

    Args:
        feature_dir: Path to the feature directory
            (e.g. ``kitty-specs/034-feature/``).
        repo_root: Root of the main repository (contains ``.kittify/``).
    """
    from .progress import generate_progress_json  # local import to avoid circular

    # Context-aware staleness key (FR-012): key the derived-view location on the
    # canonical mission slug, not the literal CWD-relative dir name, so the same
    # mission is not falsely stale across primary/lane/coord CWDs.
    mission_slug = _stale_check_slug(feature_dir)
    derived_dir = repo_root / ".kittify" / "derived"
    feature_derived = derived_dir / mission_slug

    events_path = feature_dir / EVENTS_FILENAME
    status_path = feature_derived / DERIVED_STATUS_FILENAME
    progress_path = feature_derived / DERIVED_PROGRESS_FILENAME
    lifecycle_path = feature_derived / DERIVED_LIFECYCLE_FILENAME

    def _is_stale() -> bool:
        if not status_path.exists() or not progress_path.exists() or not lifecycle_path.exists():
            return True
        if not events_path.exists():
            return False
        events_mtime = events_path.stat().st_mtime
        status_mtime = status_path.stat().st_mtime
        progress_mtime = progress_path.stat().st_mtime
        lifecycle_mtime = lifecycle_path.stat().st_mtime
        return bool(
            events_mtime > status_mtime
            or events_mtime > progress_mtime
            or events_mtime > lifecycle_mtime
        )

    # Git-op guard (FR-005 / C-RT-1, #1789/#1062): never re-materialize tracked
    # status while a git operation is in progress. Defer regeneration until the
    # op clears — the snapshot returned below is still reduced read-only from the
    # event log, so callers get a correct in-memory view without clobbering the
    # on-disk derived files mid-rebase/-merge/-cherry-pick.
    if _is_stale() and not git_operation_in_progress(repo_root):
        write_derived_views(feature_dir, derived_dir)
        generate_progress_json(feature_dir, derived_dir)
        generate_lifecycle_json(feature_dir, derived_dir)

    # Return snapshot without writing (T002 covers any write needed by derived views)
    snapshot = reduce(read_events(feature_dir))
    identity = resolve_mission_identity(feature_dir)
    snapshot.mission_number = (
        str(identity.mission_number)
        if identity.mission_number is not None
        else None
    )
    snapshot.mission_type = identity.mission_type
    return snapshot


def format_post_mission_events(
    post_mission_events: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> list[str]:
    """Render post-mission lifecycle events as human-readable history lines (WP02 / T009).

    Consumes the ``post_mission_events`` list carried on the
    :class:`~specify_cli.status.lifecycle.MissionLifecycleResult` (already sorted
    ``(timestamp, event_id)`` for stable order) and produces one line per event in
    the mission lifecycle/history surface:

    * ``MissionReopened`` → ``re-opened by <actor> — <reason> (<when>)``
    * ``FollowUpRecorded`` → ``follow-up <commit <sha> | PR #<n>> by <actor> (<when>)``

    Returns an empty list when there are no post-mission events, so callers can
    skip the section entirely.
    """
    from .lifecycle_events import FOLLOW_UP_RECORDED, MISSION_REOPENED

    lines: list[str] = []
    for event in post_mission_events:
        if not isinstance(event, dict):
            continue
        event_type = event.get("event_type")
        payload = event.get("payload")
        payload = payload if isinstance(payload, dict) else {}
        if event_type == MISSION_REOPENED:
            actor = payload.get("reopened_by") or "unknown"
            reason = payload.get("reason") or ""
            when = payload.get("reopened_at") or event.get("timestamp") or ""
            suffix = f" — {reason}" if reason else ""
            lines.append(f"re-opened by {actor}{suffix} ({when})")
        elif event_type == FOLLOW_UP_RECORDED:
            actor = payload.get("recorded_by") or "unknown"
            when = payload.get("recorded_at") or event.get("timestamp") or ""
            ref = (
                f"PR #{payload.get('pr_number')}"
                if payload.get("follow_up_type") == "pr"
                else f"commit {payload.get('commit_sha')}"
            )
            lines.append(f"follow-up {ref} by {actor} ({when})")
    return lines


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write a JSON file atomically using a temp-file + os.replace."""
    json_str = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json_str, encoding="utf-8")
    os.replace(str(tmp_path), str(path))
