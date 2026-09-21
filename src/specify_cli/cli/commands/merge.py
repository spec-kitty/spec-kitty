"""Merge command implementation.

Lane worktrees are the only supported execution topology. ``spec-kitty merge``
always follows the same two-step flow, and the two steps are two *distinct*
"merge" operations (see the sense entries in ``docs/context/orchestration.md``):
1. Lane consolidation (``merge`` Sense 1, LOCAL): consolidate each lane branch
   into the mission branch — no remote push.
2. Branch integration / git merge (``merge`` Sense 2): integrate the mission
   branch into the target branch.
Neither step is publish-to-origin/main (``merge`` Sense 3): that operator-only
publish happens only under ``--push`` and is never implied by the command name.

Planning-artifact-only missions are the exception: their artifacts are already
committed to the target branch, so merge performs closeout bookkeeping directly
on that target branch without requiring a mission branch.

Recovery semantics (WP01 / 067):
- MergeState is created at merge start and updated after each WP mark-done.
- On interruption, rerunning ``merge`` detects the existing state and resumes.
- ``--resume`` explicitly triggers resume; ``--abort`` cleans up state and exits.
- ``cleanup_merge_workspace`` preserves state.json so recovery works.
- ``clear_state`` is called only after confirmed full completion.
"""

# ─────────────────────────────────────────────────────────────────────────────
# #2057 DECOMPOSITION SHIM (matches the #2056 / #1623 convention).
#
# This module is the thin Typer command-registration shim for ``spec-kitty
# merge``. The former ~3383-LOC / maxCC-102 god-module was decomposed into
# cohesive, independently-tested seams under ``specify_cli/merge/``:
#
#   _constants.py            shared literals / type aliases / logger
#   git_probes.py            branch/tree/porcelain git primitives (+ public
#                            ``path_is_under_worktrees``)
#   resolve.py               slug / merge-state / target-branch resolution
#   preflight.py             git / target / mission-branch / canonical-status /
#                            review-artifact / hollow-review preflights
#   push_preflight.py        publish-layer push/target-sync preflight (#1706)
#   forecast.py              ``--dry-run`` preview + JSON/human payload build
#   ordering.py              mission-number bake cluster (+ merge ordering)
#   done_bookkeeping.py      done/approved emission + done asserts + reconcile
#   bookkeeping_projection.py status-surface trust + snapshot/restore + projection
#   executor.py              ``_run_lane_based_merge[_locked]`` + the phase helpers
#
# RULES (do NOT regress):
#   * This shim owns ONLY the ``merge`` command, its dispatch helpers, and the
#     re-export ``__all__`` (kept byte-stable so the 3 src consumers +
#     ~41 importing test files need zero edits — INV-4 / FR-006).
#   * One-way imports: seams never import this shim (no cycles — C-006/INV-2).
#   * Extract new responsibilities into a seam; never grow this module.
#
# De-godding effort: https://github.com/Priivacy-ai/spec-kitty/issues/2057
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations


from specify_cli.core.constants import KITTIFY_DIR
from mission_runtime import MissionArtifactKind, placement_seam
import json
from typing import TYPE_CHECKING

import typer

from specify_cli import __version__ as SPEC_KITTY_VERSION
from specify_cli.cli.console import console
from specify_cli.cli.helpers import show_banner
from specify_cli.context.mission_resolver import mission_not_found_message
from specify_cli.core.context_validation import require_main_repo
from specify_cli.core.paths import (
    MissionMetaReadError,
    UnsafePathSegmentError,
    get_main_repo_root,
    resolve_merge_retention,
)
from specify_cli.git.sparse_checkout import (
    SparseCheckoutPreflightError,
)
from specify_cli.lanes.persistence import CorruptLanesError, MissingLanesError
from specify_cli.merge.baseline import (
    BaselineMergeCommitError,
    _read_committed_meta_json,
    _recorded_baseline_from_working_meta,
    assert_baseline_merge_commit_on_target as _assert_baseline_merge_commit_on_target,
    record_baseline_merge_commit as _record_baseline_merge_commit,
)
from specify_cli.merge.config import MergeStrategy, load_merge_config

# WP02 (#2057): shared literals/type-aliases/logger live in the merge seam's
# ``_constants`` module so later seams import them from one home (S1192-safe).
# Re-imported here (and re-exported via ``__all__``) so the public surface and
# every importer stay byte-stable (FR-003, C-008, INV-8).
from specify_cli.merge._constants import (
    HollowReviewWarnings,
    LINEAR_HISTORY_REJECTION_TOKENS,
    MissionBranchBlocker,
    TARGET_BRANCH_NOT_SYNCHRONIZED,
    TARGET_BRANCH_SYNC_INVARIANT,
    _SAFE_PATH_SEGMENT_DIAGNOSTIC,
    _STATUS_EVENTS_FILENAME,
    _STATUS_FILENAME,
    logger,
)

# WP03 (#2057): low-level git probes/primitives live in the merge seam's
# ``git_probes`` module. Re-imported here (and re-exported via ``__all__``) so
# external consumers (doctor.py, agent/mission.py) and ~41 test files keep
# importing them — esp. the PUBLIC ``path_is_under_worktrees`` — with zero edits
# (FR-006, C-006). One-way import: ``git_probes`` never imports this shim.
from specify_cli.merge.git_probes import (
    _branch_trees_equal,
    _classify_porcelain_lines,
    _emit_remediation_hint,
    _has_branch_ref,
    _is_git_repo,
    _is_linear_history_rejection,
    _lane_already_integrated,
    _paths_have_status_changes,
    _raw_porcelain_status,
    _refresh_primary_checkout_after_merge,
    path_is_under_worktrees,
)

# WP06 (#2057): the merge --dry-run forecast (preview + payload build) lives in
# the merge seam's ``forecast`` module; the command body delegates to it.
from specify_cli.merge.forecast import run_dry_run_forecast
from specify_cli.merge.retention import (
    MISSION_RETENTION_CLEANUP_CONFLICT,
    load_mission_retention,
    retention_cleanup_conflicts,
)

# WP08 (#2057): done/approved transition emission, the done asserts, resume
# reconcile, and the per-WP recording loop live in the merge seam's
# ``done_bookkeeping`` module. _mark_wp_merged_done + the asserts are re-exported
# from the shim so orchestrator_api/commands.py and tests import unchanged
# (FR-006). One-way import: ``done_bookkeeping`` never imports this shim.
from specify_cli.merge.done_bookkeeping import (
    _assert_merged_wps_done_on_target,
    _assert_merged_wps_reached_done,
    _has_transition_to,
    _mark_wp_merged_done,
    _reconcile_completed_wps_for_resume,
    _resolve_merge_actor,
)

# WP10 (#2057): the lane-based merge executor (the global-lock wrapper + the
# decomposed CC-102 locked driver) lives in the merge seam's ``executor``
# module. Re-imported here (and re-exported via __all__) so the command body +
# the test/integration-imported _run_lane_based_merge[_locked] keep importing
# from the shim (FR-006). One-way import: ``executor`` never imports this shim.
from specify_cli.merge.executor import (
    CoordinationTeardownError,
    _run_lane_based_merge,
    _run_lane_based_merge_locked,
)

# WP09 (#2057): status-surface trust + final-bookkeeping snapshot/restore +
# coord->target projection live in the merge seam's ``bookkeeping_projection``
# module. Re-imported here (and re-exported via __all__) so test-imported trust /
# snapshot / projection symbols keep importing from the shim with zero edits
# (FR-006, INV-6). One-way import: the seam never imports this shim.
# WP09 (T048 / TAO-3): the final-bookkeeping snapshot/restore compensator and its
# merge-side trust helper were retired from ``bookkeeping_projection`` — the merge
# executor now enrols those bytes with the single owner compensator in
# ``coordination.atomic_write``. Only the surviving trust + projection symbols are
# re-exported through this shim.
from specify_cli.merge.bookkeeping_projection import (
    _assert_status_path_within_target_surface,
    _assert_status_surface_path_is_trusted,
    _project_status_bookkeeping_to_target,
    _target_bookkeeping_status_paths,
    _target_branch_still_at_baseline,
    _validate_mission_slug_path_segment,
)

# WP04 (#2057): slug / merge-state / target-branch resolution lives in the merge
# seam's ``resolve`` module (consuming merge/state.py). Re-imported here (and
# re-exported via ``__all__``) so test-imported resolvers keep importing from
# the shim with zero edits (FR-006, C-002). One-way import: ``resolve`` never
# imports this shim.
from specify_cli.merge.resolve import (
    _cleanup_merge_workspaces_for_state,
    _clear_merge_state_for_mission,
    _load_merge_state_entry_for_mission,
    _load_merge_state_for_mission,
    _load_or_create_merge_state,
    _resolve_mission_slug,
    _resolve_target_branch,
)

# WP07 (#2057): the mission-number bake cluster lives in the merge seam's
# ``ordering`` module (next to assign_next_mission_number). Re-imported here so
# the shim body + the test-imported ``_bake_mission_number_into_mission_branch``
# (re-exported via __all__) keep working with zero edits (FR-006). Lazy imports
# inside the bake cluster stay lazy (C-007).
from specify_cli.merge.ordering import (
    _bake_mission_number_into_mission_branch,
)

# WP05 (#2057): git / target-branch / mission-branch / canonical-status /
# review-artifact / hollow-review preflights live in the merge seam's
# ``preflight`` module. Re-imported here (and re-exported via ``__all__``) so
# test-imported preflight symbols keep importing from the shim with zero edits
# (FR-006, C-002). One-way import: ``preflight`` never imports this shim.
from specify_cli.merge.preflight import (
    _check_mission_branch,
    _collect_hollow_review_warnings,
    _effective_push_requested,
    _enforce_canonical_status_history,
    _enforce_git_preflight,
    _enforce_planning_artifact_target_branch,
    _enforce_review_artifact_consistency,
    _validate_target_branch,
    _warn_or_confirm_hollow_reviews,
    target_branch_sync_remediation,
)

# WP05 (#2057): the push/target-sync preflight + its diagnostic payloads live in
# the publish-layer ``push_preflight`` module (domain ``preflight`` stays
# network-free, issue #1706). Re-exported for the test-imported surface.
from specify_cli.merge.push_preflight import (
    _enforce_target_branch_sync_preflight,
    _target_branch_sync_payload,
)
from specify_cli.merge.state import (
    abort_git_merge,
    clear_state,
    has_active_merge,
    load_state,
)
from specify_cli.merge.workspace import get_merge_runtime_dir, get_merge_workspace_path
from specify_cli.post_merge.retrospective_terminus import run_retrospective_postcondition
from specify_cli.task_utils import TaskCliError, find_repo_root

# WP05 (#2057): the git-ops primitive ``run_command`` and the git-preflight
# entrypoint ``run_git_preflight`` / payload builder
# ``build_git_preflight_failure_payload`` were relocated to ``core.git_ops`` /
# ``core.git_preflight`` by the decomposition. Re-imported here so the historical
# ``merge.<symbol>`` patch targets that ~several test modules monkeypatch keep
# resolving against the shim (FR-006, patch-target stability). Deliberately NOT
# in ``__all__``: ``__all__`` membership only affects ``from merge import *`` and
# nothing imports these FROM this shim, so listing them trips the dead-symbol
# gate. One-way import: the core modules never import this shim.
from specify_cli.core.git_ops import (
    run_command,  # noqa: F401 — re-exported as a monkeypatch target for tests/agent/test_commands.py + sparse-checkout integration tests; not part of the public *-import surface
)
from specify_cli.core.git_preflight import (
    build_git_preflight_failure_payload,  # noqa: F401 — re-exported as a monkeypatch target for the git-preflight tests; not part of the public *-import surface
    run_git_preflight,  # noqa: F401 — re-exported as a monkeypatch target for the git-preflight tests; not part of the public *-import surface
)

if TYPE_CHECKING:
    from pathlib import Path

    from specify_cli.merge.state import MergeState


def _clean_mission_option(mission: object) -> str | None:
    """Guard a ``--mission`` value against an unresolved ``typer.Option`` default.

    ``mission: str = typer.Option(None, "--mission", ...)`` on the ``merge``
    Typer command resolves its default at CLI-runtime only. A caller that
    invokes ``merge()`` (or a helper threaded its raw ``mission`` parameter)
    directly as a plain Python function without supplying ``mission=`` gets
    the *unresolved* ``OptionInfo`` sentinel back instead of ``None`` — a
    truthy, non-``str`` object with no ``.strip()`` method. ``(mission or
    "").strip()`` then raises ``AttributeError`` instead of falling through
    to mission auto-detection / the clean "Use --mission" diagnostic.
    Mirrors the same guard in ``cli/selector_resolution._normalize_selector``.
    """
    if not isinstance(mission, str):
        return None
    return mission


def _resolve_slug_or_exit(repo_root: Path, mission: str | None) -> str | None:
    """Resolve the operator-supplied mission handle to a canonical slug.

    Shared by the abort/resume/main paths; raises ``typer.Exit(2)`` with the
    canonical path-segment diagnostic when the handle is traversal-unsafe, or
    the structured ambiguity error (#4723) when a bare human slug names more
    than one composed ``<slug>-<mid8>`` primary dir — previously uncaught
    here, producing a raw traceback instead of a clean diagnostic.
    """
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    mission_slug_raw = (_clean_mission_option(mission) or "").strip() or None
    try:
        return _resolve_mission_slug(repo_root, mission_slug_raw)
    except UnsafePathSegmentError as exc:
        console.print(f"[red]Error:[/red] {_SAFE_PATH_SEGMENT_DIAGNOSTIC}: {exc}")
        raise typer.Exit(2) from exc
    except MissionSelectorAmbiguous as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(2) from exc


def _resolved_mission_dir_exists(repo_root: Path, resolved_slug: str) -> bool:
    """Return True when the resolved handle names an existing mission dir.

    Mirrors the existence probe inside ``_resolve_mission_slug`` (which hands back
    the RAW handle, unchanged, on a miss): a handle that resolves to no
    PRIMARY-partition mission dir is a not-found. This is the predicate the
    fresh/resume gates use to refuse an unknown ``--mission`` with the canonical
    :func:`mission_not_found_message` instead of the misleading downstream errors
    ("lanes.json is required …" / "No interrupted merge to resume").

    Deliberately NOT folded into the shared ``_resolve_slug_or_exit`` helper:
    ``merge --abort`` shares that helper and MUST stay tolerant of an
    unresolvable handle (it cleans up a partial-state mission whose primary dir
    may already be gone), so the gate lives at the two live callers only (FR-005).

    ``StatusReadPathNotFound`` (the fail-closed coordination window) is treated as
    "exists" so this probe never pre-empts that path; for ``PRIMARY_METADATA`` the
    seam does not raise it today, but the defensive arm keeps the historical
    downstream behaviour intact if that ever changes.
    """
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    try:
        candidate = placement_seam(get_main_repo_root(repo_root), resolved_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    except StatusReadPathNotFound:
        return True
    return candidate.exists()


def _teardown_coordination_for_abort(
    repo_root: Path,
    resolved: str | None,
    state_entry: tuple[str | None, MergeState] | None,
) -> None:
    """Coordination-topology teardown during ``--abort`` (FR-016).

    Idempotent; a no-op for legacy missions without coordination state. The
    slug/meta RESOLUTION stays best-effort (a partial-state abort may have no
    resolvable slug), but the actual teardown routes through the shared
    ``teardown_coordination_topology`` seam (FR-004) OUTSIDE that swallow so the
    persist-before-destroy leg (FR-005) is not masked as "best-effort cleanup".

    #3131 FR-012/T009: an ``--abort`` has no ``--keep-worktree`` flag of its
    own, so the mission's ``meta.json`` retention policy is the ONLY signal —
    resolved with both explicit flags unset (``None``). When the policy
    requests worktree retention, the destroy leg is skipped entirely (INV-1:
    no silent deletion) and a notice is printed. A corrupt ``meta.json`` here
    falls through the same best-effort slug/meta swallow as everything else in
    this resolution block (an abort must not itself crash on unreadable meta);
    the practical effect is fail-closed anyway — an unresolved policy means the
    destroy leg is skipped, never that it proceeds.
    """
    from specify_cli.coordination.teardown import teardown_coordination_topology
    from specify_cli.core.paths import load_meta_fail_closed as _load_meta

    abort_teardown_args: tuple[Path, str, str] | None = None
    retain_worktree = False
    try:
        main_for_abort = get_main_repo_root(repo_root)
        coord_slug = resolved
        if coord_slug is None and state_entry is not None:
            coord_slug = state_entry[1].mission_slug
        if not coord_slug:
            raise ValueError("cannot resolve mission slug for coordination cleanup")
        # FR-001 (#2185): ``meta.json`` (PRIMARY_METADATA, PRIMARY-partition) lives
        # ONLY on the PRIMARY checkout post-#2106. The ``--abort`` teardown reads it
        # to discover the mission identity (``mid8``) of the coord worktree to tear
        # down — reading off the kind-blind resolver lands on the STATUS-only
        # ``-coord`` husk, whose ``meta.json`` is absent or carries a stale/sentinel
        # identity. Route by kind so the teardown anchors on the real PRIMARY meta.
        feature_dir = placement_seam(main_for_abort, coord_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        meta = _load_meta(feature_dir)
        mid8 = str(meta.get("mid8", "")).strip() if isinstance(meta, dict) else ""
        retention = resolve_merge_retention(
            feature_dir,
            explicit_delete_branch=None,
            explicit_remove_worktree=None,
        )
        for warning in retention.warnings:
            console.print(f"[yellow]Warning:[/yellow] {warning}")
        retain_worktree = not retention.remove_worktree
        abort_teardown_args = (main_for_abort, coord_slug, mid8)
    except Exception as exc:  # noqa: BLE001 — slug/meta resolution is best-effort
        logger.debug(
            "Coordination teardown during --abort skipped (unresolved slug/meta): %s",
            exc,
        )

    if abort_teardown_args is None:
        return
    if retain_worktree:
        console.print("[yellow]Notice:[/yellow] retention honored for worktrees (source: meta.json) — coordination worktree kept during abort.")
        return
    # Persist-before-destroy runs OUTSIDE the resolution swallow.
    teardown_coordination_topology(*abort_teardown_args)


def _dispatch_abort(repo_root: Path, mission: str | None) -> None:
    """Handle ``merge --abort``: clear state, locks, legacy files, git merge, coord."""
    from contextlib import suppress

    resolved = _resolve_slug_or_exit(repo_root, mission)
    state_entry = _load_merge_state_entry_for_mission(repo_root, resolved)
    if state_entry is None and resolved is None:
        state_entry = _load_merge_state_entry_for_mission(repo_root, None)
    if state_entry is not None and resolved is None:
        resolved = state_entry[1].mission_slug

    if resolved or state_entry is not None:
        # T015/#4754: a git-level merge abort is only ever legitimate when
        # active spec-kitty merge state exists for THIS mission, and only
        # scoped to that mission's own merge workspace
        # (.kittify/runtime/merge/<mission_id>/workspace/) -- NEVER
        # repo_root. The merge pipeline runs `git merge` exclusively inside
        # spec-kitty-owned worktrees (the ephemeral lane-consolidation tmp worktree,
        # unconditionally cleaned up on exit, and the persisted
        # conflict-resolution workspace); a MERGE_HEAD in repo_root is
        # always the operator's OWN in-progress merge and must never be
        # touched. Detected/aborted BEFORE workspace cleanup below so the
        # message reflects what actually happened (FR-006) rather than
        # racing the force-removal that follows.
        git_merge_aborted = False
        if state_entry is not None:
            _, active_state = state_entry
            if has_active_merge(repo_root, active_state.mission_id):
                workspace_path = get_merge_workspace_path(active_state.mission_id, repo_root)
                if workspace_path.exists():
                    git_merge_aborted = abort_git_merge(workspace_path)

        cleared = _clear_merge_state_for_mission(repo_root, resolved)
        if state_entry is not None:
            source_key, active_state = state_entry
            if source_key:
                cleared = clear_state(repo_root, source_key) or cleared
            cleared = clear_state(repo_root, active_state.mission_id) or cleared
        _cleanup_merge_workspaces_for_state(repo_root, mission_slug=resolved, state_entry=state_entry)
        _teardown_coordination_for_abort(repo_root, resolved, state_entry)
        if cleared:
            console.print(f"[green]Aborted[/green] merge for {resolved}. State and workspace cleaned up.")
        else:
            console.print(f"[yellow]No active merge state found for {resolved}.[/yellow] Workspace cleaned up.")
        if git_merge_aborted:
            console.print("[green]Aborted[/green] in-progress git merge in the merge workspace.")
    else:
        cleared = clear_state(repo_root)
        if cleared:
            console.print("[green]Aborted[/green] merge. State cleaned up.")
        else:
            console.print("[yellow]No active merge state to abort.[/yellow]")

    # T002: Remove the global merge lock file (idempotent — a crash between lock
    # acquisition and release in _run_lane_based_merge leaves it behind).
    _global_lock_path = get_merge_runtime_dir("__global_merge__", repo_root) / "lock"
    with suppress(FileNotFoundError):
        _global_lock_path.unlink()
        console.print("[green]Removed merge lock.[/green]")

    # T003: Remove the legacy .kittify/merge-state.json (pre-mission-scoped releases).
    _legacy_state_path = repo_root / KITTIFY_DIR / "merge-state.json"
    with suppress(FileNotFoundError):
        _legacy_state_path.unlink()
        console.print("[green]Removed legacy merge-state.[/green]")

    # T004 (#4754): the unconditional `abort_git_merge(repo_root)` call that
    # used to live here is REMOVED -- spec-kitty never runs `git merge`
    # against repo_root, so a MERGE_HEAD found there is always the
    # operator's own in-progress merge. The only legitimate git-level abort
    # (scoped to the spec-kitty merge workspace, gated on active state) now
    # runs above, before workspace cleanup.


def _dispatch_resume(repo_root: Path, mission: str | None, *, json_output: bool = False) -> str | None:
    """Handle ``merge --resume``: require interrupted state; return the mission slug.

    Returns the mission slug to thread into the main flow (the operator may have
    omitted ``--mission``, in which case the stored slug is adopted).
    """
    mission_slug_raw = (_clean_mission_option(mission) or "").strip() or None
    resolved = _resolve_slug_or_exit(repo_root, mission)
    # FR-004/FR-005: an unknown ``--mission`` handle is refused with the canonical
    # not-found BEFORE the no-state check, so a fat-fingered handle never masquerades
    # as "No interrupted merge to resume". The gate is confined to this caller (and
    # the fresh flow) — never the shared ``_resolve_slug_or_exit`` — so ``--abort``
    # stays tolerant.
    if resolved and not _resolved_mission_dir_exists(repo_root, resolved):
        error_msg = mission_not_found_message(resolved)
        if json_output:
            print(json.dumps({"spec_kitty_version": SPEC_KITTY_VERSION, "error": error_msg}))
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)
    existing_state = _load_merge_state_for_mission(repo_root, resolved)
    if existing_state is None:
        console.print("[red]Error:[/red] No interrupted merge to resume.")
        raise typer.Exit(1)
    console.print(
        f"[bold cyan]Resume requested[/bold cyan] for {existing_state.mission_slug} ({len(existing_state.completed_wps)}/{len(existing_state.wp_order)} done)"
    )
    return existing_state.mission_slug if not mission_slug_raw else mission


def _enforce_retention_cleanup(
    repo_root: Path,
    mission_slug: str,
    *,
    delete_branch: bool | None,
    remove_worktree: bool | None,
    json_output: bool,
) -> None:
    """Require explicit cleanup choices when a mission retains its artifacts."""

    retention = load_mission_retention(get_main_repo_root(repo_root), mission_slug)
    conflicts = retention_cleanup_conflicts(
        retention,
        delete_branch=delete_branch,
        remove_worktree=remove_worktree,
    )
    if not conflicts:
        return

    remediation = [
        "--keep-branch and/or --keep-worktree to retain those artifacts",
        "--delete-branch and/or --remove-worktree to separately direct cleanup",
    ]
    if json_output:
        print(
            json.dumps(
                {
                    "spec_kitty_version": SPEC_KITTY_VERSION,
                    "mission_slug": mission_slug,
                    "blocked": True,
                    "blockers": [
                        {
                            "diagnostic_code": MISSION_RETENTION_CLEANUP_CONFLICT,
                            "retained": list(conflicts),
                            "constraint_id": retention.constraint_id if retention else None,
                            "remediation": remediation,
                        }
                    ],
                    "diagnostic_code": MISSION_RETENTION_CLEANUP_CONFLICT,
                }
            )
        )
    else:
        console.print(
            f"[red]Error:[/red] Mission retention constraint {retention.constraint_id if retention else '<unknown>'} requires an explicit cleanup decision."
        )
        console.print("Omitted cleanup flags default to deletion; retained fields: " + ", ".join(conflicts) + ".")
        console.print(f"  diagnostic_code: {MISSION_RETENTION_CLEANUP_CONFLICT}")
        for action in remediation:
            console.print(f"  - {action}")
    raise typer.Exit(1)


def _run_real_merge(
    repo_root: Path,
    *,
    resolved_mission: str,
    resolved_target_branch: str,
    resolved_strategy: MergeStrategy,
    delete_branch: bool | None,
    remove_worktree: bool | None,
    push: bool,
    allow_sparse_checkout: bool,
    yes: bool,
    skip_review_artifact_check: bool = False,
    skip_note: str | None = None,
    skip_lanes: bool = False,
) -> None:
    """Run the real lane-based merge + post-merge retrospective / next-step hints."""
    try:
        _run_lane_based_merge(
            repo_root=repo_root,
            mission_slug=resolved_mission,
            push=push,
            delete_branch=delete_branch,
            remove_worktree=remove_worktree,
            target_override=resolved_target_branch,
            strategy=resolved_strategy,
            allow_sparse_checkout=allow_sparse_checkout,
            assume_yes=yes,
            skip_review_artifact_check=skip_review_artifact_check,
            skip_note=skip_note,
            skip_lanes=skip_lanes,
        )
    except SparseCheckoutPreflightError as exc:
        # WP05/T020: surface sparse-checkout preflight as a user-facing error and
        # exit non-zero WITHOUT writing any merge state.
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except (MissingLanesError, CorruptLanesError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc
    except CoordinationTeardownError as exc:
        # #3926: the merge itself landed; only the coord triple did not come
        # down. Report it as the partial state it is — a success line here
        # would send the operator away from a stranded coord worktree/branch.
        console.print(f"[red]Error:[/red] coordination teardown incomplete: {exc}")
        raise typer.Exit(1) from exc

    # -- Post-merge: WP07/FR-007 retrospective postcondition (fail-open) --
    run_retrospective_postcondition(mission_slug=resolved_mission, repo_root=repo_root)

    # -- Post-merge: suggest mission review + retrospective review/synthesis --
    console.print(
        "\n[cyan]Next:[/cyan] Run [bold]/spec-kitty-mission-review[/bold] to audit the merged mission for spec→code fidelity, drift, risks, and security."
    )
    console.print(
        "[cyan]Then, while context is fresh, review the retrospective that was"
        " captured at terminus:[/cyan]\n"
        "  [bold]spec-kitty retrospect summary[/bold] — cross-mission view\n"
        f"  [bold]spec-kitty agent retrospect synthesize --mission {resolved_mission}[/bold]"
        " — apply staged proposals (dry-run; add --apply to mutate)"
    )


@require_main_repo
def merge(
    strategy: MergeStrategy | None = typer.Option(
        None,
        "--strategy",
        help="Strategy for the branch-integration step (git merge of mission\u2192target): merge | squash | rebase. Default: squash.",
    ),
    delete_branch: bool | None = typer.Option(
        None,
        "--delete-branch/--keep-branch",
        help=(
            "Delete lane branches after merge. Unset (the default) defers to the "
            "mission's meta.json retention policy (#3131), falling back to "
            "delete when no policy is recorded. Passing either flag explicitly "
            "always wins over the mission's policy."
        ),
    ),
    remove_worktree: bool | None = typer.Option(
        None,
        "--remove-worktree/--keep-worktree",
        help=(
            "Remove lane worktrees after merge. Unset (the default) defers to "
            "the mission's meta.json retention policy (#3131), falling back to "
            "remove when no policy is recorded. Passing either flag explicitly "
            "always wins over the mission's policy."
        ),
    ),
    push: bool = typer.Option(False, "--push", help="Publish to origin after the local merge (the operator publish step; distinct from local lane consolidation)"),
    target_branch: str = typer.Option(None, "--target", help="Target branch for the branch-integration step (auto-detected)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without executing"),
    json_output: bool = typer.Option(False, "--json", help="Output deterministic JSON (dry-run mode)"),
    mission: str = typer.Option(None, "--mission", help="Mission slug when merging from main branch"),
    resume: bool = typer.Option(False, "--resume", help="Resume an interrupted merge from the last incomplete WP"),
    abort: bool = typer.Option(False, "--abort", help="Abort an in-progress merge, cleaning up state and worktrees"),
    context_token: str = typer.Option(None, "--context", help="Unused compatibility flag"),
    keep_workspace: bool = typer.Option(False, "--keep-workspace", help="Unused compatibility flag"),
    allow_sparse_checkout: bool = typer.Option(
        False,
        "--allow-sparse-checkout",
        help=("Proceed even if legacy sparse-checkout state is detected. Use of this override is logged. Does not bypass the commit-time data-loss backstop."),
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Proceed after merge warnings without prompts"),
    skip_review_artifact_check: bool = typer.Option(
        False,
        "--skip-review-artifact-check",
        help=(
            "Bypass the review-artifact consistency gate (the #2959 escape hatch). "
            "Requires --note; the skip is recorded as durable override evidence in "
            "the status log, never a silent bypass."
        ),
    ),
    note: str | None = typer.Option(
        None,
        "--note",
        help="Reason recorded as override evidence when using --skip-review-artifact-check (required with it).",
    ),
    skip_lanes: bool = typer.Option(
        False,
        "--skip-lanes",
        "--no-lanes",
        help=(
            "Complete a merge-ready direct-on-target mission that has no lane "
            "branch (#2745, FR-012): when lanes.json is genuinely absent, "
            "synthesize a no-lane manifest instead of hard-failing with the "
            "missing-lanes error. A mission that has real lanes is unaffected "
            "-- an existing lanes.json is always honored as-is. Does NOT "
            "bypass the merge-ready precondition: a not-merge-ready mission "
            "still refuses before any mutation."
        ),
    ),
) -> None:
    """Merge a lane-based mission into its target branch."""
    del context_token, keep_workspace

    # #2959 escape hatch — a skip is never silent: refuse it without a reason
    # BEFORE any merge work runs, so the evidence record always carries a note.
    if skip_review_artifact_check and not (note and note.strip()):
        console.print('[red]Error:[/red] --skip-review-artifact-check requires --note "<reason>" so the bypass is recorded as override evidence.')
        raise typer.Exit(2)
    # --note only carries meaning as the reason for a skip; passed alone it is
    # inert. Warn rather than fail so a stray flag never blocks a merge (squad note).
    if note and note.strip() and not skip_review_artifact_check:
        console.print(
            "[yellow]Note:[/yellow] --note has no effect without --skip-review-artifact-check; it is only recorded when the review-artifact gate is bypassed."
        )

    if not json_output:
        show_banner()

    try:
        repo_root = find_repo_root()
    except TaskCliError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if abort:
        _dispatch_abort(repo_root, mission)
        return

    if resume:
        mission = _dispatch_resume(repo_root, mission, json_output=json_output)
        # Fall through to the normal merge flow which will detect the state.
        # FOLD-F2 (terminus-safety-invariant-01M2XFT7, T021/FR-012): a
        # genuinely-lanes.json-absent direct-on-target mission's
        # --skip-lanes/--no-lanes choice must survive --resume without the
        # operator re-passing the flag -- the lanes-manifest decision below
        # runs BEFORE MergeState is loaded inside the executor, so recover
        # the persisted choice here and OR it into this invocation's flag.
        resumed_state = _load_merge_state_for_mission(repo_root, mission)
        if resumed_state is not None and resumed_state.skip_lanes:
            skip_lanes = True

    _enforce_git_preflight(repo_root, json_output=json_output)

    # T009 — FR-005/FR-006: Resolve strategy: CLI flag > config > default (SQUASH)
    resolved_strategy: MergeStrategy = strategy or load_merge_config(repo_root).strategy or MergeStrategy.SQUASH

    resolved_mission = _resolve_slug_or_exit(repo_root, mission)

    # FR-004/FR-005: refuse an unknown ``--mission`` handle with the canonical
    # not-found BEFORE the lanes load (which would otherwise raise the misleading
    # "lanes.json is required …" MissingLanesError). Confined to this fresh caller
    # (and ``_dispatch_resume``) — never the shared ``_resolve_slug_or_exit`` — so
    # ``merge --abort`` keeps tolerating a partial-state, dir-gone handle. Scoped to
    # the fresh flow (``not resume``): the resume flow has its OWN gate in
    # ``_dispatch_resume`` and, when it adopts a slug from active merge state, that
    # mission is known-good — re-probing the dir here would wrongly reject it.
    if not resume and resolved_mission and not _resolved_mission_dir_exists(repo_root, resolved_mission):
        error_msg = mission_not_found_message(resolved_mission)
        if json_output:
            print(json.dumps({"spec_kitty_version": SPEC_KITTY_VERSION, "error": error_msg}))
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)

    # T004: Auto-detect existing state when running merge without --resume
    if not resume and resolved_mission:
        existing_state = load_state(repo_root, resolved_mission)
        if existing_state is not None and existing_state.remaining_wps:
            console.print(
                f"[bold cyan]Detected interrupted merge[/bold cyan] for {resolved_mission} "
                f"({len(existing_state.completed_wps)}/{len(existing_state.wp_order)} WPs done). "
                "Auto-resuming."
            )

    try:
        resolved_target_branch, target_source = _resolve_target_branch(repo_root, resolved_mission, target_branch)
    except MissionMetaReadError as exc:
        # FR-005 fail-closed: a corrupt/unreadable meta.json must abort the merge
        # with a clean, visible error and non-zero exit — never a raw traceback,
        # and never a silent fall-through to the repo default branch. The error
        # is surfaced (corruption visible), not swallowed.
        error_msg = f"Cannot resolve the merge target branch: {exc}. meta.json exists but is corrupt or unreadable; fix it before merging."
        if json_output:
            print(json.dumps({"spec_kitty_version": SPEC_KITTY_VERSION, "error": error_msg}))
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1) from exc
    _validate_target_branch(
        repo_root,
        resolved_mission,
        resolved_target_branch,
        target_source,
        json_output=json_output,
    )

    if json_output and not dry_run:
        print(
            json.dumps(
                {
                    "spec_kitty_version": SPEC_KITTY_VERSION,
                    "error": "--json is currently supported with --dry-run only.",
                }
            )
        )
        raise typer.Exit(1)

    if resolved_mission:
        _enforce_retention_cleanup(
            repo_root,
            resolved_mission,
            delete_branch=delete_branch,
            remove_worktree=remove_worktree,
            json_output=json_output,
        )

    if dry_run:
        # WP06 (#2057): the dry-run preview + payload build lives in the
        # ``forecast`` seam. Behavior + JSON key set preserved byte-for-byte
        # (FR-001, FR-004); ``run_dry_run_forecast`` terminates the dry-run path.
        #
        # #3131 FR-008: the RAW tri-state flags are threaded through so the
        # forecast resolves the effective cleanup decision through
        # ``resolve_merge_retention`` (against the mission's primary meta.json)
        # exactly as the real merge path does. An unset flag (``None``) therefore
        # lets a mission's retention policy govern the preview — the dry-run
        # forecast now reflects the resolved retain/delete decision, not the
        # pre-#3131 delete/remove default.
        run_dry_run_forecast(
            repo_root=repo_root,
            resolved_feature=resolved_mission,
            resolved_target_branch=resolved_target_branch,
            resolved_strategy=resolved_strategy,
            delete_branch=delete_branch,
            remove_worktree=remove_worktree,
            push=push,
            json_output=json_output,
        )
        return

    if not resolved_mission:
        console.print("[red]Error:[/red] Mission slug could not be resolved. Use --mission <slug>.")
        raise typer.Exit(2)

    _run_real_merge(
        repo_root,
        resolved_mission=resolved_mission,
        resolved_target_branch=resolved_target_branch,
        resolved_strategy=resolved_strategy,
        delete_branch=delete_branch,
        remove_worktree=remove_worktree,
        push=push,
        allow_sparse_checkout=allow_sparse_checkout,
        yes=yes,
        skip_review_artifact_check=skip_review_artifact_check,
        skip_note=note,
        skip_lanes=skip_lanes,
    )


__all__ = [
    "_has_transition_to",
    "_assert_merged_wps_reached_done",
    "_assert_merged_wps_done_on_target",
    "_reconcile_completed_wps_for_resume",
    "_assert_baseline_merge_commit_on_target",
    "_record_baseline_merge_commit",
    "_recorded_baseline_from_working_meta",
    "_read_committed_meta_json",
    "BaselineMergeCommitError",
    "_mark_wp_merged_done",
    "_project_status_bookkeeping_to_target",
    "_validate_mission_slug_path_segment",
    "_target_bookkeeping_status_paths",
    "_assert_status_path_within_target_surface",
    "_assert_status_surface_path_is_trusted",
    "_target_branch_still_at_baseline",
    "_load_merge_state_for_mission",
    "_load_or_create_merge_state",
    "_clear_merge_state_for_mission",
    "_run_lane_based_merge",
    "_run_lane_based_merge_locked",
    "_classify_porcelain_lines",
    "_lane_already_integrated",
    "_raw_porcelain_status",
    "_paths_have_status_changes",
    "_resolve_merge_actor",
    "_refresh_primary_checkout_after_merge",
    "_effective_push_requested",
    "_enforce_canonical_status_history",
    "_enforce_planning_artifact_target_branch",
    "_warn_or_confirm_hollow_reviews",
    "_is_linear_history_rejection",
    "_emit_remediation_hint",
    "_branch_trees_equal",
    "_check_mission_branch",
    "_has_branch_ref",
    "_is_git_repo",
    "_enforce_target_branch_sync_preflight",
    "_enforce_review_artifact_consistency",
    "_collect_hollow_review_warnings",
    "_target_branch_sync_payload",
    "_bake_mission_number_into_mission_branch",
    "target_branch_sync_remediation",
    "TARGET_BRANCH_NOT_SYNCHRONIZED",
    "TARGET_BRANCH_SYNC_INVARIANT",
    "_STATUS_EVENTS_FILENAME",
    "_STATUS_FILENAME",
    "MissionBranchBlocker",
    "HollowReviewWarnings",
    "LINEAR_HISTORY_REJECTION_TOKENS",
    "path_is_under_worktrees",
    "merge",
]
