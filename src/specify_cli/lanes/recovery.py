"""Implementation crash recovery for lane worktrees.

Detects post-crash state by scanning for orphaned branches, workspace
contexts, and status events that are out of sync. Provides recovery
functions to reconcile worktrees, contexts, and status.

Recovery is conservative: it never advances WP status past in_progress.
All recovery transitions use actor="recovery" for auditability.
"""

from __future__ import annotations

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.mission_metadata import load_meta
from specify_cli.missions._read_path_resolver import resolve_feature_dir_for_mission
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from kernel.clock import now_utc_iso
from specify_cli.lanes.branch_naming import (
    BranchIdentityUnresolved,
    InvalidMissionIdentity,
    mission_branch_name_required,
    parse_lane_id_from_branch,
)
from specify_cli.lanes.worktree_allocator import predict_lane_worktree
from specify_cli.status import Lane
from specify_cli.workspace.context import (
    WorkspaceContext,
    list_contexts,
    save_context,
)

logger = logging.getLogger(__name__)


RECOVERY_ACTOR = "recovery"

# Status lanes that recovery can advance through (never past in_progress)
_RECOVERY_CEILING = Lane.IN_PROGRESS


def _get_recovery_transitions(current_lane: Lane) -> list[Lane]:
    """Return the ordered list of Lane transitions recovery may emit from *current_lane*.

    Recovery is conservative: it never advances a WP past IN_PROGRESS.
    Uses ``validate_transition()`` from the canonical status module so that
    the transition matrix is the single source of truth.

    The progression recovery may emit is: planned -> claimed -> in_progress.
    Starting from *current_lane*, only transitions that are (a) allowed by the
    canonical matrix and (b) at or below the ceiling (IN_PROGRESS) are included.

    Guard conditions (actor, workspace_context, etc.) are not checked here
    because the actual transactional status emit in ``reconcile_status``
    uses ``RECOVERY_ACTOR`` and handles guard failures by catching exceptions.
    This function only validates structural matrix membership.

    Returns an empty list when no recovery transition is possible.
    """
    from specify_cli.status import validate_transition, GuardContext  # noqa: PLC0415

    # Ordered progression that recovery may advance through, capped at ceiling
    _PROGRESSION = [Lane.PLANNED, Lane.CLAIMED, Lane.IN_PROGRESS]
    try:
        ceiling_index = _PROGRESSION.index(_RECOVERY_CEILING)
        start_index = _PROGRESSION.index(current_lane)
    except ValueError:
        # current_lane or ceiling not in the recovery progression
        return []

    result: list[Lane] = []
    from_lane: Lane = current_lane
    for target in _PROGRESSION[start_index + 1: ceiling_index + 1]:
        # Pass recovery context to satisfy actor/workspace guards.
        # Recovery is always authoritative and always runs in a worktree.
        ok, _err = validate_transition(
            from_lane.value,
            target.value,
            GuardContext(actor=RECOVERY_ACTOR, workspace_context="recovery"),
        )
        if ok:
            result.append(target)
            from_lane = target
        else:
            break
    return result


@dataclass
class RecoveryState:
    """Post-crash state for a single WP/lane combination."""

    wp_id: str
    lane_id: str
    branch_name: str
    branch_exists: bool
    worktree_exists: bool
    context_exists: bool
    status_lane: str  # current lane from event log
    has_commits: bool  # commits beyond base
    recovery_action: str  # "recreate_worktree" | "recreate_context" | "emit_transitions" | "no_action"
    # When consult_status_events=True and dep branches are merged-and-deleted,
    # this field records how the WP was resolved (e.g. "merged_and_deleted")
    resolution_note: str = ""


@dataclass
class RecoveryReport:
    """Summary of recovery operations performed."""

    recovered_wps: list[str]
    worktrees_recreated: int
    contexts_recreated: int
    transitions_emitted: int
    errors: list[str]
    # WPs whose dependency branches were merged-and-deleted but are ready to
    # start from the target branch tip (populated by scan_recovery_state when
    # consult_status_events=True).
    ready_to_start_from_target: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "recovered_wps": self.recovered_wps,
            "worktrees_recreated": self.worktrees_recreated,
            "contexts_recreated": self.contexts_recreated,
            "transitions_emitted": self.transitions_emitted,
            "errors": self.errors,
            "ready_to_start_from_target": self.ready_to_start_from_target,
        }


def _list_mission_branches(repo_root: Path, mission_slug: str) -> list[str]:
    """List all local branches matching kitty/mission-{slug}* pattern."""
    pattern = f"kitty/mission-{mission_slug}*"
    result = subprocess.run(
        ["git", "branch", "--list", pattern, "--format=%(refname:short)"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]


def _branch_has_commits_beyond(
    repo_root: Path, branch: str, base_branch: str,
) -> bool:
    """Check if a branch has commits beyond a base branch."""
    result = subprocess.run(
        ["git", "log", "--oneline", "-1", "--end-of-options", f"{base_branch}..{branch}"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def _worktree_exists_for_branch(repo_root: Path, branch: str) -> Path | None:
    """Check if a git worktree exists for a given branch. Returns path if found."""
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None

    current_path: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = line[len("worktree "):]
        elif line.startswith("branch refs/heads/"):
            wt_branch = line[len("branch refs/heads/"):]
            if wt_branch == branch and current_path:
                return Path(current_path)
    return None


def _get_wp_lane_from_events(feature_dir: Path, wp_id: str) -> str:
    """Get the current lane for a WP from the status event log."""
    try:
        from specify_cli.status import reduce, read_events  # noqa: PLC0415

        events = read_events(feature_dir)
        if events:
            snapshot = reduce(events)
            state = snapshot.work_packages.get(wp_id)
            if state:
                return str(Lane(state.get("lane", Lane.PLANNED)).value)
    except Exception:
        logger.debug("Could not read status events for %s in %s", wp_id, feature_dir)
    return str(Lane.PLANNED.value)


def _find_wp_ids_for_lane(
    feature_dir: Path, lane_id: str,
) -> list[str]:
    """Find WP IDs assigned to a lane from lanes.json."""
    try:
        from specify_cli.lanes.persistence import read_lanes_json

        manifest = read_lanes_json(feature_dir)
        if manifest is None:
            return []
        for lane in manifest.lanes:
            if lane.lane_id == lane_id:
                return list(lane.wp_ids)
    except Exception:
        logger.debug("Could not read lanes.json for %s in %s", lane_id, feature_dir)
    return []


def _find_mission_branch(feature_dir: Path) -> str:
    """Find the mission integration branch from lanes.json."""
    try:
        from specify_cli.lanes.persistence import read_lanes_json

        manifest = read_lanes_json(feature_dir)
        if manifest is not None:
            return str(manifest.mission_branch)
    except Exception:
        logger.debug("Could not read mission branch from %s", feature_dir)
    return ""


def _mission_id_from_meta(feature_dir: Path) -> str | None:
    """Return ``mission_id`` declared in ``meta.json``, or ``None`` if absent.

    Feeds the fail-closed branch composer (FR-006): a modern mission carries its
    ULID here; a legacy mission has none and is resolved by slug shape instead.
    """
    # Routed onto the canonical meta.json reader (FR-005 / post-#2091): the
    # pre-existing try/except absorbed both a missing file (OSError) and a
    # malformed/non-object payload to "no mission_id" -- the same silent
    # contract ``mission_metadata.load_meta(..., on_malformed="none")``
    # implements (see the identical idiom in
    # ``missions._read_path_resolver._declares_coordination_branch``).
    meta = load_meta(feature_dir, on_malformed="none")
    raw = meta.get("mission_id") if meta else None
    return str(raw) if raw else None


def _resolve_mission_branch(feature_dir: Path, mission_slug: str) -> str:
    """Resolve the mission branch from lanes.json, else compose fail-closed.

    Replaces the legacy ``f"kitty/mission-{slug}"`` fallback (the live
    wrong-compose path for mid8-era missions): when lanes.json has no branch,
    compose via :func:`mission_branch_name_required`, fed ``mission_id`` from
    ``meta.json``. Dual-era: legacy/mid8-tail slugs resolve; an unresolvable
    modern identity raises :class:`BranchIdentityUnresolved`.
    """
    mission_branch = _find_mission_branch(feature_dir)
    if mission_branch:
        return mission_branch
    meta_path = feature_dir / "meta.json"
    try:
        # ``mission_branch_name_required`` is typed -> str; mypy widens it to
        # ``Any`` through the late-import chain (``follow_imports=skip`` on
        # ``specify_cli.*``) -- pre-existing systemic pattern (see the
        # ``_compose_mission_dir`` cast note in ``_read_path_resolver.py``);
        # bind explicitly so the return narrows back to ``str``.
        composed: str = mission_branch_name_required(
            mission_slug, _mission_id_from_meta(feature_dir)
        )
        return composed
    except InvalidMissionIdentity as exc:
        # Present-but-invalid identity: keep the typed error (its
        # INVALID_MISSION_IDENTITY code and hand-edit remedy) and name the
        # meta.json to correct; the base-class template would say "absent".
        raise InvalidMissionIdentity(exc.invalid_mission_id, meta_path=meta_path) from exc
    except BranchIdentityUnresolved as exc:
        # Absent identity: re-raise with the feature directory in next_step so
        # a recovery caller can locate the meta.json missing its mission_id.
        raise BranchIdentityUnresolved(
            mission_slug,
            next_step=f"{exc.next_step} (meta.json expected at {meta_path})",
        ) from exc


def _read_all_wp_ids_from_tasks(feature_dir: Path) -> list[str]:
    """Return all WP IDs found in the tasks/ directory."""
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        return []
    import re as _re
    wp_id_re = _re.compile(r"^(WP\d{2,})", _re.IGNORECASE)
    wp_ids: list[str] = []
    for md_file in sorted(tasks_dir.glob("WP*.md")):
        m = wp_id_re.match(md_file.name)
        if m:
            wp_ids.append(m.group(1).upper())
    return wp_ids


def _read_wp_dependencies(feature_dir: Path, wp_id: str) -> list[str]:
    """Read the dependencies list from a WP file's frontmatter.

    Deliberately avoids importing anything from specify_cli.lanes.recovery
    to prevent circular import chains.
    """
    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.exists():
        return []
    import re as _re
    wp_id_re = _re.compile(rf"^{_re.escape(wp_id)}(?:[-_.].+)?\.md$", _re.IGNORECASE)
    for md_file in tasks_dir.glob("WP*.md"):
        if wp_id_re.match(md_file.name):
            try:
                from specify_cli.core.dependency_graph import parse_wp_dependencies
                return list(parse_wp_dependencies(md_file))
            except Exception:
                logger.debug("Could not parse dependencies from %s", md_file)
            break
    return []


def _get_all_wp_lanes_from_events(feature_dir: Path) -> dict[str, str]:
    """Return {wp_id: lane} mapping from the status event log.

    Returns an empty dict when the event log is absent or unreadable.
    """
    try:
        from specify_cli.status import reduce, read_events  # noqa: PLC0415

        events = read_events(feature_dir)
        if not events:
            return {}
        snapshot = reduce(events)
        return {wp_id: str(state.get("lane", "planned"))
                for wp_id, state in snapshot.work_packages.items()}
    except Exception:
        logger.debug("Could not read all WP lanes from %s", feature_dir)
        return {}


def _compute_recovery_action(
    *,
    worktree_exists: bool,
    context_exists: bool,
    has_commits: bool,
    status_lane: str,
) -> str:
    """Map the (worktree, context, commits, status) signals to a recovery action.

    Pure decision table extracted from ``scan_recovery_state`` (FR-002 / C901):
    deterministic, side-effect-free, and unit-testable without filesystem or git.
    """
    if not worktree_exists:
        # Branch exists but the worktree is gone (regardless of context state).
        return "recreate_worktree"
    if not context_exists:
        # Worktree exists but the context file is gone.
        return "recreate_context"
    if has_commits and bool(_get_recovery_transitions(Lane(status_lane))):
        # Everything exists but status is behind the filesystem reality.
        return "emit_transitions"
    return "no_action"


def _collect_contexts_by_lane(
    repo_root: Path, mission_slug: str,
) -> dict[str, WorkspaceContext]:
    """Return the existing workspace contexts for *mission_slug* keyed by lane."""
    return {
        ctx.lane_id: ctx
        for ctx in list_contexts(repo_root)
        if ctx.mission_slug == mission_slug
    }


def _scan_live_branch_states(
    repo_root: Path,
    mission_slug: str,
    *,
    primary_dir: Path,
    coord_dir: Path,
    mission_branch: str,
    lane_branches: list[str],
    contexts_by_lane: dict[str, WorkspaceContext],
) -> list[RecoveryState]:
    """Build recovery states for every WP that still has a live lane branch.

    PRIMARY/STATUS split (FR-002 / C-001): lane→WP membership is read from
    ``lanes.json`` on *primary_dir* (LANE_STATE, PRIMARY-partition), while the
    per-WP lane comes from the status event log on *coord_dir* (STATUS — stays
    coord-aware).
    """
    recovery_states: list[RecoveryState] = []
    for branch in lane_branches:
        lane_id = parse_lane_id_from_branch(branch)
        if lane_id is None:
            continue

        worktree_path_from_git = _worktree_exists_for_branch(repo_root, branch)
        expected_worktree, _lane_branch = predict_lane_worktree(
            repo_root, mission_slug, lane_id
        )
        worktree_exists = (
            worktree_path_from_git is not None
            or expected_worktree.exists()
        )

        context = contexts_by_lane.get(lane_id)
        context_exists = context is not None
        has_commits = _branch_has_commits_beyond(repo_root, branch, mission_branch)

        # PRIMARY leg: lane→WP membership from lanes.json.
        wp_ids = _find_wp_ids_for_lane(primary_dir, lane_id)
        if not wp_ids:
            wp_ids = list(context.lane_wp_ids) if context and context.lane_wp_ids else ["unknown"]

        for wp_id in wp_ids:
            # STATUS leg: the per-WP lane comes from the event log (coord-aware).
            status_lane = _get_wp_lane_from_events(coord_dir, wp_id)
            recovery_states.append(
                RecoveryState(
                    wp_id=wp_id,
                    lane_id=lane_id,
                    branch_name=branch,
                    branch_exists=True,
                    worktree_exists=worktree_exists,
                    context_exists=context_exists,
                    status_lane=status_lane,
                    has_commits=has_commits,
                    recovery_action=_compute_recovery_action(
                        worktree_exists=worktree_exists,
                        context_exists=context_exists,
                        has_commits=has_commits,
                        status_lane=status_lane,
                    ),
                )
            )
    return recovery_states


def _enumerate_expected_wp_ids(primary_dir: Path) -> list[str]:
    """Return the union of WP IDs from the tasks/ dir and lanes.json (PRIMARY).

    Both ``tasks/`` (WORK_PACKAGE_TASK) and ``lanes.json`` (LANE_STATE) are
    PRIMARY-partition artifacts — *primary_dir* must already be the routed
    PRIMARY read dir (FR-002).
    """
    all_task_wp_ids = _read_all_wp_ids_from_tasks(primary_dir)
    try:
        from specify_cli.lanes.persistence import read_lanes_json
        manifest = read_lanes_json(primary_dir)
        if manifest is not None:
            for lane in manifest.lanes:
                for wid in lane.wp_ids:
                    if wid not in all_task_wp_ids:
                        all_task_wp_ids.append(wid)
    except Exception:  # noqa: BLE001
        logger.debug("Could not read lanes.json for wp enumeration in %s", primary_dir)
    return all_task_wp_ids


def _append_merged_and_deleted(
    recovery_states: list[RecoveryState],
    *,
    all_task_wp_ids: list[str],
    represented_wps: set[str],
    all_wp_lanes: dict[str, str],
) -> None:
    """Append synthetic ``merged_and_deleted`` states for branchless done WPs."""
    for wp_id in all_task_wp_ids:
        if wp_id in represented_wps:
            continue
        event_lane = all_wp_lanes.get(wp_id, Lane.PLANNED.value)
        if event_lane == Lane.DONE.value:
            recovery_states.append(
                RecoveryState(
                    wp_id=wp_id,
                    lane_id="",
                    branch_name="",
                    branch_exists=False,
                    worktree_exists=False,
                    context_exists=False,
                    status_lane=event_lane,
                    has_commits=False,
                    recovery_action="no_action",
                    resolution_note="merged_and_deleted",
                )
            )


def _collect_done_wp_ids(
    recovery_states: list[RecoveryState], all_wp_lanes: dict[str, str],
) -> set[str]:
    """Return the set of WP IDs that are done (via recovery states or event log)."""
    done_wp_ids: set[str] = set()
    for rs in recovery_states:
        if rs.status_lane == Lane.DONE.value or rs.resolution_note == "merged_and_deleted":
            done_wp_ids.add(rs.wp_id)
    for wp_id_ev, lane_ev in all_wp_lanes.items():
        if lane_ev == Lane.DONE.value:
            done_wp_ids.add(wp_id_ev)
    return done_wp_ids


def _compute_ready_to_start(
    primary_dir: Path,
    *,
    all_task_wp_ids: list[str],
    done_wp_ids: set[str],
    represented_wps: set[str],
    recovery_states: list[RecoveryState],
) -> list[str]:
    """Return WP IDs whose declared deps are all done (PRIMARY tasks/ read).

    ``_read_wp_dependencies`` reads WP frontmatter from ``tasks/`` (WORK_PACKAGE_TASK,
    PRIMARY-partition) on *primary_dir*. Empty when there is no post-merge context.
    """
    if not done_wp_ids:
        return []
    ready_to_start: list[str] = []
    for wp_id in all_task_wp_ids:
        if wp_id in done_wp_ids:
            continue
        if wp_id in represented_wps:
            existing = next((rs for rs in recovery_states if rs.wp_id == wp_id), None)
            if existing and existing.resolution_note not in (
                "merged_and_deleted", "ready_to_start_from_target", "",
            ):
                continue
        deps = _read_wp_dependencies(primary_dir, wp_id)
        if deps and all(dep in done_wp_ids for dep in deps):
            ready_to_start.append(wp_id)
    return ready_to_start


def _append_ready_to_start(
    recovery_states: list[RecoveryState],
    *,
    ready_to_start: list[str],
    all_wp_lanes: dict[str, str],
) -> None:
    """Append synthetic ``ready_to_start_from_target`` states (de-duplicated)."""
    for wp_id in ready_to_start:
        if any(
            rs.wp_id == wp_id and rs.resolution_note == "ready_to_start_from_target"
            for rs in recovery_states
        ):
            continue
        recovery_states.append(
            RecoveryState(
                wp_id=wp_id,
                lane_id="",
                branch_name="",
                branch_exists=False,
                worktree_exists=False,
                context_exists=False,
                status_lane=all_wp_lanes.get(wp_id, "planned"),
                has_commits=False,
                recovery_action="no_action",
                resolution_note="ready_to_start_from_target",
            )
        )


def scan_recovery_state(
    repo_root: Path,
    mission_slug: str,
    *,
    consult_status_events: bool = True,
) -> list[RecoveryState]:
    """Scan for post-crash implementation state.

    Lists branches matching kitty/mission-{slug}*, cross-references
    workspace contexts and status events to detect inconsistencies.

    When ``consult_status_events=True`` (the default), the scanner also
    reads ``kitty-specs/<mission_slug>/status.events.jsonl`` and:

    - Marks WPs whose branch is absent but whose event-log lane is ``done``
      as ``merged_and_deleted`` rather than reporting them as missing.
    - Populates ``RecoveryState.ready_to_start_from_target`` for WPs whose
      declared dependencies are ALL ``done`` according to the event log.

    When ``consult_status_events=False``, only the live-branch scan runs
    (legacy path, no event-log consultation).

    PRIMARY/STATUS read split (FR-002 / #2185, C-001): planning artifacts
    (``lanes.json`` / ``tasks/``, PRIMARY-partition) resolve through the
    kind-aware seam onto the PRIMARY checkout; the status event log (STATUS)
    stays coord-aware so it reads the worktree-local ``status.events.jsonl``.

    Returns a list of RecoveryState objects for WPs that need attention.
    The returned list now also contains synthetic RecoveryState entries
    (recovery_action="no_action") for WPs that are ``ready_to_start_from_target``
    even though they have no live branch — callers can check the
    ``resolution_note`` field to distinguish these from real recovery cases.
    """
    # PRIMARY leg: lanes.json / tasks/ live on the PRIMARY checkout (#2106). A
    # single PRIMARY read dir co-resolves both LANE_STATE and WORK_PACKAGE_TASK.
    seam = placement_seam(repo_root, mission_slug)
    primary_dir = seam.read_dir(MissionArtifactKind.LANE_STATE)
    # STATUS leg: the append-only event log stays coord-aware (C-001 / #2155).
    # Fail-loud on a DELETED coordination branch is deliberate and specified: the
    # WP02 classification ledger records this site as `migrate-fail-loud` because
    # "recovery-state computation genuinely needs to know whether the coord branch
    # backing a WP's event log was deleted, rather than silently reading a
    # stale/absent surface". See docs/development/read-side-seam-classification.md
    # (`lanes/recovery.py` row) and the acceptance test
    # tests/specify_cli/consolidation/test_read_seam_migration_merge_lanes.py
    # ::test_recovery_scan_fails_loud_when_coordination_branch_was_deleted.
    #
    # Tracked follow-up (do not "fix" here): reviewers argue `implement --recover`
    # is the operator's escape hatch from broken state and should render this as a
    # report finding carrying the exception's `doctor coordination --fix` next_step
    # rather than raising. That is a deliberate UX contract change and is out of
    # scope for the read-side seam migration; it needs its own mission.
    coord_dir = seam.read_dir(MissionArtifactKind.STATUS_STATE)

    branches = _list_mission_branches(repo_root, mission_slug)
    lane_branches = [b for b in branches if parse_lane_id_from_branch(b) is not None]

    mission_branch = _resolve_mission_branch(primary_dir, mission_slug)
    contexts_by_lane = _collect_contexts_by_lane(repo_root, mission_slug)

    all_wp_lanes: dict[str, str] = (
        _get_all_wp_lanes_from_events(coord_dir) if consult_status_events else {}
    )

    recovery_states = _scan_live_branch_states(
        repo_root,
        mission_slug,
        primary_dir=primary_dir,
        coord_dir=coord_dir,
        mission_branch=mission_branch,
        lane_branches=lane_branches,
        contexts_by_lane=contexts_by_lane,
    )

    if not consult_status_events:
        # Legacy path: no event-log consultation, return early.
        return recovery_states

    # Extended status-events path: scan WPs with NO live branch.
    represented_wps = {rs.wp_id for rs in recovery_states}
    all_task_wp_ids = _enumerate_expected_wp_ids(primary_dir)
    _append_merged_and_deleted(
        recovery_states,
        all_task_wp_ids=all_task_wp_ids,
        represented_wps=represented_wps,
        all_wp_lanes=all_wp_lanes,
    )

    represented_wps = {rs.wp_id for rs in recovery_states}
    done_wp_ids = _collect_done_wp_ids(recovery_states, all_wp_lanes)
    ready_to_start = _compute_ready_to_start(
        primary_dir,
        all_task_wp_ids=all_task_wp_ids,
        done_wp_ids=done_wp_ids,
        represented_wps=represented_wps,
        recovery_states=recovery_states,
    )
    _append_ready_to_start(
        recovery_states,
        ready_to_start=ready_to_start,
        all_wp_lanes=all_wp_lanes,
    )
    return recovery_states


def get_ready_to_start_from_target(states: list[RecoveryState]) -> list[str]:
    """Extract WP IDs that are ready to start from the target branch tip.

    These are WPs whose dependency lane branches have all been
    merged-and-deleted (confirmed done by the event log) and whose own
    branch does not yet exist.

    Args:
        states: Output of ``scan_recovery_state(..., consult_status_events=True)``

    Returns:
        List of WP IDs ready to start from the target branch tip.
    """
    return [rs.wp_id for rs in states if rs.resolution_note == "ready_to_start_from_target"]


def recover_worktree(
    repo_root: Path,
    mission_slug: str,
    state: RecoveryState,
) -> None:
    """Recover a lane worktree from an existing branch.

    Uses `git worktree add <path> <branch>` (WITHOUT -b) to attach
    to the pre-existing branch.
    """
    from specify_cli.lanes.worktree_allocator import _recover_lane_worktree

    worktree_path, _lane_branch = predict_lane_worktree(
        repo_root, mission_slug, state.lane_id
    )
    _recover_lane_worktree(repo_root, worktree_path, state.branch_name)


def recover_context(
    repo_root: Path,
    mission_slug: str,
    state: RecoveryState,
) -> WorkspaceContext:
    """Recreate a workspace context from branch metadata.

    When the context file is missing but the branch and worktree exist,
    reconstruct the context from available metadata.
    """
    # FR-001 (#2185): lane→WP membership and the mission branch are read from
    # ``lanes.json`` (LANE_STATE) / ``meta.json`` (PRIMARY_METADATA) — both
    # PRIMARY-partition, resolved topology-blind onto the PRIMARY checkout.
    feature_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.LANE_STATE
    )
    worktree_path, _lane_branch = predict_lane_worktree(
        repo_root, mission_slug, state.lane_id
    )

    # Get base info from lanes.json
    wp_ids = _find_wp_ids_for_lane(feature_dir, state.lane_id)
    mission_branch = _resolve_mission_branch(feature_dir, mission_slug)

    # Get base commit.
    # NOTE: without ``--verify``, ``git rev-parse`` echoes ``--end-of-options``
    # back onto stdout verbatim instead of treating it purely as an option
    # terminator (a quirk of its non-``--verify`` argument-scanning mode) —
    # confirmed against real git 2.43. ``--verify`` restores the intended
    # single-ref "resolve or fail" contract this call already relies on
    # (checked via ``returncode``/``stdout``) and keeps ``--end-of-options``
    # effective, matching the documented ``--verify --end-of-options`` idiom.
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--end-of-options", mission_branch],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    base_commit = result.stdout.strip() if result.returncode == 0 else None

    context = WorkspaceContext(
        wp_id=state.wp_id,
        mission_slug=mission_slug,
        worktree_path=str(worktree_path.relative_to(repo_root)),
        branch_name=state.branch_name,
        base_branch=mission_branch,
        base_commit=base_commit,
        dependencies=[],
        created_at=now_utc_iso(),
        created_by="recovery",
        vcs_backend="git",
        lane_id=state.lane_id,
        lane_wp_ids=wp_ids if wp_ids else [state.wp_id],
        current_wp=state.wp_id,
    )
    save_context(repo_root, context)
    return context


def reconcile_status(
    repo_root: Path,
    mission_slug: str,
    state: RecoveryState,
) -> int:
    """Emit missing status transitions to catch up with filesystem reality.

    When a branch exists with commits but status is behind, emit the
    missing transitions. Never advances past in_progress.

    Returns the number of transitions emitted.
    """
    from specify_cli.coordination.status_transition import emit_status_transition_transactional
    from specify_cli.status import TransitionRequest  # noqa: PLC0415

    # KEEP coord-aware (C-001 / #2155 analog): this ``feature_dir`` feeds
    # ``emit_status_transition_transactional`` below — a STATUS-WRITE leg. The
    # status event log lives on the coordination worktree for coord-topology
    # missions, so this MUST stay on the coord-aware resolver — never route it.
    feature_dir = resolve_feature_dir_for_mission(repo_root, mission_slug)
    current_lane = state.status_lane

    # Determine target lane based on evidence
    if state.has_commits:
        target = Lane.IN_PROGRESS
    elif state.context_exists:
        target = Lane.CLAIMED
    else:
        return 0

    try:
        current_lane_enum = Lane(current_lane)
    except ValueError:
        return 0
    transitions = _get_recovery_transitions(current_lane_enum)
    if not transitions:
        return 0

    emitted = 0
    for next_lane in transitions:
        try:
            emit_status_transition_transactional(
                TransitionRequest(
                    feature_dir=feature_dir,
                    mission_slug=mission_slug,
                    wp_id=state.wp_id,
                    to_lane=next_lane,
                    actor=RECOVERY_ACTOR,
                    reason=f"Recovered after crash -- branch {state.branch_name} exists"
                    + (" with commits" if state.has_commits else ""),
                    execution_mode="worktree",
                    repo_root=repo_root,
                )
            )
            emitted += 1
        except Exception:
            break

        if next_lane == target:
            break

    return emitted


def run_recovery(
    repo_root: Path,
    mission_slug: str,
) -> RecoveryReport:
    """Orchestrate full crash recovery: scan + reconcile + report.

    Performs recovery in order:
    1. Scan for post-crash state (including event-log consultation)
    2. Recover worktrees (where branches exist but worktrees don't)
    3. Recover contexts (where worktrees exist but contexts don't)
    4. Reconcile status events
    5. Report WPs ready to start from target branch tip

    Returns a RecoveryReport summarizing what was done.
    """
    states = scan_recovery_state(repo_root, mission_slug)

    # Collect WPs ready to start from target (populated by event-log path)
    ready_wps = get_ready_to_start_from_target(states)

    report = RecoveryReport(
        recovered_wps=[],
        worktrees_recreated=0,
        contexts_recreated=0,
        transitions_emitted=0,
        errors=[],
        ready_to_start_from_target=ready_wps,
    )

    if not states:
        return report

    # Filter to states that need active recovery
    needs_recovery = [s for s in states if s.recovery_action != "no_action"]

    # Track which lanes have already had worktree/context recovery
    # to avoid duplicate operations (multiple WPs share a lane worktree)
    recovered_lanes_worktree: set[str] = set()
    recovered_lanes_context: set[str] = set()

    for state in needs_recovery:
        try:
            # Step 1: Recover worktree if needed (once per lane)
            if state.recovery_action == "recreate_worktree" and state.lane_id not in recovered_lanes_worktree:
                recover_worktree(repo_root, mission_slug, state)
                report.worktrees_recreated += 1
                recovered_lanes_worktree.add(state.lane_id)

                # Also recreate context if it was missing (once per lane)
                if not state.context_exists and state.lane_id not in recovered_lanes_context:
                    recover_context(repo_root, mission_slug, state)
                    report.contexts_recreated += 1
                    recovered_lanes_context.add(state.lane_id)

            # Step 2: Recover context if needed (once per lane)
            elif state.recovery_action == "recreate_context" and state.lane_id not in recovered_lanes_context:
                recover_context(repo_root, mission_slug, state)
                report.contexts_recreated += 1
                recovered_lanes_context.add(state.lane_id)

            # Step 3: Reconcile status (per WP, not per lane)
            try:
                _status_lane_enum = Lane(state.status_lane)
            except ValueError:
                _status_lane_enum = None
            if state.has_commits and _status_lane_enum is not None and bool(_get_recovery_transitions(_status_lane_enum)):
                emitted = reconcile_status(repo_root, mission_slug, state)
                report.transitions_emitted += emitted

            if state.wp_id not in report.recovered_wps:
                report.recovered_wps.append(state.wp_id)

        except Exception as exc:
            report.errors.append(f"{state.wp_id} ({state.lane_id}): {exc}")

    return report
