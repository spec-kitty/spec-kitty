"""Private provenance and status-replay helpers for the tasks handoff guard."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import cast

from specify_cli.core.constants import KITTY_SPECS_DIR

logger = logging.getLogger(__name__)


def _fallback_planning_pin_is_trusted(
    worktree_path: Path,
    planning_tip: str,
    recorded_pin: str,
    workspace_base_commit: str,
    *,
    merge_base: Callable[[Path, str, str], str | None],
    is_post_fork_ancestor: Callable[[Path, str, str], bool],
) -> bool:
    """Trust a recovered claim pin at the immutable fork or proven post-fork."""
    if recorded_pin == workspace_base_commit:
        # SINGLE_BRANCH and freshly claimed workspaces can fork directly from
        # the planning tip. The immutable fork is then itself the claim-time
        # planning snapshot, not a post-fork lane commit.
        return merge_base(worktree_path, planning_tip, recorded_pin) == recorded_pin and merge_base(worktree_path, "HEAD", recorded_pin) == recorded_pin
    return is_post_fork_ancestor(worktree_path, recorded_pin, workspace_base_commit)


def _unique_shared_snapshot(worktree_path: Path, left: str, right: str) -> str | None:
    """Return a shared commit only when Git reports one best merge base."""
    from specify_cli.cli.commands.agent import tasks as _tasks

    try:
        result = _tasks.subprocess.run(
            ["git", "merge-base", "--all", left, right],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
    except (OSError, _tasks.subprocess.TimeoutExpired):
        return None
    snapshots = tuple(line.strip() for line in (result.stdout or "").splitlines() if line.strip())
    return snapshots[0] if result.returncode == 0 and len(snapshots) == 1 else None


def _committed_blob(worktree_path: Path, ref: str, path: str) -> bytes | None:
    from specify_cli.cli.commands.agent import tasks as _tasks

    try:
        result = _tasks.subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=str(worktree_path),
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, _tasks.subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _status_snapshot_matches(
    worktree_path: Path,
    mission_slug: str,
    commit: str,
    planning_snapshot: str,
    replay_coordination_snapshot: str,
) -> bool:
    if not mission_slug or mission_slug in {".", ".."} or Path(mission_slug).name != mission_slug:
        return False
    mission_dir = f"{KITTY_SPECS_DIR}/{mission_slug}"
    events_path = f"{mission_dir}/status.events.jsonl"
    status_path = f"{mission_dir}/status.json"
    meta_path = f"{mission_dir}/meta.json"
    coordination_events = _committed_blob(worktree_path, replay_coordination_snapshot, events_path)
    result_events = _committed_blob(worktree_path, commit, events_path)
    coordination_status = _committed_blob(worktree_path, replay_coordination_snapshot, status_path)
    result_status = _committed_blob(worktree_path, commit, status_path)
    planning_meta = _committed_blob(worktree_path, planning_snapshot, meta_path)
    result_meta = _committed_blob(worktree_path, commit, meta_path)
    if any(
        (
            coordination_events is None,
            result_events != coordination_events,
            coordination_status is None,
            result_status is None,
            planning_meta is None,
            result_meta != planning_meta,
        )
    ):
        return False

    from specify_cli.status import materialize_snapshot_from_text, materialize_to_json

    try:
        with TemporaryDirectory(prefix="spec-kitty-handoff-status-") as temp_dir:
            replay_dir = Path(temp_dir)
            (replay_dir / "status.json").write_bytes(cast(bytes, coordination_status))
            (replay_dir / "meta.json").write_bytes(cast(bytes, planning_meta))
            expected = cast(
                str,
                materialize_to_json(
                    materialize_snapshot_from_text(
                        replay_dir,
                        cast(bytes, coordination_events).decode("utf-8"),
                        mission_slug=mission_slug,
                    )
                ),
            ).encode("utf-8")
    except Exception as exc:  # noqa: BLE001 -- unverifiable replay must not authorize handoff
        logger.debug("Could not replay canonical handoff status snapshot: %s", exc)
        return False
    return result_status == expected


def _canonical_status_replay(
    worktree_path: Path,
    fork_commit: str,
    commit: str,
    parents: tuple[str, ...],
    mission_slug: str | None,
    planning_pin: str | None,
    merged_planning_tip: str | None,
    coordination_snapshot: str | None,
) -> bool:
    if planning_pin is None or coordination_snapshot is None or mission_slug is None:
        return False
    from specify_cli.cli.commands.agent import tasks_shared as _shared

    planning_history_tip = merged_planning_tip or planning_pin
    planning_snapshot = _unique_shared_snapshot(worktree_path, commit, planning_history_tip)
    replay_coordination_snapshot = _unique_shared_snapshot(worktree_path, commit, coordination_snapshot)
    if planning_snapshot is None or replay_coordination_snapshot is None:
        return False
    if not _shared._commit_is_post_fork_lane_ancestor(worktree_path, replay_coordination_snapshot, fork_commit):
        return False
    if _shared._commit_in_trusted_snapshots(worktree_path, replay_coordination_snapshot, parents) is not True:
        return False
    return _status_snapshot_matches(worktree_path, mission_slug, commit, planning_snapshot, replay_coordination_snapshot)


def _canonical_final_head_status_replay(
    worktree_path: Path,
    fork_commit: str,
    mission_slug: str | None,
    planning_pin: str | None,
    planning_ref: str | None,
    merged_planning_tip: str | None,
    coordination_snapshot: str | None,
    coordination_ref: str | None,
    capture_ref_tip: Callable[[Path, str], str | None],
) -> bool:
    if any(value is None for value in (mission_slug, planning_pin, planning_ref)):
        return False
    planning_tip = capture_ref_tip(worktree_path, cast(str, planning_ref))
    coordination_tip = planning_tip if coordination_ref is None else capture_ref_tip(worktree_path, coordination_ref)
    if planning_tip is None or coordination_tip is None:
        return False
    planning_snapshot = _unique_shared_snapshot(worktree_path, "HEAD", planning_tip)
    replay_coordination_snapshot = _unique_shared_snapshot(worktree_path, "HEAD", coordination_tip)
    if planning_snapshot is None or replay_coordination_snapshot is None:
        return False
    expected_planning_snapshot = merged_planning_tip or cast(str, planning_pin)
    # Without a post-fork planning refresh, the immutable fork can carry the
    # latest shared planning metadata used to materialize its inherited status.
    if merged_planning_tip is None and planning_snapshot == fork_commit:
        expected_planning_snapshot = fork_commit
    expected_coordination_snapshot = coordination_snapshot or (expected_planning_snapshot if coordination_ref is None else fork_commit)
    if planning_snapshot != expected_planning_snapshot or replay_coordination_snapshot != expected_coordination_snapshot:
        return False
    return _status_snapshot_matches(
        worktree_path,
        cast(str, mission_slug),
        "HEAD",
        planning_snapshot,
        replay_coordination_snapshot,
    )


def _lane_history_commits(worktree_path: Path, fork_commit: str) -> tuple[tuple[str, ...], ...] | None:
    from specify_cli.cli.commands.agent import tasks as _tasks

    try:
        result = _tasks.subprocess.run(
            ["git", "rev-list", "--parents", f"{fork_commit}..HEAD"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=30,
        )
    except (OSError, _tasks.subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    commits = tuple(tuple(line.split()) for line in result.stdout.splitlines() if line.strip())
    return None if any(len(commit) < 2 for commit in commits) else commits


def _lane_commit_handoff_paths(
    worktree_path: Path,
    fork_commit: str,
    commit: str,
    parents: tuple[str, ...],
    trusted_snapshots: tuple[str, ...],
    status_snapshot_path: str | None,
    mission_slug: str | None,
    planning_pin: str | None,
    merged_planning_tip: str | None,
    coordination_snapshot: str | None,
) -> tuple[tuple[str, ...], bool] | None:
    from specify_cli.cli.commands.agent import tasks_shared as _shared

    inherited = _shared._commit_in_trusted_snapshots(worktree_path, commit, trusted_snapshots)
    if inherited is None:
        return None
    if inherited:
        return (), False
    changed_paths = _shared._lane_commit_authored_kitty_specs_paths(worktree_path, commit, parents)
    if changed_paths is None:
        return None
    status_is_derived = (
        len(parents) == 2
        and status_snapshot_path is not None
        and status_snapshot_path in changed_paths
        and _canonical_status_replay(
            worktree_path,
            fork_commit,
            commit,
            parents,
            mission_slug,
            planning_pin,
            merged_planning_tip,
            coordination_snapshot,
        )
    )
    if status_is_derived:
        return tuple(path for path in changed_paths if path != status_snapshot_path), True
    return changed_paths, False
