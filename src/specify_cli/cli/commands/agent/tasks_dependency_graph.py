"""Dependent-gating / dependency-warning glue extracted from ``tasks.py``.

Behaviour-preserving seam extracted from ``tasks.py`` (issue #2058, WP05).
This module holds the *gating/warning glue* that sits on top of the dependency
graph library — it does NOT own the graph library itself. The
``core.dependency_graph`` call sites used by ``validate_workflow`` stay in
``tasks.py``; this seam only re-imports ``build_dependency_graph`` /
``get_dependents`` for the dependent-warning path that ``move_task`` drives.

Contents:

- :func:`compute_incomplete_dependents` — pure: given a WP id, feature dir and a
  prebuilt dependency graph, return the dependents that are not yet complete.
  Testable without the full ``move_task`` flow.
- :func:`_check_dependent_warnings` — renders the for_review dependency alert by
  composing :func:`compute_incomplete_dependents` with workspace resolution.
- :func:`_behind_commits_touch_only_planning_artifacts` — git subprocess helper
  that keeps lane transitions from being blocked by planning-only commits.
- :func:`_count_behind_commits_outside_planning_artifacts` — #3940 companion:
  counts behind-commits touching files outside the ledger trees so the block
  guidance reports source divergence, not the raw commit count.

One-way import rule (INV-2): this module MUST NOT import from
``specify_cli.cli.commands.agent.tasks``. ``tasks.py`` imports from here.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

from specify_cli.cli.console import console

from specify_cli.core.dependency_graph import build_dependency_graph, get_dependents
from specify_cli.core.paths import get_main_repo_root
from specify_cli.core.vcs.git import (
    git_diff_names_checked,
    git_merge_base,
    git_rev_list_count,
)
from specify_cli.status import Lane, resolve_lane_alias
from specify_cli.workspace.context import resolve_workspace_for_wp

__all__ = [
    "compute_incomplete_dependents",
    "_check_dependent_warnings",
    "_behind_commits_touch_only_planning_artifacts",
    "_count_behind_commits_outside_planning_artifacts",
]


# #3940: roots of the ledger/planning trees whose commits never count as
# source divergence in the lane-currency check. Whole trees, not per-mission
# subtrees — a missions-family target branch carries the orchestrator's
# ledger commits for every mission on the branch.
_PLANNING_LEDGER_ROOTS = ("kitty-specs/", ".kittify/")



def compute_incomplete_dependents(wp_id: str, feature_dir: Path, graph: dict[str, list[str]]) -> list[str]:
    """Return dependents of ``wp_id`` that are not yet complete (pure).

    Reads the canonical event log under ``feature_dir`` to resolve each
    dependent's lane and returns the subset still in ``planned`` /
    ``in_progress`` / ``claimed``. Extracted from the ``move_task`` for_review
    dependent-warning path so the gating logic is testable without driving the
    full command flow.

    Args:
        wp_id: Work package whose dependents are inspected.
        feature_dir: Mission directory holding the status event log.
        graph: Dependency adjacency list from :func:`build_dependency_graph`.

    Returns:
        Dependent WP ids that are incomplete, in graph order.
    """
    dependents = get_dependents(wp_id, graph)
    if not dependents:
        return []

    # Check if any dependents are incomplete (not yet done)
    # Lane is event-log-only; read from canonical event log
    try:
        from specify_cli.status import read_events as _dw_read_events
        from specify_cli.status import reduce as _dw_reduce

        _dw_events = _dw_read_events(feature_dir)
        _dw_snapshot = _dw_reduce(_dw_events) if _dw_events else None
        _dw_lanes: dict[str, Lane] = {}
        if _dw_snapshot:
            for _dw_wp_id, _dw_state in _dw_snapshot.work_packages.items():
                _dw_lanes[_dw_wp_id] = Lane(_dw_state.get("lane", Lane.PLANNED))
    except Exception:
        _dw_lanes = {}

    incomplete = []
    for dep_id in dependents:
        # Skip any dependent we cannot read; behavior-preserving with the prior
        # ``try/except: continue`` (S110 is globally ignored as redundant with
        # this contextlib form, see pyproject [tool.ruff.lint].ignore).
        with contextlib.suppress(Exception):
            lane = _dw_lanes.get(dep_id, Lane.PLANNED)

            if resolve_lane_alias(lane) in [Lane.PLANNED, Lane.IN_PROGRESS, Lane.CLAIMED]:
                incomplete.append(dep_id)

    return incomplete


def _check_dependent_warnings(repo_root: Path, mission_slug: str, wp_id: str, target_lane: str, json_mode: bool) -> None:
    """Display warning when WP moves to for_review and has incomplete dependents.

    Args:
        repo_root: Repository root path
        mission_slug: Feature slug (e.g., "010-lane-only-runtime")
        wp_id: Work package ID (e.g., "WP01")
        target_lane: Target lane being moved to
        json_mode: If True, suppress Rich console output
    """
    # Only warn when moving to for_review
    if target_lane != Lane.FOR_REVIEW:
        return

    # Don't show warnings in JSON mode
    if json_mode:
        return

    # Write path: keep main-repo-root resolution so canonical serialization
    # pins to the primary checkout regardless of where the operator stands.
    main_repo_root = get_main_repo_root(repo_root)
    # late import — keeps cold-start cost low
    from mission_runtime import MissionArtifactKind, placement_seam

    # read-surface-ssot-closeout WP08 / FR-001 / NFR-001: route the kind-blind
    # resolve_feature_dir_for_mission STATUS leg onto the kind-aware placement
    # seam. STATUS_STATE stays on the topology-aware (coord-aware) partition —
    # the SAME resolution resolve_feature_dir_for_mission produced for this
    # read — so read_events inside compute_incomplete_dependents keeps reading
    # the coordination worktree's event log for a coord-topology mission.
    feature_dir = placement_seam(main_repo_root, mission_slug).read_dir(
        MissionArtifactKind.STATUS_STATE
    )
    # WP06 / FR-004 / C-001 per-leg split: build_dependency_graph reads tasks/ from PRIMARY
    # (WORK_PACKAGE_TASK-partition); compute_incomplete_dependents reads status.events.jsonl
    # from the coord-aware feature_dir above.  Do NOT change build_dependency_graph's signature
    # — route by passing primary_dir at the CALLER only. The out-of-loop callers (policy/
    # merge_gates) now apply this SAME per-leg reroute at their own call sites (#3439 / FR-003
    # /FR-005 lifted the earlier C-009 deferral).
    primary_dir = placement_seam(main_repo_root, mission_slug).read_dir(
        MissionArtifactKind.WORK_PACKAGE_TASK
    )

    # Build dependency graph from PRIMARY (tasks/ lives there, not on coord husk).
    try:
        graph = build_dependency_graph(primary_dir)
    except Exception:
        # If we can't build the graph, skip warnings
        return

    incomplete = compute_incomplete_dependents(wp_id, feature_dir, graph)

    if incomplete:
        current_workspace = resolve_workspace_for_wp(main_repo_root, mission_slug, wp_id)
        console.print("\n[yellow]⚠️  Dependency Alert[/yellow]")
        console.print(f"{', '.join(incomplete)} depend on {wp_id} (not yet done)")
        console.print("\nIf changes are requested during review:")
        console.print("  1. Notify dependent WP agents")
        console.print("  2. Dependent workspaces may need to incorporate your changes")
        for dep in incomplete:
            dep_workspace = resolve_workspace_for_wp(main_repo_root, mission_slug, dep)
            if dep_workspace.branch_name is None:
                # Planning-lane WP: operates in the main repo checkout, no worktree
                # to rebase.  The planning workspace is always up-to-date with main.
                console.print(f"     {dep}: planning-lane workspace (main repo checkout) — no rebase needed; ensure main is up to date")
            elif dep_workspace.branch_name == current_workspace.branch_name:
                console.print(f"     {dep}: shares {current_workspace.branch_name} (same lane, no separate rebase command)")
            else:
                console.print(f"     cd {dep_workspace.worktree_path} && git rebase {current_workspace.branch_name}")
        console.print()


def _behind_commits_touch_only_planning_artifacts(
    worktree_path: Path,
    check_branch: str,
    mission_slug: str,  # noqa: ARG001 — kept for the injected-callable signature (#3940)
) -> bool:
    """Return True when upstream commits only touch planning/status files.

    This prevents lane transitions from being blocked by commits that update
    task metadata on the planning branch (for example mark-status/move-task).

    Diffs ``merge_base..check_branch`` — the diff TARGET is ``check_branch``,
    not ``HEAD`` (mission merge-base-diff-ssot-01KX44SD, F1 guard). The
    merge-base step routes through the canonical two-ref
    ``core.vcs.git.git_merge_base`` primitive, which eliminates any risk of
    this site ever drifting onto the HEAD-relative ``merge_base_changed_files``
    convenience (that convenience computes ``mb..HEAD`` and would silently
    invert which commits are inspected).

    Fully consolidated onto the shared surface: the diff step uses
    ``core.vcs.git.git_diff_names_checked``, the fail-CLOSED variant that
    returns ``None`` on a diff subprocess failure (→ ``False``, block) as
    distinct from an empty tuple on a genuinely empty diff (→ ``True``,
    non-blocking). This resolves the prior NFR-002 exception where the diff
    stayed a direct subprocess call because ``git_diff_names`` collapsed
    "failed" and "empty" into the same empty tuple.

    #3940: the ledger trees are matched WHOLE — ``kitty-specs/`` and
    ``.kittify/`` at the root, not per-mission subtrees. A missions-family
    target branch carries the orchestrator's ledger/planning commits for
    *every* mission on the branch, so a lane can sit "behind" by dozens of
    commits that touch zero source paths; counting those as divergence forced
    a pointless rebase across ~90 ledger-only commits (the #3940 report). The
    check therefore decides "behind" on source divergence, not commit count.
    """
    merge_base = git_merge_base(worktree_path, "HEAD", check_branch)
    if merge_base is None:
        return False

    # Compare merge-base..check_branch to inspect only commits that HEAD is
    # behind on (the branch, not HEAD, is the diff target). Fail-closed: a diff
    # failure (None) blocks; a genuinely empty diff (()) is non-blocking.
    changed = git_diff_names_checked(worktree_path, merge_base, check_branch)
    if changed is None:
        return False

    changed_files = list(changed)
    if not changed_files:
        return True

    # #3940: whole-tree ledger roots (see _PLANNING_LEDGER_ROOTS).
    return all(path.startswith(_PLANNING_LEDGER_ROOTS) for path in changed_files)


def _count_behind_commits_outside_planning_artifacts(
    worktree_path: Path,
    check_branch: str,
    behind_count: int,
) -> int:
    """Count behind-commits touching files outside the ledger trees (#3940).

    One fail-closed ``git_rev_list_count`` call over ``HEAD..check_branch``
    with the ledger roots excluded via pathspecs, so the block guidance
    reports *source* divergence — the number of commits the lane actually
    has to rebase across — instead of the raw behind count, which is
    dominated by orchestrator ledger commits.

    Args:
        worktree_path: Lane worktree whose HEAD is behind.
        check_branch: The branch the lane is measured against.
        behind_count: The raw behind count, used as the fail-open fallback
            when the count cannot be determined (the transition already
            blocks in that state, so the message just stays conservative).

    Returns:
        The number of behind commits touching at least one file outside
        ``kitty-specs/`` and ``.kittify/``, or ``behind_count`` on failure.
    """
    pathspecs = (".", *(f":(exclude){root.rstrip('/')}" for root in _PLANNING_LEDGER_ROOTS))
    counted = git_rev_list_count(worktree_path, f"HEAD..{check_branch}", pathspecs=pathspecs)
    if counted is None:
        return behind_count
    return counted
