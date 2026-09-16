"""I/O-heavy executor phases for the ``agent/workflow.py`` decomposition (WP02, T008).

coord-authority-trio-degod-01KX7094: the counterpart to
``workflow_cores.py`` -- this module holds the pieces of ``implement()`` /
``review()`` that open worktrees, run git, read/write status artifacts, or
otherwise touch the outside world. ``implement``/``review``/
``_resolve_review_context`` themselves stay defined in ``workflow.py`` (the
Typer-shell layer) and call these phase functions in sequence.

Monkeypatch-safety (load-bearing, read before editing): several existing
test files replace names via ``monkeypatch.setattr(workflow, "<name>",
...)`` / ``monkeypatch.setattr(workflow_module, "<name>", ...)`` /
``unittest.mock.patch("specify_cli.cli.commands.agent.workflow.<name>",
...)`` / ``patch.object(workflow_module, "<name>", ...)`` (catalogued by an
exhaustive repo-wide grep across ALL FOUR patch idioms before this split):
``_commit_via_coordination_transaction``, ``_commit_workflow_change``,
``build_charter_context``, ``feature_status_lock``, ``get_main_repo_root``,
``is_worktree_context``, ``_load_coord_branch_meta``, ``locate_project_root``,
``locate_work_package``, ``resolve_planning_read_dir``,
``resolve_workspace_for_wp``, ``_revert_coordination_commit``,
``safe_commit``, ``_sync_lane_after_coordination_commit``,
``top_level_implement``. A bare
``from specify_cli.cli.commands.agent.workflow import <name>`` at this
module's top level would FREEZE a reference to the pre-patch function
object at import time -- a test's ``monkeypatch.setattr(workflow, ...)``
mutates ``workflow.__dict__``, which a frozen import never re-reads.  Every
call in this module into a name still defined in ``workflow.py`` therefore
goes through :func:`_wf`, a lazy accessor that re-reads
``workflow.__dict__`` on every call (the same pattern ``workflow.py``'s own
``_workflow_placement_seam`` already uses for ``mission_runtime.
placement_seam``) -- this is also what avoids a circular import at module
load time (``workflow.py`` imports this module for its re-export shims).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, NoReturn, cast

import typer

from mission_runtime import MissionArtifactKind, placement_seam
from specify_cli.cli.commands.agent.workflow_cores import (
    build_owned_files_review_pathspecs,
    has_prior_rejection,
    is_missing_canonical_status_error,
    missing_canonical_status_message,
    render_isolation_banner,
    render_resolved_agent_identity,
    render_wp_prompt_wrapper,
    resolve_review_feedback_context,
    shared_artifact_guidance,
    workspace_contract_description,
)
from specify_cli.core.constants import MISSION_TYPE_RESEARCH
from specify_cli.mission import get_deliverables_path, get_mission_type
from specify_cli.status import Lane, WorkPackageClaimConflict, WorkPackageStartRejected, read_wp_frontmatter
from specify_cli.task_utils import extract_scalar
from specify_cli.workspace.context import ResolvedWorkspace, husk_resolution_error

if TYPE_CHECKING:
    from specify_cli.status import AgentAssignment
    from specify_cli.status.resolved_binding import ResolvedBinding
    from specify_cli.status.wp_metadata import WPMetadata
    from specify_cli.task_utils import WorkPackage

logger = logging.getLogger(__name__)


def _wf() -> ModuleType:
    """Lazy accessor for the ``workflow`` module -- see module docstring.

    Explicit local annotation re-narrows the import from ``Any`` back to
    ``ModuleType`` -- the project's ``follow_imports = "skip"`` mypy config
    for ``specify_cli.*`` (pyproject.toml) means a cross-module late import
    is otherwise seen as ``Any`` (the same pattern documented in
    ``missions/_read_path_resolver.py``).
    """
    from specify_cli.cli.commands.agent import workflow as _workflow_module

    module: ModuleType = _workflow_module
    return module


def _claim_policy_metadata(shell_pid: int, agent: str) -> dict[str, Any]:
    """Best-effort ``policy_metadata`` triple for a claim transition (WP07/T026-T027).

    Routes the ``(shell_pid, shell_pid_created_at, agent)`` triple onto the
    claim transition's ``policy_metadata`` sidecar (FR-004) using WP01's
    :func:`~specify_cli.status.emit.build_claim_policy_metadata` builder --
    the exact key names WP01's reducer fold (``planned -> claimed``) reads.

    ``shell_pid_created_at`` capture is best-effort (C-007): when
    :func:`~specify_cli.core.process_liveness.capture_creation_time_baseline`
    cannot capture a baseline, the key is OMITTED (never fails the claim,
    D3a legacy-claim semantics) rather than calling the builder with a
    fabricated value.
    """
    from specify_cli.core.process_liveness import capture_creation_time_baseline
    from specify_cli.status import build_claim_policy_metadata

    baseline = capture_creation_time_baseline(shell_pid)
    if baseline is None:
        return {"shell_pid": shell_pid, "agent": agent}
    # Explicit local annotation re-narrows the import from ``Any`` back to
    # ``dict[str, Any]`` -- the project's ``follow_imports = "skip"`` mypy
    # config for ``specify_cli.*`` means a cross-module late import is
    # otherwise seen as ``Any`` (same pattern as :func:`_wf` above).
    metadata: dict[str, Any] = build_claim_policy_metadata(shell_pid=shell_pid, shell_pid_created_at=baseline, agent=agent)
    return metadata


def _locate_wp(repo_root: Path, mission_slug: str, normalized_wp_id: str) -> WorkPackage:
    """Typed accessor for ``workflow.locate_work_package`` (#2675 T054).

    ``_wf()`` returns ``ModuleType``, so ``.locate_work_package(...)`` leaks
    ``Any`` through every call site. This is the ONE sanctioned ``cast`` in
    this module -- every ``locate_work_package`` call site (erroring or not)
    routes through here instead of scattering casts at each read site.
    """
    return cast(
        "WorkPackage",
        _wf().locate_work_package(repo_root, mission_slug, normalized_wp_id),
    )


# ---------------------------------------------------------------------------
# T008 -- the two functions the WP names explicitly
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _CommitFailureContext:
    """The status-artifact rollback inputs threaded to :func:`_handle_commit_failure`.

    coord-commit-integrity (campsite, Sonar S107): bundles the four rollback
    coordinates — the event-log path + its pre-emit size and the status-snapshot
    path + its pre-emit bytes — that ``_restore_status_artifacts`` needs to
    truncate/restore the artifacts to their pre-emit state. Both ``except`` arms
    in :func:`commit_workflow_change` share one identical instance, so the
    failure handler takes this frozen bundle plus only the arm-specific fields.
    """

    events_path: Path
    pre_emit_event_size: int
    status_path: Path
    pre_emit_status_bytes: bytes | None


def _handle_commit_failure(
    *,
    exc: Exception,
    receipt_ref: str,
    message: str,
    wp_id: str,
    rollback: _CommitFailureContext,
    error_prefix: str,
    include_recovery_note: bool,
) -> NoReturn:
    """Roll back status artifacts, record a ``refused`` receipt, surface, exit.

    coord-commit-integrity WP01/T002 (campsite): the shared body of the two
    copy-paste ``except`` arms in :func:`commit_workflow_change` (the
    BookkeepingTransaction arm and the legacy ``safe_commit`` arm). Extracted
    verbatim so adding the T003 misroute guard does not push
    ``commit_workflow_change`` over the complexity ceiling.

    When a chained ``safe_commit`` recovery already created a commit
    (``_safe_commit_recovery_commit_sha`` returns a SHA) the status artifacts
    are NOT rolled back (the commit is real); otherwise the event log / status
    snapshot are restored to their pre-emit bytes (from ``rollback``).
    ``error_prefix`` is the arm-specific message head (``": {exc}"`` is always
    appended); the legacy arm additionally appends a recovery note
    (``include_recovery_note``).
    """
    w = _wf()
    recovery_commit_sha = w._safe_commit_recovery_commit_sha(exc)
    if recovery_commit_sha is None:
        w._restore_status_artifacts(
            events_path=rollback.events_path,
            pre_emit_event_size=rollback.pre_emit_event_size,
            status_path=rollback.status_path,
            pre_emit_status_bytes=rollback.pre_emit_status_bytes,
        )
    w._record_receipt(
        receipt_ref,
        message,
        "refused",
        sha=recovery_commit_sha,
        wp_id=wp_id,
    )
    error_text = f"{error_prefix}: {exc}"
    if include_recovery_note:
        recovery_note = (
            "Commit was created before staging recovery failed; status artifacts were not rolled back."
            if recovery_commit_sha is not None
            else "Event log rolled back to pre-emit state."
        )
        error_text = f"{error_text}. {recovery_note}"
    print(error_text)
    raise typer.Exit(1) from exc


def commit_workflow_change(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    target_branch: str,
    paths: list[Path],
    message: str,
    operation: str,
    wp_id: str,
    pre_emit_event_size: int,
    pre_emit_status_bytes: bytes | None,
    auto_rebase_lane_after_commit: bool = False,
) -> None:
    """Commit a workflow change with atomic event-log rollback on failure.

    For modern (post-WP03) missions with ``coordination_branch`` in
    meta.json, routes through :class:`BookkeepingTransaction` so the
    event-log append is atomically reversible (FR-010, FR-011) and the
    commit lands on the coordination branch (FR-005).

    For legacy missions without ``coordination_branch``, falls back to
    the bare :func:`safe_commit` path but still truncates the event log
    on commit failure to ``pre_emit_event_size``. WP08 will replace this
    fallback with a proper legacy bridge.

    Records the outcome via ``_record_receipt`` so the T029 terminal
    summary can render it.

    Raises:
        typer.Exit(1): On commit failure (after rollback).
    """
    w = _wf()

    # #2508 fix (FR-010, the #2160-class read-source bug): ``feature_dir`` is
    # the STATUS_STATE-partition read (a coord-topology mission's coord
    # WORKTREE, per ``_canonical_status_feature_dir``) -- but ``meta.json`` is
    # ``PRIMARY_METADATA``, a PRIMARY-partition kind that lives ONLY on the
    # primary checkout (mirrors ``worktree_allocator._read_coordination_branch``
    # and the dozen other ``MissionArtifactKind.PRIMARY_METADATA`` read sites).
    # A coord worktree's checked-out ``meta.json`` snapshot can be stale, absent,
    # or predate the ``coordination_branch`` field -- reading identity off it
    # silently returns ``(None, None, None)`` and misfires the legacy
    # ``safe_commit`` fallback below even for a genuine coord-topology mission.
    # Anchor this read on the primary surface via the same kind-aware seam
    # every other identity read in this module already uses.
    primary_meta_dir = w._resolve_workflow_read_dir(
        repo_root=repo_root, mission_slug=mission_slug, kind=MissionArtifactKind.PRIMARY_METADATA
    )
    coord_branch, mission_id, mid8 = w._load_coord_branch_meta(primary_meta_dir)
    events_path = feature_dir / w._STATUS_EVENTS_FILENAME
    status_path = feature_dir / w._STATUS_FILENAME
    rollback_ctx = _CommitFailureContext(
        events_path=events_path,
        pre_emit_event_size=pre_emit_event_size,
        status_path=status_path,
        pre_emit_status_bytes=pre_emit_status_bytes,
    )
    # T017: the seam-resolved STATUS_STATE placement. The MECHANISM choice
    # below (BookkeepingTransaction vs. the legacy safe_commit fallback) still
    # keys off ``_load_coord_branch_meta`` — it needs the concrete
    # ``mission_id``/``mid8`` identity fields the transaction requires, which
    # the seam's ref-only CommitTarget does not carry. But the legacy leaf's
    # DESTINATION ref is threaded from this ONE resolution rather than the
    # raw, un-seam-resolved ``target_branch`` parameter (C-001).
    placement = w._resolve_workflow_placement(
        repo_root=repo_root, mission_slug=mission_slug, kind=MissionArtifactKind.STATUS_STATE
    )
    if placement.ref != target_branch:
        # Diagnostic only (never authoritative): the seam is the single
        # placement authority (C-001); ``target_branch`` is whatever ref the
        # caller had checked out (:func:`_ensure_target_branch_checked_out`
        # tracks the user's CURRENT branch, not necessarily the mission's
        # canonical target). A divergence here is exactly the ad hoc-vs-seam
        # drift this mission exists to surface.
        logger.debug(
            "_commit_workflow_change: seam-resolved STATUS_STATE placement %r "
            "diverges from the caller-supplied target_branch %r for mission %r",
            placement.ref,
            target_branch,
            mission_slug,
        )

    if coord_branch and mission_id and mid8:
        try:
            receipt = w._commit_via_coordination_transaction(
                coord_branch=str(coord_branch),
                repo_root=repo_root,
                mission_id=str(mission_id),
                mission_slug=mission_slug,
                mid8=str(mid8),
                paths=paths,
                message=message,
                operation=operation,
                wp_id=wp_id,
            )
        except typer.Exit:
            w._restore_status_artifacts(
                events_path=events_path,
                pre_emit_event_size=pre_emit_event_size,
                status_path=status_path,
                pre_emit_status_bytes=pre_emit_status_bytes,
            )
            raise
        except Exception as exc:  # noqa: BLE001 — surface + exit
            _handle_commit_failure(
                exc=exc,
                receipt_ref=str(coord_branch),
                message=message,
                wp_id=wp_id,
                rollback=rollback_ctx,
                error_prefix=f"Error: Failed to record {operation} via BookkeepingTransaction",
                include_recovery_note=False,
            )
        if auto_rebase_lane_after_commit:
            try:
                w._sync_lane_after_coordination_commit(
                    repo_root=repo_root,
                    mission_slug=mission_slug,
                    wp_id=wp_id,
                    coord_branch=str(coord_branch),
                )
            except Exception as exc:  # noqa: BLE001 — structured sync refusal
                try:
                    w._revert_coordination_commit(receipt)
                    w._mark_receipt_refused(commit_sha=receipt.commit_sha)
                    w._restore_status_artifacts(
                        events_path=events_path,
                        pre_emit_event_size=pre_emit_event_size,
                        status_path=status_path,
                        pre_emit_status_bytes=pre_emit_status_bytes,
                    )
                except Exception as rollback_exc:  # noqa: BLE001
                    print(f"Error: Failed to rollback lifecycle state after lane sync refusal: {rollback_exc}")
                w._render_lane_auto_rebase_failure(exc)
                raise typer.Exit(1) from exc
        return

    # FR-002(a) misroute-to-legacy guard (WP01/T003, #2861). We only reach here
    # when the modern branch above was NOT taken, i.e. the identity triple is
    # incomplete (``mission_id``/``mid8`` unresolved). If ``coord_branch`` is
    # nonetheless present, this is a COORD-routed topology with a corrupt/partial
    # identity: falling through to ``_commit_via_legacy_safe_commit`` would commit
    # coordination artifacts from ``repo_root`` (whose HEAD is the caller's target
    # branch, not the coord branch) — the silent-misroute class behind #2861
    # (either a ``SafeCommitHeadMismatch`` or, worse, a phantom "already
    # committed" no-op over gitignored ``.worktrees/`` paths). Fail loud instead;
    # never route coord paths through the legacy repo_root leaf.
    if coord_branch:
        print(
            f"Error: coord-commit misroute prevented for {wp_id}: mission "
            f"{mission_slug!r} declares coordination_branch {str(coord_branch)!r} but "
            f"its identity triple is incomplete (mission_id/mid8 unresolved). Refusing "
            f"to commit coordination artifacts from the repository root. Repair "
            f"meta.json (mission_id/mid8) and retry."
        )
        raise typer.Exit(1)

    # Legacy fallback (TODO(WP08): replace with the legacy bridge). Genuinely
    # coord-less (no coordination_branch) — the mission's paths live in
    # ``repo_root``; ``_commit_via_legacy_safe_commit`` resolves the porcelain
    # pre-check root from (mission_slug, mid8) for FR-002(b) robustness.
    try:
        w._commit_via_legacy_safe_commit(
            repo_root=repo_root,
            target_branch=placement.ref,
            paths=paths,
            message=message,
            wp_id=wp_id,
            mission_slug=mission_slug,
            mid8=mid8,
        )
    except Exception as exc:  # noqa: BLE001 — surface + truncate + exit
        _handle_commit_failure(
            exc=exc,
            receipt_ref=placement.ref,
            message=message,
            wp_id=wp_id,
            rollback=rollback_ctx,
            error_prefix=f"Error: Failed to commit workflow status update for {wp_id}",
            include_recovery_note=True,
        )


def ensure_workspace_materialized(
    workspace: ResolvedWorkspace,
    wp_id: str,
    create_workspace: Callable[[], None],
    reenter_self_heal: Callable[[], None],
) -> None:
    """Ensure the already-resolved *workspace* is materialized on disk.

    FR-008/#1832 (C-IC05) — single resolution path. *workspace* is the
    canonical resolution produced once by the caller. This helper consumes that
    resolved context; it never re-runs ``resolve_workspace_for_wp``. A husk
    (path present, no ``.git``) is absent-but-blocked (#1833). When the
    workspace does not yet exist, *create_workspace* is invoked to materialize
    the worktree at the already-resolved path; ``ResolvedWorkspace.exists`` then
    re-stats disk, so the same contract reflects the freshly-created worktree.
    A second resolution authority — which could independently report "no
    workspace could be resolved" on a verified read-path — is exactly what this
    function eliminates.

    FR-005/#3281 (C-006): when the workspace already exists, *reenter_self_heal*
    is invoked instead of a bare early return — a retry over a leftover lane
    worktree (missing the recorded planning SHA, or an approved dependency-lane
    tip merged after this worktree was created) must re-enter the allocator's
    idempotent reuse-path self-heal, not silently short-circuit. This does NOT
    break the #1832/#1833 single-resolution invariant: *create_workspace* (a
    SECOND resolution authority / full ``top_level_implement``) still never
    runs when the workspace exists — only the dedicated, already-idempotent
    self-heal callable does, and it is a true no-op resume when the workspace's
    ancestry is already correct (the merge helpers' own
    ``git merge-base --is-ancestor`` short-circuit makes "ancestry-correct" and
    "stale" converge on the same call with different observable effect).

    A pure side-effect seam: it mutates disk (and re-stats the resolved context
    in place) but returns nothing — the caller already holds the canonical
    ``ResolvedWorkspace`` and must not rebind it to a second value.

    Raises:
        typer.Exit: husk detected, creation attempted from a worktree, the
            path was not materialized after creation, or self-heal raised.
    """
    if workspace.is_husk:
        print(f"Error: {husk_resolution_error(workspace.worktree_path)}")
        raise typer.Exit(1)

    if workspace.exists:
        try:
            reenter_self_heal()
        except typer.Exit:
            raise
        except Exception as e:
            print(f"Error self-healing workspace for {wp_id}: {e}")
            raise typer.Exit(1) from e
        return

    cwd = Path.cwd().resolve()
    if _wf().is_worktree_context(cwd):
        print("Error: Workspace does not exist and cannot be created from a worktree.")
        print("Run this command from the main repository:")
        print(f"  spec-kitty agent action implement {wp_id} --agent <your-name>")
        raise typer.Exit(1)

    print(f"Creating workspace for {wp_id}...")
    try:
        create_workspace()
    except typer.Exit:
        # Worktree creation failed - propagate error
        raise
    except Exception as e:
        print(f"Error creating worktree: {e}")
        raise typer.Exit(1) from e

    # Single resolution path: re-stat the already-resolved workspace; do NOT
    # re-resolve via a second authority.
    if not workspace.exists:
        print(
            f"Error: implement completed but the workspace at {workspace.worktree_path} "
            f"for {wp_id} was not materialized."
        )
        raise typer.Exit(1)


def render_charter_context_text(
    repo_root: Path, action: str, *, mission_type: str | None = None
) -> str:
    """Render charter context for workflow prompts.

    WP11 (T062/B-8/FR-012): ``mission_type`` is forwarded to
    ``build_charter_context`` so the action doctrine bundle resolves for the
    mission's grain. Without it the grain is typeless and degrades to an empty
    bundle (FR-003a) — governance declared but not delivered.
    """
    try:
        context = _wf().build_charter_context(
            repo_root, action=action, mark_loaded=True, mission_type=mission_type
        )
        text: str = context.text
        return text
    except Exception as exc:
        return f"Governance: unavailable ({exc})"


# ---------------------------------------------------------------------------
# Shared: writing a full prompt to the scoped /tmp namespace
# ---------------------------------------------------------------------------


def write_prompt_to_file(
    command_type: str,
    mission_slug: str,
    wp_id: str,
    content: str,
    *,
    repo_root: Path,
) -> Path:
    """Write full prompt content to a temp file for agents with output limits.

    The filename is scoped by ``mission_slug`` so that concurrent missions
    sharing a WP id (e.g. two missions both with ``WP01``) do not collide on the
    same ``/tmp`` path and overwrite each other's prompt (#1831).
    """
    from runtime.next._tmp_namespace import prompt_tmp_dir

    prompt_file = (
        prompt_tmp_dir(repo_root)
        / f"spec-kitty-{command_type}-{mission_slug}-{wp_id}.md"
    )
    prompt_file.write_text(content, encoding="utf-8")
    return prompt_file


# ---------------------------------------------------------------------------
# ``implement()`` phase extractions (T009)
# ---------------------------------------------------------------------------


def implement_sparse_checkout_preflight(
    repo_root: Path, mission_slug: str, agent: str | None, allow_sparse_checkout: bool
) -> None:
    """WP05/T021 FR-007: sparse-checkout preflight, run before any worktree
    creation or state change. Raises ``typer.Exit(1)`` on refusal.

    *repo_root* is already the main repo root by the time ``implement()``
    calls this (resolved via ``get_main_repo_root`` at the top of the
    command) — re-deriving it here would be idempotent, so this phase takes
    it as given rather than re-calling ``get_main_repo_root``.
    """
    from specify_cli.git.sparse_checkout import SparseCheckoutPreflightError, require_no_sparse_checkout
    from specify_cli.mission_metadata import resolve_mission_identity

    mission_id_for_preflight: str | None = None
    try:
        # FR-005 (#2186): anchor the preflight ``mission_id`` on the PRIMARY
        # checkout. The kind-blind coord-aware resolvers
        # (``candidate_feature_dir_for_mission`` / ``resolve_feature_dir_for_mission``)
        # land on the STATUS-only husk (no meta.json) — a wrong/empty id for the
        # sparse-checkout override log. read-side-seam-primary-primitive-closure-01KYKMMT
        # WP05/FR-004: routed through the kind-aware seam instead — PRIMARY_METADATA
        # is a PRIMARY-partition kind, so it short-circuits to PRIMARY before any
        # coord probe and never lands on that husk.
        identity = resolve_mission_identity(
            placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        )
        mission_id_for_preflight = identity.mission_id
    except Exception:  # noqa: BLE001 — meta.json may not exist for legacy missions
        mission_id_for_preflight = None

    try:
        require_no_sparse_checkout(
            repo_root=repo_root,
            command="spec-kitty agent action implement",
            override_flag=allow_sparse_checkout,
            actor=agent,
            mission_slug=mission_slug,
            mission_id=mission_id_for_preflight,
        )
    except SparseCheckoutPreflightError as exc:
        # Surface as a user-facing error. No worktree is created.
        print(f"Error: {exc}")
        raise typer.Exit(1) from exc


def implement_locate_wp(repo_root: Path, mission_slug: str, normalized_wp_id: str) -> WorkPackage:
    """Find the WP file, translating the canonical-status-missing case."""
    try:
        return _locate_wp(repo_root, mission_slug, normalized_wp_id)
    except RuntimeError as e:
        if is_missing_canonical_status_error(e):
            print(f"Error: {missing_canonical_status_message(normalized_wp_id, mission_slug)}")
            raise typer.Exit(1) from e
        print(f"Error locating work package: {e}")
        raise typer.Exit(1) from e
    except Exception as e:
        print(f"Error locating work package: {e}")
        raise typer.Exit(1) from e


def implement_check_wp_charter_precondition(main_repo_root: Path, wp: WorkPackage, normalized_wp_id: str) -> None:
    """C-006 charter precondition: check BEFORE any worktree creation or status transition."""
    wp_profile = extract_scalar(getattr(wp, "frontmatter", None) or "", "agent_profile")
    if not wp_profile:
        return

    from charter.activation.exceptions import CharterActivationError
    from charter.activation.invocation_context import ProjectContext

    pack_ctx = ProjectContext.from_repo(main_repo_root).require_pack_context()
    activated = pack_ctx.activated_agent_profiles
    if activated is not None and wp_profile not in activated:
        activated_list = ", ".join(sorted(activated)) or "(none)"
        resolution_cmd = f"spec-kitty charter activate agent-profile {wp_profile}"
        print(
            f"Error: WP{normalized_wp_id} charter precondition FAILED\n"
            f"  Assigned profile '{wp_profile}' is not accessible through "
            f"the active charter.\n"
            f"  Currently activated: {activated_list}\n"
            f"  Run: {resolution_cmd}"
        )
        raise CharterActivationError(
            f"artifact={wp_profile!r}, "
            f"activated={activated_list!r}, "
            f"resolution={resolution_cmd!r}"
        )


def implement_check_dependency_gate(
    main_repo_root: Path, mission_slug: str, normalized_wp_id: str, wp_meta: WPMetadata
) -> None:
    """Gate the not-yet-started claim transition on dependency readiness.

    Re-invoking implement on a WP that is already
    in_progress/for_review/.../approved (resume, prompt redisplay,
    fix-cycle) must not be rejected just because a dependency later
    regressed out of approved/done — the lifecycle treats those
    re-invocations as no-op resumes, not new claims.
    """
    from specify_cli.core.dependency_graph import dependency_readiness_for_wp
    from specify_cli.status import read_events as dep_read_events
    from specify_cli.status import reduce as dep_reduce_events
    from specify_cli.status import resolve_lane_alias as dep_resolve_alias

    w = _wf()
    dependency_feature_dir = w._canonical_status_feature_dir(main_repo_root, mission_slug)
    dependency_snapshot = dep_reduce_events(dep_read_events(dependency_feature_dir))
    dependency_lanes = {
        wp_id: state.get("lane", Lane.PLANNED) for wp_id, state in dependency_snapshot.work_packages.items()
    }
    if normalized_wp_id not in dependency_snapshot.work_packages:
        print(f"Error: {missing_canonical_status_message(normalized_wp_id, mission_slug)}")
        raise typer.Exit(1)

    try:
        self_lane = Lane(dep_resolve_alias(str(dependency_lanes.get(normalized_wp_id, Lane.PLANNED))))
    except ValueError:
        self_lane = Lane.PLANNED
    if self_lane not in (Lane.PLANNED, Lane.CLAIMED):
        return

    # Thread per-dependency provenance (the reduced snapshot state dicts) into
    # the gate so a canceled-with-operator-provenance dependency counts as
    # resolved (FR-009). Collapsing to the lane-only map here would make the
    # provenance-aware authority inert at the CLI claim path (pedro HIGH).
    # Pre-flight UX only (FR-014, fsm-write-path-integrity WP04). The authoritative
    # dependency gate is `GuardContext.dependency_ready`, resolved in-lock by the emit shells.
    readiness = dependency_readiness_for_wp(
        normalized_wp_id,
        wp_meta.dependencies,
        dependency_lanes,
        provenance=dependency_snapshot.work_packages,
    )
    if not readiness.satisfied:
        blocked = ", ".join(readiness.unsatisfied)
        print(
            f"Error: dependencies_not_satisfied: {normalized_wp_id} depends on {blocked}; "
            "all dependencies must be approved or done before implementation can start"
        )
        raise typer.Exit(1)


def implement_resolve_feedback_and_gate(
    main_repo_root: Path,
    mission_slug: str,
    normalized_wp_id: str,
    wp: WorkPackage,
) -> tuple[Path, bool, str | None, Path | None, str | None]:
    """Resolve the review-feedback context and enforce the analysis-report gate.

    Returns ``(feature_dir, has_feedback, review_feedback_ref,
    review_feedback_file, review_feedback_source)``.
    """
    w = _wf()

    # IC-04/T017: review-feedback-context READ. WORK_PACKAGE_TASK is a
    # PRIMARY-partition kind (review-cycle artifacts + this WP's baseline
    # artifact both live under tasks/<wp_slug>/, reused later at the
    # fix-mode and baseline-commit sites) — routes through the kind-aware
    # seam instead of the kind-blind coord husk (NFR-001 / Directive-041).
    feature_dir = w._resolve_workflow_read_dir(
        repo_root=main_repo_root, mission_slug=mission_slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK
    )
    has_feedback, review_feedback_ref, review_feedback_file, review_feedback_source = resolve_review_feedback_context(
        feature_dir=feature_dir,
        wp_id=normalized_wp_id,
        wp_frontmatter=getattr(wp, "frontmatter", "") or "",
    )

    if review_feedback_source == "canonical" and review_feedback_file is None:
        print(f"Error: {normalized_wp_id} review feedback artifact is missing or unreadable: {review_feedback_ref}")
        print("Re-run move-task with --review-feedback-file so the fix cycle can attach the canonical review artifact.")
        raise typer.Exit(1)

    # #1989 (read-side companion to WP01): read the report from the PRIMARY
    # checkout where record-analysis writes it (see _analysis_report_gate_dir).
    w._require_current_analysis_report(
        w._analysis_report_gate_dir(main_repo_root, mission_slug),
        main_repo_root,
        mission_slug,
    )

    return feature_dir, has_feedback, review_feedback_ref, review_feedback_file, review_feedback_source


def implement_resolve_mission_type(repo_root: Path, mission_slug: str) -> tuple[str, str | None]:
    """Resolve the mission type + (for research missions) the deliverables path.

    FR-005 (#2186): the mission TYPE is a meta.json read and meta.json lives
    ONLY on PRIMARY — always resolved off its OWN PRIMARY-anchored dir, not
    the STATUS-leg ``feature_dir`` the surrounding flow otherwise threads. The
    kind-blind coord-aware resolvers would land on the STATUS-only husk for a
    coord-topology mission (no meta.json there). read-side-seam-primary-
    primitive-closure-01KYKMMT WP05/FR-004: routed through the kind-aware seam
    instead — PRIMARY_METADATA is a PRIMARY-partition kind, so it resolves
    PRIMARY for every topology without ever consulting that husk.
    """
    mission_type_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    mission_type = get_mission_type(mission_type_dir)
    deliverables_path = None
    if mission_type == MISSION_TYPE_RESEARCH:
        deliverables_path = get_deliverables_path(mission_type_dir, mission_slug)
    return mission_type, deliverables_path


@dataclass(slots=True, kw_only=True)
class ImplementClaimResult:
    """Return value of :func:`implement_claim_transition`."""

    wp: WorkPackage
    current_lane: Lane
    fix_mode_active: bool
    wp_slug: str
    wp_agent_assignment: AgentAssignment


def _implement_start_claim(
    *,
    main_repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    normalized_wp_id: str,
    agent: str | None,
    wp_agent_assignment: AgentAssignment,
    current_lane: Lane,
    status_execution_mode: str,
    workspace_path: Path,
    resolved_binding: ResolvedBinding | None,
) -> str:
    """Emit the claim status event, guarded by the runtime operational-context
    precondition. Returns ``shell_pid``. Raises ``typer.Exit(1)`` on
    conflict/rejection.
    """
    import os

    from runtime.next.runtime_bridge import build_operational_context_for_claim
    from specify_cli.status import start_implementation_status
    from specify_cli.status import build_self_asserting_actor

    shell_pid = str(os.getppid())  # Parent process ID (the shell running this command)
    actor = agent or "unknown"
    # FR-005: route the compact ``--agent`` value through the single self-
    # asserting actor seam — only the parsed BARE tool reaches actor.tool, an
    # absent segment stays None (no synthetic default), and the dispatch
    # binding wins over the self-asserted parse.
    transition_actor = build_self_asserting_actor(
        role=_IMPLEMENT_CLAIM_ROLE,
        agent=agent,
        fallback_tool=wp_agent_assignment.tool,
        binding=resolved_binding,
    )

    # FR-017 / NFR-004: build and validate the runtime OperationalContext
    # via the shared claim builder BEFORE emitting the claim status event
    # or allocating any worktree. The builder is read-only; running its
    # guard here means a missing-context precondition failure aborts
    # before start_implementation_status, leaving zero new status events
    # and zero new worktree paths.
    operational_context = build_operational_context_for_claim(
        repo_root=main_repo_root,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=normalized_wp_id,
        actor=actor,
        active_model=(
            resolved_binding.model
            if resolved_binding is not None and resolved_binding.model is not None
            else wp_agent_assignment.model
        ),
        active_role=wp_agent_assignment.role or actor,
        current_activity="implement",
        active_profile=(
            resolved_binding.agent_profile
            if resolved_binding is not None
            else None
        ),
    )
    operational_context.require_active_role()

    try:
        start_implementation_status(
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            wp_id=normalized_wp_id,
            actor=transition_actor,
            workspace_context=f"{status_execution_mode}:{workspace_path}",
            execution_mode=status_execution_mode,
            repo_root=main_repo_root,
            allow_rework=current_lane in {Lane.FOR_REVIEW, Lane.APPROVED, Lane.IN_REVIEW},
            # WP07/T026 (FR-004/FR-014): the claim triple rides the
            # planned -> claimed transition's policy_metadata sidecar
            # instead of a separate WP-file write -- WP01's reducer folds
            # these exact keys into the reduced snapshot.
            policy_metadata=_claim_policy_metadata(int(shell_pid), actor),
            annotation_delta=(
                resolved_binding.to_delta(role=_IMPLEMENT_CLAIM_ROLE)
                if resolved_binding is not None
                else None
            ),
        )
    except WorkPackageClaimConflict as exc:
        print(f"Error: {exc}")
        raise typer.Exit(1) from exc
    except WorkPackageStartRejected as exc:
        print(f"Error: {exc}")
        raise typer.Exit(1) from exc

    return shell_pid


def _implement_write_claim_and_commit(
    *,
    wp: WorkPackage,
    agent: str | None,
    main_repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    normalized_wp_id: str,
    target_branch: str,
    pre_emit_event_size: int,
    pre_emit_status_bytes: bytes | None,
) -> None:
    """Auto-commit the claim's event-log/status artifacts (enables instant
    status sync). The WP file is not mutated for the claim (byte-stable, SC-004);
    reload is the caller's responsibility."""
    w = _wf()

    # ``agent`` is guaranteed truthy here (#2675 T054): the caller only
    # reaches this helper inside the ``if current_lane != Lane.IN_PROGRESS or
    # needs_agent_assignment or agent:`` branch, and only after the
    # `--agent required` guard (`if not agent and not (current_lane ==
    # Lane.IN_PROGRESS and not needs_agent_assignment): raise`) has passed.
    # The only way to satisfy both is ``agent`` truthy -- the falsy-agent
    # disjunct of that guard (``current_lane == IN_PROGRESS and not
    # needs_agent_assignment``) is exactly the case the outer ``if`` already
    # excludes. Narrow explicitly rather than widen ``set_scalar``'s
    # parameter type.
    assert agent, "agent must be non-empty; caller validates this before calling _implement_write_claim_and_commit"

    # WP04/T015 (FR-004/NFR-003/SC-004): the claim triple rides the
    # transition's policy_metadata sidecar (see _implement_start_claim) -- the
    # WP file is NOT mutated for the claim. The former frontmatter dual-write
    # mirror (agent/shell_pid/activity-log) was removed in the #2816 unconditional
    # cutover, so this function writes 0 runtime bytes to the WP file.

    # Auto-commit to target branch (enables instant status sync)
    actual_wp_path = wp.path.resolve()
    status_artifacts = [path.resolve() for path in w._collect_status_artifacts(feature_dir)]
    # WP06 T027: route through BookkeepingTransaction when the
    # mission has a coordination branch, fall back to safe_commit
    # with surgical event-log truncate on failure otherwise.
    w._commit_workflow_change(
        repo_root=main_repo_root,
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        target_branch=target_branch,
        paths=[actual_wp_path, *status_artifacts],
        message=f"chore: Start {normalized_wp_id} implementation [{agent}]",
        operation=f"planned -> claimed for {normalized_wp_id}",
        wp_id=normalized_wp_id,
        pre_emit_event_size=pre_emit_event_size,
        pre_emit_status_bytes=pre_emit_status_bytes,
        auto_rebase_lane_after_commit=True,
    )


def _implement_emit_resume_refresh(
    *,
    feature_dir: Path,
    wp_id: str,
    mission_slug: str,
    actor: str,
    repo_root: Path,
    resolved_binding: ResolvedBinding | None = None,
) -> None:
    """WP07/T029a (FR-004/US3): refresh ``shell_pid`` on resume/re-claim of an
    already ``in_progress`` WP via an off-axis ``InnerStateChanged``
    annotation.  When the resume came through a dispatch invocation, the
    resolved binding rides the same annotation so liveness and provenance
    cannot be durably split by a crash.

    Resume is NOT a ``planned -> claimed`` transition, so this never routes
    through ``policy_metadata`` (that sidecar is reserved for the real claim
    transition, T026/T027). Historically this path wrote nothing at all (a
    true no-op) -- it still writes nothing to the WP file here (no
    frontmatter mutation, no dual-write bridge needed: SC-001/SC-005
    byte-stability holds unconditionally across a resume). Persistence is
    authoritative: append failures propagate and abort the resume.
    """
    import os

    from specify_cli.core.process_liveness import capture_creation_time_baseline
    from specify_cli.status import emit_inner_state_changed
    from specify_cli.status import WPInnerStateDelta

    shell_pid = os.getppid()
    baseline = capture_creation_time_baseline(shell_pid)
    delta_values: dict[str, Any] = {
        "shell_pid": shell_pid,
        "shell_pid_created_at": baseline,
    }
    if resolved_binding is not None:
        delta_values.update(resolved_binding.to_delta(role=_IMPLEMENT_CLAIM_ROLE).to_dict())
    emit_inner_state_changed(
        feature_dir,
        wp_id,
        WPInnerStateDelta.from_dict(delta_values),
        actor=actor,
        mission_slug=mission_slug,
        repo_root=repo_root,
    )


#: The *actual* role that ran at each claim seam — the resolved-binding ``role``
#: is the role that executed, NOT the authored frontmatter recommendation (INV-6).
_IMPLEMENT_CLAIM_ROLE = "implementer"
_REVIEW_CLAIM_ROLE = "reviewer"


def implement_claim_transition(
    *,
    repo_root: Path,
    main_repo_root: Path,
    mission_slug: str,
    normalized_wp_id: str,
    wp: WorkPackage,
    wp_meta: WPMetadata,
    feature_dir: Path,
    agent: str | None,
    target_branch: str,
    workspace_path: Path,
    status_execution_mode: str,
    resolved_binding: ResolvedBinding | None = None,
) -> ImplementClaimResult:
    """Move a WP to ``in_progress`` (claiming it) if not already there.

    ``status_execution_mode`` is passed in already resolved from the
    caller's ``workspace`` (FR-008/#1832 C-IC05 single resolution path) --
    this function does not re-derive it, so it does not need ``workspace``
    itself, only ``workspace_path`` (for the status-event context string).

    Mirrors the pre-extraction inline block byte-for-byte: computes
    ``current_lane``/``fix_mode_active``/``wp_slug`` unconditionally, then
    only runs the claim/commit/dossier-sync/reload sequence when the WP is
    not already ``in_progress`` with an assigned agent.
    """
    from specify_cli.status import get_wp_lane as wf_get_wp_lane
    from specify_cli.status import read_events as wf_read_events
    from specify_cli.status import reduce as wf_reduce

    w = _wf()

    # Move to in_progress lane if not already there, and ensure agent is recorded
    # Lane is event-log-only; read from canonical event log (no frontmatter fallback)
    wf_feature_dir = w._canonical_status_feature_dir(main_repo_root, mission_slug)
    wf_events = wf_read_events(wf_feature_dir)
    wf_snapshot = wf_reduce(wf_events) if wf_events else None
    wf_has_canonical = wf_snapshot is not None and normalized_wp_id in wf_snapshot.work_packages
    if not wf_has_canonical:
        raise RuntimeError(missing_canonical_status_message(normalized_wp_id, mission_slug, wf_feature_dir))
    current_lane = wf_get_wp_lane(wf_feature_dir, normalized_wp_id)

    # Resolve structured agent assignment from WP metadata (centralizes legacy coercion)
    wp_agent_assignment = wp_meta.resolved_agent()
    logger.debug("WP agent assignment: tool=%s model=%s", wp_agent_assignment.tool, wp_agent_assignment.model)
    needs_agent_assignment = wp_agent_assignment.tool == "unknown"
    wp_slug = wp.path.stem
    fix_mode_active = has_prior_rejection(feature_dir, wp_slug, normalized_wp_id)

    events_path_pre = wf_feature_dir / w._STATUS_EVENTS_FILENAME
    status_path_pre = wf_feature_dir / w._STATUS_FILENAME
    # Capture before every status mutation, including the bare-resume path, so
    # commit failure can restore both authoritative artifacts byte-for-byte.
    pre_emit_event_size = events_path_pre.stat().st_size if events_path_pre.exists() else 0
    pre_emit_status_bytes = status_path_pre.read_bytes() if status_path_pre.exists() else None

    if current_lane != Lane.IN_PROGRESS or needs_agent_assignment or agent:
        # Require --agent parameter to track who is working
        if not agent and not (current_lane == Lane.IN_PROGRESS and not needs_agent_assignment):
            print("Error: --agent parameter required when starting implementation.")
            print(f"  Usage: spec-kitty agent action implement {normalized_wp_id} --agent <your-name>")
            print("  Example: spec-kitty agent action implement WP01 --agent claude")
            print()
            print("If you're using a generated agent command file, --agent is already included.")
            print("This tracks WHO is working on the WP (prevents abandoned tasks).")
            raise typer.Exit(1)

        shell_pid = _implement_start_claim(
            main_repo_root=main_repo_root,
            feature_dir=wf_feature_dir,
            mission_slug=mission_slug,
            normalized_wp_id=normalized_wp_id,
            agent=agent,
            wp_agent_assignment=wp_agent_assignment,
            current_lane=current_lane,
            status_execution_mode=status_execution_mode,
            workspace_path=workspace_path,
            resolved_binding=resolved_binding,
        )

        if current_lane == Lane.IN_PROGRESS:
            _implement_emit_resume_refresh(
                feature_dir=wf_feature_dir,
                wp_id=normalized_wp_id,
                mission_slug=mission_slug,
                actor=agent or wp_agent_assignment.tool or "unknown",
                resolved_binding=resolved_binding,
                repo_root=main_repo_root,
            )
        _implement_write_claim_and_commit(
            wp=wp,
            agent=agent,
            main_repo_root=main_repo_root,
            feature_dir=wf_feature_dir,
            mission_slug=mission_slug,
            normalized_wp_id=normalized_wp_id,
            target_branch=target_branch,
            pre_emit_event_size=pre_emit_event_size,
            pre_emit_status_bytes=pre_emit_status_bytes,
        )

        print(f"✓ Claimed {normalized_wp_id} (agent: {agent}, PID: {shell_pid}, target: {target_branch})")

        # Reload to get updated content
        wp = _locate_wp(repo_root, mission_slug, normalized_wp_id)
    else:
        print(f"⚠️  {normalized_wp_id} is already in lane: {current_lane}. Action implement will not move it to in_progress.")
        _implement_emit_resume_refresh(
            feature_dir=wf_feature_dir,
            wp_id=normalized_wp_id,
            mission_slug=mission_slug,
            actor=agent or wp_agent_assignment.tool or "unknown",
            repo_root=main_repo_root,
            resolved_binding=resolved_binding,
        )
        status_artifacts = [path.resolve() for path in w._collect_status_artifacts(wf_feature_dir)]
        w._commit_workflow_change(
            repo_root=main_repo_root,
            feature_dir=wf_feature_dir,
            mission_slug=mission_slug,
            target_branch=target_branch,
            paths=[wp.path.resolve(), *status_artifacts],
            message=f"chore: Refresh {normalized_wp_id} implementation liveness",
            operation=f"refresh implementation liveness for {normalized_wp_id}",
            wp_id=normalized_wp_id,
            pre_emit_event_size=pre_emit_event_size,
            pre_emit_status_bytes=pre_emit_status_bytes,
            auto_rebase_lane_after_commit=True,
        )

    return ImplementClaimResult(
        wp=wp,
        current_lane=current_lane,
        fix_mode_active=fix_mode_active,
        wp_slug=wp_slug,
        wp_agent_assignment=wp_agent_assignment,
    )


def implement_try_render_fix_mode_prompt(
    *,
    fix_mode_active: bool,
    feature_dir: Path,
    wp_slug: str,
    review_feedback_ref: str | None,
    review_feedback_file: Path | None,
    workspace_path: Path,
    mission_slug: str,
    normalized_wp_id: str,
    repo_root: Path,
) -> Path | None:
    """Render the focused fix-mode prompt when the WP was rejected and has
    review-cycle artifacts. The fix-prompt completely replaces the full WP
    prompt (not appended). Returns the written prompt path, or ``None`` when
    fix-mode does not apply (caller should render the full prompt instead).

    ``feature_dir`` is retained for the stable public signature (this WP's
    only caller, ``workflow.py``, passes it by keyword) but is no longer
    read: WP05 (verdict-seam-write-unification-01KZ9Q35, T024) repointed the
    artifact-directory resolution onto ``repo_root``/``mission_slug`` via
    :func:`~specify_cli.review.cycle._review_cycle_wp_dir` (the T058 owner
    function) instead of a raw ``feature_dir``-anchored join.
    """
    del feature_dir  # WP05/T024: directory resolution now routes through repo_root + mission_slug
    if not fix_mode_active:
        return None

    try:
        from specify_cli.cli.console import console
        from specify_cli.review.artifacts import ReviewCycleArtifact
        from specify_cli.review.cycle import _review_cycle_wp_dir
        from specify_cli.review.fix_prompt import generate_fix_prompt

        # WP05 (verdict-seam-write-unification-01KZ9Q35, T024): routed through
        # the T058 owner function instead of a raw ``feature_dir / "tasks" /
        # wp_slug`` join -- one of the three sites WP04's review flagged as
        # unrouted (alongside
        # ``workflow_cores.py::has_prior_rejection`` and ``workflow.py::
        # review``). This function's own ``.from_file``/``.latest`` calls
        # below remain content/cycle-number loaders (squad #1 — KEPT, not
        # verdict readers), unaffected by this directory-resolution fix.
        sub_artifact_dir = _review_cycle_wp_dir(repo_root, mission_slug, wp_slug)
        # Declared up front (#2675 T054): ``.from_file(...)`` returns a
        # non-Optional ``ReviewCycleArtifact`` while ``.latest(...)`` returns
        # ``ReviewCycleArtifact | None`` -- without this explicit annotation
        # mypy infers ``latest_artifact``'s type from the first (non-Optional)
        # branch and flags the second assignment as an incompatible
        # redefinition.
        latest_artifact: ReviewCycleArtifact | None
        if review_feedback_ref and review_feedback_ref.startswith("review-cycle://") and review_feedback_file is not None:
            latest_artifact = ReviewCycleArtifact.from_file(review_feedback_file)
        else:
            latest_artifact = ReviewCycleArtifact.latest(sub_artifact_dir)
        if latest_artifact is None:
            return None

        console.print(
            f"[bold]Fix mode[/bold]: generating focused prompt from "
            f"review-cycle-{latest_artifact.cycle_number} "
            f"(Canonical feedback: {sub_artifact_dir / f'review-cycle-{latest_artifact.cycle_number}.md'})"
        )
        fix_prompt_text = generate_fix_prompt(
            artifact=latest_artifact,
            worktree_path=workspace_path,
            mission_slug=mission_slug,
            wp_id=normalized_wp_id,
        )
        fix_prompt_file = write_prompt_to_file("implement", mission_slug, normalized_wp_id, fix_prompt_text, repo_root=repo_root)
        print()
        print(f"📍 Workspace: cd {workspace_path}")
        print(f"🔧 Fix mode — Cycle {latest_artifact.cycle_number}: focused prompt from review artifact")
        print()
        print("▶▶▶ NEXT STEP: Read the full fix-mode prompt file now:")
        print(f"    cat {fix_prompt_file}")
        print()
        return fix_prompt_file
    except Exception as fix_mode_err:
        logger.warning("Fix-mode prompt generation failed, falling through to full prompt: %s", fix_mode_err)
        return None


def _baseline_artifact_needs_commit(repo_root: Path, artifact: Path) -> bool:
    """True if ``artifact`` has something to commit (untracked or modified) in ``repo_root``.

    A resume of an already-captured WP re-loads the cached, already-committed
    artifact; re-committing it would run ``git commit`` with nothing staged and
    raise "nothing to commit" — a misleading best-effort warning on every
    resume (#2895). Gating the commit on a non-empty ``git status --porcelain``
    for the artifact skips that no-op. Degrades to ``True`` (attempt the commit,
    preserving prior behaviour) if git is unusable here.
    """
    from specify_cli.core import git_ops

    try:
        rc, out, _err = git_ops.run_command(
            ["git", "status", "--porcelain", "--", str(artifact)],
            capture=True,
            check_return=False,
            cwd=repo_root,
        )
    except Exception:  # noqa: BLE001 — git absent/unusable: fall back to attempting the commit
        return True
    if rc != 0:
        # git couldn't report status (e.g. not a repo): don't suppress a
        # possibly-needed commit — preserve the prior "always attempt" behaviour.
        return True
    return bool(out.strip())


def implement_capture_baseline(
    *,
    workspace_path: Path,
    target_branch: str,
    normalized_wp_id: str,
    mission_slug: str,
    feature_dir: Path,
    wp_slug: str,
    main_repo_root: Path,
) -> None:
    """Capture (one-time, cached) baseline test results before the agent
    starts coding, and best-effort commit the baseline artifact."""
    from specify_cli.core.commit_guard import GuardCapability

    w = _wf()
    try:
        from rich.markup import escape

        from specify_cli.cli.console import console
        from specify_cli.review.baseline import capture_baseline
        from specify_cli.review.scope_source import resolve_scope_source

        # T015 (mission scopesource-gate-followup-01KY6S9P, FR-011/FR-014):
        # inject the shared factory so implement-time capture activates
        # ``_capture_baseline_via_scope_source`` -- the SAME
        # test_command()/parse_results() authority the pre-review head run
        # uses. The factory resolves only ``DeclaredCommandScopeSource`` after
        # the workflow-derived source was retired. Resolved
        # against the SAME ``main_repo_root`` the baseline artifact placement
        # below already uses -- not a freshly reconstructed root.
        baseline = capture_baseline(
            worktree_path=workspace_path,
            base_branch=target_branch,
            wp_id=normalized_wp_id,
            mission_slug=mission_slug,
            feature_dir=feature_dir,
            wp_slug=wp_slug,
            scope_source=resolve_scope_source(main_repo_root),
        )
        # Rich markup only renders through the CLI console seam; the builtin
        # print emitted the tags literally (#4163).
        if baseline is not None and baseline.failed > 0:
            console.print(f"[dim]Baseline: {baseline.failed} pre-existing test failure(s) captured[/dim]")
        elif baseline is not None and baseline.failed == -1:
            console.print("[yellow]Warning: baseline test capture failed — no baseline context available[/yellow]")

        # Commit the baseline artifact whenever capture actually wrote one
        # (any non-sentinel result, clean OR dirty) — NOT only when
        # ``failed > 0``. Landing fold (mission scopesource-gate-followup): the
        # unified ScopeSource capture path (T015) calls ``result.save(...)``
        # unconditionally, and the head-side gate LOADS this artifact to diff
        # against (``tasks_move_task.py`` ``_load_baseline``). So a clean
        # (``failed == 0``) baseline MUST be committed too — both to feed the
        # baseline↔head diff this mission unifies, and to keep the
        # ``for_review`` uncommitted-owned-file guard from blocking on an
        # otherwise-orphaned WP-owned artifact. The prior ``failed > 0`` gate
        # left every clean baseline uncommitted, which regressed
        # ``test_issue_2684`` once implement-time capture began emitting one.
        # (The ``failed == -1`` sentinel is never persisted, so it never
        # reaches this commit.)
        baseline_artifact = feature_dir / "tasks" / wp_slug / "baseline-tests.json"
        if (
            baseline is not None
            and baseline.failed != -1
            and baseline_artifact.exists()
            and _baseline_artifact_needs_commit(main_repo_root, baseline_artifact)
        ):
            # Mechanical WP06 pre-step migration.
            try:
                # Baseline artifact (tasks/<wp>/baseline-tests.json) is a
                # WORK_PACKAGE_TASK-kind artifact — a PRIMARY-partition
                # kind (T017): it lands on the mission/lane
                # ``target_branch`` for EVERY topology, resolved via the
                # seam rather than constructed inline. STANDARD asserts
                # no protected-branch flow, so a protected target is
                # refused — the best-effort handler below logs the
                # refusal (FR-008).
                baseline_placement = w._resolve_workflow_placement(
                    repo_root=main_repo_root,
                    mission_slug=mission_slug,
                    kind=MissionArtifactKind.WORK_PACKAGE_TASK,
                )
                w.safe_commit(
                    repo_root=main_repo_root,
                    worktree_root=main_repo_root,
                    target=baseline_placement,
                    message=f"chore: Capture baseline tests for {normalized_wp_id}",
                    paths=(baseline_artifact,),
                    capability=GuardCapability.STANDARD,
                )
            except Exception as bl_commit_exc:  # noqa: BLE001 — best-effort
                # #2896: surface the real refusal reason visibly, not only to
                # the logger — otherwise a later `for_review` block on the
                # still-uncommitted artifact reads as a mysterious "uncommitted
                # owned file" with no trace of WHY the commit was refused (e.g.
                # a protected target / SafeCommitHeadMismatch).
                logger.warning("Baseline artifact commit failed: %s", bl_commit_exc)
                # The refusal text is arbitrary (git output such as
                # ``! [rejected] main -> main``): escape it so Rich neither
                # swallows bracketed words nor raises MarkupError on it.
                console.print(
                    f"[yellow]Warning: baseline artifact was not committed "
                    f"({escape(str(bl_commit_exc))}); a later move to for_review may block on it.[/yellow]"
                )
    except Exception as bl_err:
        logger.warning("Baseline capture error: %s", bl_err)


def build_implement_prompt_lines(
    *,
    normalized_wp_id: str,
    wp: WorkPackage,
    workspace: ResolvedWorkspace,
    workspace_path: Path,
    wp_agent_assignment: AgentAssignment,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    subtask_cmd: str,
    has_feedback: bool,
    review_feedback_ref: str | None,
    review_feedback_file: Path | None,
    mission_type: str,
    deliverables_path: str | None,
) -> list[str]:
    """Assemble the full ``IMPLEMENT: <wp>`` prompt body."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(f"IMPLEMENT: {normalized_wp_id}")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Source: {wp.path}")
    lines.append("")
    lines.append(f"Workspace: {workspace_path}")
    lines.append(workspace_contract_description(workspace, normalized_wp_id))
    lines.append("")
    # WP03 (#833): surface the resolved agent 4-tuple so model / profile_id /
    # role flow into the rendered prompt instead of being silently discarded.
    lines.extend(render_resolved_agent_identity(wp_agent_assignment))
    lines.append("")
    lines.append(render_charter_context_text(repo_root, "implement", mission_type=mission_type))
    lines.append("")

    # CRITICAL: WP isolation rules
    lines.extend(render_isolation_banner(normalized_wp_id, "implement"))
    lines.append("")

    # Inject worktree topology context for stacked branches
    try:
        from specify_cli.core.worktree_topology import materialize_worktree_topology, render_topology_json

        topology = materialize_worktree_topology(repo_root, mission_slug)
        if topology.has_stacking:
            lines.extend(render_topology_json(topology, current_wp_id=normalized_wp_id))
            lines.append("")
    except Exception as exc:
        lines.append(f"[Topology unavailable: {exc}]")
        lines.append("")

    # Next steps
    lines.append("=" * 80)
    lines.append("WHEN YOU'RE DONE:")
    lines.append("=" * 80)
    lines.append("✓ Implementation complete and tested:")
    lines.append("  1. **Commit your implementation files:**")
    lines.append("     git status  # Check what you changed")
    lines.append("     git add <your-implementation-files>  # NOT WP status files")
    lines.append(f'     git commit -m "feat({normalized_wp_id}): <brief description>"')
    lines.append("     git log -1 --oneline  # Verify commit succeeded")
    lines.append("  2. Mark all subtasks as done:")
    lines.append(f"     spec-kitty agent tasks mark-status {subtask_cmd} --status done --mission {mission_slug}")
    lines.append("  3. Move WP to review:")
    lines.append(f'     spec-kitty agent tasks move-task {normalized_wp_id} --to for_review --mission {mission_slug} --note "Ready for review"')
    lines.append("")
    lines.append("✗ Blocked or cannot complete:")
    lines.append(f'  spec-kitty agent tasks add-history {normalized_wp_id} --mission {mission_slug} --note "Blocked: <reason>"')
    lines.append("=" * 80)
    lines.append("")
    lines.append("📍 WORKING DIRECTORY:")
    lines.append(f"   cd {workspace_path}")
    if workspace.lane_id:
        lines.append("   # All implementation work happens in this workspace")
        lines.append(f"   # When done, return to repo root: cd {repo_root}")
    else:
        lines.append("   # Planning-artifact work for this WP happens in the repository root")
    lines.append("")
    lines.extend(shared_artifact_guidance(workspace, repo_root, mission_slug))
    lines.append("")
    lines.append("📋 STATUS TRACKING:")
    lines.append(f"   kitty-specs/ status is tracked in {target_branch} branch (visible to all agents)")
    lines.append("   Status changes auto-commit to the coordination branch (visible to all agents)")
    lines.append("   ⚠️  You will see commits from other agents - IGNORE THEM")
    lines.append("=" * 80)
    lines.append("")

    if has_feedback:
        lines.append("⚠️  This work package has review feedback.")
        if review_feedback_ref:
            lines.append(f"   Canonical feedback reference: {review_feedback_ref}")
            if review_feedback_ref.startswith("feedback://"):
                lines.append("   WARNING: legacy feedback:// reference detected; readable but deprecated.")
            if review_feedback_file is not None:
                lines.append(f'   Read it first: cat "{review_feedback_file}"')
            else:
                lines.append("   WARNING: review feedback reference is set, but the artifact is missing/unreadable.")
                lines.append("   Ask reviewer to re-run move-task with --review-feedback-file.")
        else:
            lines.append("   WARNING: review_status=has_feedback but no review_feedback reference is set.")
            lines.append("   Ask reviewer to re-run move-task with --review-feedback-file.")
        lines.append("")

    # Research mission: Show deliverables path prominently
    if mission_type == MISSION_TYPE_RESEARCH and deliverables_path:
        lines.append("╔" + "=" * 78 + "╗")
        lines.append("║  🔬 RESEARCH MISSION - TWO ARTIFACT TYPES                                 ║")
        lines.append("╠" + "=" * 78 + "╣")
        lines.append("║                                                                          ║")
        lines.append("║  📁 RESEARCH DELIVERABLES (your output):                                 ║")
        deliv_line = f"║     {deliverables_path:<69} ║"
        lines.append(deliv_line)
        lines.append("║     ↳ Create findings, reports, data here                                ║")
        lines.append("║     ↳ Commit to worktree branch                                          ║")
        lines.append(f"║     ↳ Will merge to {target_branch:<62} ║")
        lines.append("║                                                                          ║")
        lines.append("║  📋 PLANNING ARTIFACTS (kitty-specs/):                                   ║")
        lines.append("║     ↳ evidence-log.csv, source-register.csv                              ║")
        lines.append("║     ↳ Edit in planning repo (rare during implementation)                 ║")
        lines.append("║                                                                          ║")
        lines.append("║  ⚠️  DO NOT put research deliverables in kitty-specs/!                   ║")
        lines.append("╚" + "=" * 78 + "╝")
        lines.append("")

    # WP content marker and content
    lines.extend(render_wp_prompt_wrapper(wp.path.read_text(encoding="utf-8")))

    # Completion instructions at end
    lines.append("=" * 80)
    lines.append("🎯 IMPLEMENTATION COMPLETE? RUN THESE COMMANDS:")
    lines.append("=" * 80)
    lines.append("")
    lines.append("✅ Implementation complete and tested:")
    lines.append("   1. **Commit your implementation files:**")
    lines.append("      git status  # Check what you changed")
    lines.append("      git add <your-implementation-files>  # NOT WP status files")
    lines.append(f'      git commit -m "feat({normalized_wp_id}): <brief description>"')
    lines.append("      git log -1 --oneline  # Verify commit succeeded")
    lines.append("      (Use fix: for bugs, chore: for maintenance, docs: for documentation)")
    lines.append("   2. Mark all subtasks as done:")
    lines.append(f"      spec-kitty agent tasks mark-status {subtask_cmd} --status done --mission {mission_slug}")
    lines.append("   3. Move WP to review (will check for uncommitted changes):")
    lines.append(f'      spec-kitty agent tasks move-task {normalized_wp_id} --to for_review --mission {mission_slug} --note "Ready for review: <summary>"')
    lines.append("")
    lines.append("⚠️  Blocked or cannot complete:")
    lines.append(f'   spec-kitty agent tasks add-history {normalized_wp_id} --mission {mission_slug} --note "Blocked: <reason>"')
    lines.append("")
    lines.append("⚠️  NOTE: The move-task command will FAIL if you have uncommitted changes!")
    lines.append("     Commit all implementation files BEFORE moving to for_review.")
    lines.append("     Dependent work packages need your committed changes.")
    lines.append("=" * 80)
    return lines


def implement_finalize_and_print(
    *,
    prompt_lines: list[str],
    mission_slug: str,
    normalized_wp_id: str,
    repo_root: Path,
    workspace: ResolvedWorkspace,
    workspace_path: Path,
    has_feedback: bool,
    review_feedback_ref: str | None,
    mission_type: str,
    deliverables_path: str | None,
    subtask_cmd: str,
) -> None:
    """Write the full prompt to its scoped tmp file and print the concise
    stdout summary directing the agent to read it."""
    full_content = "\n".join(prompt_lines)
    prompt_file = write_prompt_to_file("implement", mission_slug, normalized_wp_id, full_content, repo_root=repo_root)

    print()
    print(f"📍 Workspace: cd {workspace_path}")
    if workspace.lane_id:
        shared = ", ".join(workspace.lane_wp_ids or [normalized_wp_id])
        print(f"   Lane workspace: {workspace.lane_id} (shared by {shared})")
    else:
        print("   Repository-root planning workspace")
    if has_feedback:
        if review_feedback_ref:
            print(f"⚠️  Has review feedback - read reference: {review_feedback_ref}")
            if review_feedback_ref.startswith("feedback://"):
                print("   Warning: legacy feedback:// reference detected; readable but deprecated.")
        else:
            print("⚠️  Has review feedback - but no review_feedback reference is set")
    if mission_type == MISSION_TYPE_RESEARCH and deliverables_path:
        print(f"🔬 Research deliverables: {deliverables_path}")
        print("   (NOT in kitty-specs/ - those are planning artifacts)")
    print()
    print("▶▶▶ NEXT STEP: Read the full prompt file now:")
    print(f"    cat {prompt_file}")
    print()
    print("After implementation, run:")
    print(f'  1. git status && git add <your-files> && git commit -m "feat({normalized_wp_id}): <description>"')
    print(f"  2. spec-kitty agent tasks mark-status {subtask_cmd} --status done --mission {mission_slug}")
    print(f'  3. spec-kitty agent tasks move-task {normalized_wp_id} --to for_review --mission {mission_slug} --note "Ready for review"')
    print("     (Pre-flight check will verify no uncommitted changes)")


# ---------------------------------------------------------------------------
# ``review()`` phase extractions (T010)
# ---------------------------------------------------------------------------


@dataclass(slots=True, kw_only=True)
class ReviewLaneContext:
    """Return value of :func:`review_resolve_wp_and_lane_gate`."""

    wp: WorkPackage
    feature_dir: Path
    current_lane: Lane
    review_workspace: ResolvedWorkspace
    status_execution_mode: str
    is_review_claimed: bool


def review_resolve_wp_and_lane_gate(
    repo_root: Path, main_repo_root: Path, mission_slug: str, normalized_wp_id: str
) -> ReviewLaneContext:
    """Load the WP and enforce the "must be for_review (or review-claimed)" gate."""
    from specify_cli.cli.commands.agent.workflow_cores import event_is_review_claim
    from specify_cli.status import get_wp_lane as rv_get_wp_lane
    from specify_cli.status import read_events as rv_read_events
    from specify_cli.status import reduce as rv_reduce

    w = _wf()

    try:
        wp = _locate_wp(repo_root, mission_slug, normalized_wp_id)
    except RuntimeError as e:
        if is_missing_canonical_status_error(e):
            raise RuntimeError(missing_canonical_status_message(normalized_wp_id, mission_slug)) from e
        raise

    # Move to in_progress lane if not already there.
    # Explicit WP review requests must target for_review (or already review-claimed in_progress).
    # Lane is event-log-only; read from canonical event log (no frontmatter fallback)
    feature_dir = w._canonical_status_feature_dir(main_repo_root, mission_slug)
    rv_events = rv_read_events(feature_dir)
    rv_snapshot = rv_reduce(rv_events) if rv_events else None
    rv_has_canonical = rv_snapshot is not None and normalized_wp_id in rv_snapshot.work_packages
    if not rv_has_canonical:
        raise RuntimeError(missing_canonical_status_message(normalized_wp_id, mission_slug, feature_dir))
    current_lane = rv_get_wp_lane(feature_dir, normalized_wp_id)
    # Seam-B (WP03, #3128 / FR-005): the review WP-execution write chokepoint,
    # reached before the review-claim transition. Refuse a review invoked from a
    # checkout the mission does not own (canonically another mission's lane
    # worktree). write_intent gates the checkout-identity refusal; the pure read
    # vehicles leave it False so reads are never falsely refused.
    review_workspace = _wf().resolve_workspace_for_wp(
        main_repo_root, mission_slug, normalized_wp_id, write_intent=True
    )
    status_execution_mode = "direct_repo" if review_workspace.resolution_kind == "repo_root" else "worktree"
    latest_event = None
    for event in reversed(rv_events):
        if getattr(event, "wp_id", None) == normalized_wp_id:
            latest_event = event
            break
    is_review_claimed = bool(latest_event is not None and event_is_review_claim(latest_event))
    if current_lane == Lane.IN_PROGRESS and not is_review_claimed:
        print(f"Error: {normalized_wp_id} is still being implemented, not claimed for review.")
        print("Only work packages in 'for_review' (or already review-claimed in_review) can start workflow review.")
        print(f"Move it first: spec-kitty agent tasks move-task {normalized_wp_id} --to for_review --mission {mission_slug}")
        raise typer.Exit(1)
    if current_lane not in {Lane.FOR_REVIEW, Lane.IN_REVIEW} and not is_review_claimed:
        print(f"Error: {normalized_wp_id} is in lane '{current_lane}', not 'for_review'.")
        print("Only work packages in 'for_review' (or already claimed for review) can start workflow review.")
        print(f"Move it first: spec-kitty agent tasks move-task {normalized_wp_id} --to for_review --mission {mission_slug}")
        raise typer.Exit(1)

    return ReviewLaneContext(
        wp=wp,
        feature_dir=feature_dir,
        current_lane=current_lane,
        review_workspace=review_workspace,
        status_execution_mode=status_execution_mode,
        is_review_claimed=is_review_claimed,
    )


def review_enforce_bulk_edit_gate(
    *,
    feature_dir: Path,
    main_repo_root: Path,
    mission_slug: str,
    target_branch: str,
    review_workspace: ResolvedWorkspace,
) -> None:
    """Bulk edit occurrence classification + per-file diff compliance gate (FR-006/7/8)."""
    from specify_cli.bulk_edit.gate import (
        check_review_diff_compliance,
        ensure_occurrence_classification_ready,
        render_diff_check_failure,
        render_gate_failure,
    )
    from specify_cli.cli.console import console as rich_console

    gate_result = ensure_occurrence_classification_ready(feature_dir)
    if not gate_result.passed:
        render_gate_failure(gate_result, rich_console)
        raise typer.Exit(1)

    if gate_result.change_mode == "bulk_edit":
        _wf()._enforce_bulk_edit_diff_compliance(
            feature_dir=feature_dir,
            main_repo_root=main_repo_root,
            mission_slug=mission_slug,
            target_branch=target_branch,
            review_workspace=review_workspace,
            check_review_diff_compliance=check_review_diff_compliance,
            render_diff_check_failure=render_diff_check_failure,
            rich_console=rich_console,
        )


def review_claim_transition(
    *,
    wp: WorkPackage,
    feature_dir: Path,
    current_lane: Lane,
    agent: str | None,
    main_repo_root: Path,
    mission_slug: str,
    normalized_wp_id: str,
    target_branch: str,
    status_execution_mode: str,
    repo_root: Path,
    resolved_binding: ResolvedBinding | None = None,
) -> WorkPackage:
    """Claim a WP for review (``for_review`` -> ``in_review``) if applicable."""
    from specify_cli.status import start_review_status
    from specify_cli.status import emit_inner_state_changed
    from specify_cli.status import WPInnerStateDelta
    from specify_cli.status import build_self_asserting_actor

    w = _wf()

    if current_lane != Lane.FOR_REVIEW and not (current_lane == Lane.IN_REVIEW and agent):
        print(f"⚠️  {normalized_wp_id} is already in lane: {current_lane}. Workflow review will not move it to in_review.")
        return wp

    # Require --agent parameter to track who is reviewing
    if not agent:
        print("Error: --agent parameter required when starting review.")
        print(f"  Usage: spec-kitty agent action review {normalized_wp_id} --agent <your-name>")
        print("  Example: spec-kitty agent action review WP01 --agent claude")
        print()
        print("If you're using a generated agent command file, --agent is already included.")
        print("This tracks WHO is reviewing the WP (prevents abandoned reviews).")
        raise typer.Exit(1)

    import os

    shell_pid = str(os.getppid())  # Parent process ID (the shell running this command)
    claim_policy_metadata = _claim_policy_metadata(int(shell_pid), agent)
    claim_delta_values: dict[str, Any] = {
        "shell_pid": int(shell_pid),
        "shell_pid_created_at": claim_policy_metadata.get("shell_pid_created_at"),
        "agent": agent,
    }
    if resolved_binding is not None:
        claim_delta_values.update(resolved_binding.to_delta(role=_REVIEW_CLAIM_ROLE).to_dict())
    claim_delta = WPInnerStateDelta.from_dict(claim_delta_values)
    # FR-005: route the compact ``--agent`` value through the single self-
    # asserting actor seam — only the parsed BARE tool reaches actor.tool, an
    # absent segment stays None, and the dispatch binding wins over the self-
    # asserted parse (``agent`` is guaranteed truthy here — the ``--agent``
    # required guard above already raised otherwise, so ``fallback_tool`` is
    # unreachable).
    transition_actor = build_self_asserting_actor(
        role=_REVIEW_CLAIM_ROLE,
        agent=agent,
        fallback_tool=None,
        binding=resolved_binding,
    )

    with w.feature_status_lock(main_repo_root, feature_dir.name):
        # WP06 T027: capture pre-emit event-log size for
        # surgical rollback on commit failure.
        events_path_pre_rev = feature_dir / w._STATUS_EVENTS_FILENAME
        status_path_pre_rev = feature_dir / w._STATUS_FILENAME
        pre_emit_event_size_rev = events_path_pre_rev.stat().st_size if events_path_pre_rev.exists() else 0
        pre_emit_status_bytes_rev = status_path_pre_rev.read_bytes() if status_path_pre_rev.exists() else None
        try:
            start_review_status(
                feature_dir=feature_dir,
                mission_slug=mission_slug,
                wp_id=normalized_wp_id,
                actor=transition_actor,
                review_ref="action-review-claim",
                workspace_context=f"action-review:{main_repo_root}",
                execution_mode=status_execution_mode,
                repo_root=main_repo_root,
                # WP07/T027 (FR-004/FR-014): mirror T026 -- carry the claim
                # triple on the for_review -> in_review transition's
                # policy_metadata sidecar too (provenance on the event even
                # though WP01's reducer only special-cases the
                # planned -> claimed fold; see the emit_inner_state_changed
                # annotation below for the snapshot-slot write this
                # transition alone does not perform).
                policy_metadata=claim_policy_metadata,
                annotation_delta=claim_delta,
            )
        except WorkPackageClaimConflict as exc:
            print(f"Error: {exc}")
            raise typer.Exit(1) from exc
        except WorkPackageStartRejected as exc:
            print(f"Error: {exc}")
            raise typer.Exit(1) from exc

        if current_lane == Lane.IN_REVIEW:
            emit_inner_state_changed(
                feature_dir,
                normalized_wp_id,
                claim_delta,
                actor=agent,
                mission_slug=mission_slug,
                repo_root=main_repo_root,
            )

        # WP04/T015 (FR-004/NFR-003/SC-004): the review claim's shell_pid/agent
        # reach the reduced snapshot via the transaction-carried annotation (or
        # the single no-op re-claim annotation above).
        # The former frontmatter dual-write mirror was removed in the #2816
        # unconditional cutover, so this claim writes 0 runtime bytes to the WP
        # file (byte-stable across the claim).

        # Atomic commit: WP file + all status artifacts (#211, #212)
        actual_wp_path = wp.path.resolve()
        status_artifacts = w._collect_status_artifacts(feature_dir)
        # WP06 T027: route through BookkeepingTransaction (modern
        # path) or surgical-truncate fallback (legacy path).
        w._commit_workflow_change(
            repo_root=main_repo_root,
            feature_dir=feature_dir,
            mission_slug=mission_slug,
            target_branch=target_branch,
            paths=[actual_wp_path, *status_artifacts],
            message=f"chore: Start {normalized_wp_id} review [{agent}]",
            operation=f"for_review -> in_review for {normalized_wp_id}",
            wp_id=normalized_wp_id,
            pre_emit_event_size=pre_emit_event_size_rev,
            pre_emit_status_bytes=pre_emit_status_bytes_rev,
            auto_rebase_lane_after_commit=True,
        )

    print(f"✓ Claimed {normalized_wp_id} for review (agent: {agent}, PID: {shell_pid}, target: {target_branch})")

    # Reload to get updated content
    return _locate_wp(repo_root, mission_slug, normalized_wp_id)


def review_compute_dependents_warning(repo_root: Path, mission_slug: str, normalized_wp_id: str) -> list[str]:
    """Warn when other planned/in-flight WPs depend on the one under review."""
    from specify_cli.core.dependency_graph import build_dependency_graph, get_dependents

    dependents_warning: list[str] = []
    # WP04 / T018 / FR-002: build_dependency_graph reads tasks/ (PRIMARY-partition)
    # → route through the planning seam.  Status-event reads stay on the coord-aware
    # resolver (C-001) so dependents' lane comes from the authoritative event log.
    review_planning_dir = placement_seam(repo_root, mission_slug).read_dir(
        MissionArtifactKind.WORK_PACKAGE_TASK
    )
    graph = build_dependency_graph(review_planning_dir)
    dependents = get_dependents(normalized_wp_id, graph)
    if not dependents:
        return dependents_warning

    # Load lanes from event log (lane is event-log-only).
    # Status reads stay coord-aware (C-001).
    #
    # The STATUS_STATE resolution lives INSIDE the best-effort guard on purpose.
    # Under the DELETED coord-branch shape the kind-aware seam fails loud with
    # ``CoordinationBranchDeleted`` (a ``StatusReadPathNotFound`` subclass, hence
    # an ``Exception`` subclass that the handler below catches) where the old
    # kind-blind resolver could never raise. This helper only computes an
    # advisory warning, so an unreadable status surface must degrade to "no
    # dependents' lanes known" — it must never abort ``agent workflow review``.
    try:
        from specify_cli.status import read_events as rw_read_events
        from specify_cli.status import reduce as rw_reduce

        review_status_dir = placement_seam(repo_root, mission_slug).read_dir(
            MissionArtifactKind.STATUS_STATE
        )
        rw_events = rw_read_events(review_status_dir)
        rw_snapshot = rw_reduce(rw_events) if rw_events else None
        rw_lanes: dict[str, Lane] = {}
        if rw_snapshot:
            for rw_wp_id, rw_state in rw_snapshot.work_packages.items():
                rw_lanes[rw_wp_id] = Lane(rw_state.get("lane", Lane.PLANNED))
    except Exception:
        rw_lanes = {}

    incomplete: list[str] = [
        dependent_id for dependent_id in dependents if rw_lanes.get(dependent_id, Lane.PLANNED) in {Lane.PLANNED, Lane.IN_PROGRESS, Lane.FOR_REVIEW}
    ]
    if incomplete:
        dependents_list = ", ".join(sorted(incomplete))
        dependents_warning.append(f"⚠️  Dependency Alert: {dependents_list} depend on {normalized_wp_id} (not yet done)")
        dependents_warning.append("   If you request changes, notify those agents to rebase.")
    return dependents_warning


def _review_context_line(
    *, workspace: ResolvedWorkspace, workspace_path: Path, review_ctx: dict[str, object], mission_slug: str, wp: WorkPackage
) -> list[str]:
    """Render the "GIT REVIEW CONTEXT" block, or the unavailable-diff notice."""
    lines: list[str] = []
    if review_ctx["base_branch"] != "unknown":
        base = review_ctx["base_branch"]
        branch_ref = review_ctx["branch_name"]
        review_paths = ""
        if workspace.resolution_kind == "repo_root":
            wp_meta, _ = read_wp_frontmatter(wp.path)
            pathspecs = build_owned_files_review_pathspecs(list(wp_meta.owned_files or []), mission_slug)
            if pathspecs:
                review_paths = " -- " + " ".join(pathspecs)
        lines.append("─── GIT REVIEW CONTEXT " + "─" * 57)
        lines.append(f"Branch:      {branch_ref}")
        lines.append(f"Base branch: {base} ({review_ctx['commit_count']} commits ahead)")
        lines.append("")
        lines.append("Review commands (run in the workspace):")
        lines.append(f"  cd {workspace_path}")
        lines.append(f"  git log {base}..{branch_ref} --oneline{review_paths}           # WP commits only")
        lines.append(f"  git diff {base}..{branch_ref} --stat{review_paths}             # Changed files")
        lines.append(f"  git diff {base}..{branch_ref}{review_paths}                    # Full diff")
        lines.append("─" * 80)
        lines.append("")
    elif workspace.resolution_kind == "repo_root":
        lines.append("─── GIT REVIEW CONTEXT " + "─" * 57)
        lines.append("Review commands unavailable: no deterministic implementation claim commit found for this WP.")
        lines.append("Re-run review after the WP has a committed implementation claim on this mission.")
        lines.append("─" * 80)
        lines.append("")
    return lines


def _review_baseline_context_lines(*, main_repo_root: Path, mission_slug: str, wp_slug: str) -> list[str]:
    """Render the "BASELINE TEST CONTEXT" block, if a cached baseline exists."""
    lines: list[str] = []
    w = _wf()
    # IC-04/T017: baseline-test READ, kept DISTINCT from the write in
    # implement_capture_baseline (campsite note #5 — they diverge
    # intentionally, never dedupe into one shared call/variable).
    # WORK_PACKAGE_TASK (tasks/<wp_slug>/) is a PRIMARY-partition kind —
    # routed via the kind-aware seam instead of the kind-blind coord husk
    # (NFR-001 / Directive-041).
    rv_feature_dir = w._resolve_workflow_read_dir(
        repo_root=main_repo_root, mission_slug=mission_slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK
    )
    try:
        from specify_cli.review.baseline import BaselineTestResult

        rv_baseline_path = rv_feature_dir / "tasks" / wp_slug / "baseline-tests.json"
        rv_baseline = BaselineTestResult.load(rv_baseline_path)
        if rv_baseline is not None and rv_baseline.failed > 0:
            lines.append("─── BASELINE TEST CONTEXT " + "─" * 54)
            lines.append(
                f"**{rv_baseline.failed} test failure(s) existed BEFORE this WP** (base: {rv_baseline.base_branch} @ {rv_baseline.base_commit[:7]}):"
            )
            lines.append("")
            lines.append("| Test | Error | File |")
            lines.append("|------|-------|------|")
            for f in rv_baseline.failures:
                lines.append(f"| {f.test} | {f.error[:80]} | {f.file} |")
            lines.append("")
            lines.append("**These failures are NOT regressions introduced by this WP.** Only flag test failures that are NOT in this list.")
            lines.append("─" * 80)
            lines.append("")
        elif rv_baseline is not None and rv_baseline.failed == -1:
            lines.append("─── BASELINE TEST CONTEXT " + "─" * 54)
            lines.append(
                "**Warning**: Baseline test capture failed at implement time. "
                "Cannot distinguish pre-existing failures from regressions. "
                "Exercise caution when attributing test failures to this WP."
            )
            lines.append("─" * 80)
            lines.append("")
    except Exception as rv_bl_err:
        logger.warning("Baseline load error in review: %s", rv_bl_err)
    return lines


def build_review_prompt_lines(
    *,
    normalized_wp_id: str,
    wp: WorkPackage,
    workspace: ResolvedWorkspace,
    workspace_path: Path,
    review_agent_assignment: AgentAssignment | None,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    dependents_warning: list[str],
    review_ctx: dict[str, object],
    main_repo_root: Path,
    review_feedback_path: Path,
) -> list[str]:
    """Assemble the full ``REVIEW: <wp>`` prompt body."""
    lines: list[str] = []
    lines.append("=" * 80)
    lines.append(f"REVIEW: {normalized_wp_id}")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Source: {wp.path}")
    lines.append("")
    lines.append(f"Workspace: {workspace_path}")
    lines.append(workspace_contract_description(workspace, normalized_wp_id))
    lines.append("")
    if review_agent_assignment is not None:
        lines.extend(render_resolved_agent_identity(review_agent_assignment))
        lines.append("")
    # WP11 (T062/B-8): resolve the mission-type grain from the mission scope so
    # review context delivers the action doctrine bundle rather than degrading
    # to typeless. A resolution failure degrades to ``None`` (typeless), the
    # pre-WP11 behaviour, rather than aborting the prompt.
    try:
        review_mission_type, _ = implement_resolve_mission_type(repo_root, mission_slug)
    except Exception:
        review_mission_type = None
    lines.append(
        render_charter_context_text(repo_root, "review", mission_type=review_mission_type)
    )
    lines.append("")

    if dependents_warning:
        lines.extend(dependents_warning)
        lines.append("")

    lines.extend(render_isolation_banner(normalized_wp_id, "review"))
    lines.append("")

    try:
        from specify_cli.core.worktree_topology import materialize_worktree_topology, render_topology_json

        topology = materialize_worktree_topology(repo_root, mission_slug)
        if topology.has_stacking:
            lines.extend(render_topology_json(topology, current_wp_id=normalized_wp_id))
            lines.append("")
    except Exception as exc:
        lines.append(f"[Topology unavailable: {exc}]")
        lines.append("")

    lines.extend(_review_context_line(workspace=workspace, workspace_path=workspace_path, review_ctx=review_ctx, mission_slug=mission_slug, wp=wp))

    wp_slug = wp.path.stem
    lines.extend(_review_baseline_context_lines(main_repo_root=main_repo_root, mission_slug=mission_slug, wp_slug=wp_slug))

    lines.append("=" * 80)
    lines.append("WHEN YOU'RE DONE:")
    lines.append("=" * 80)
    lines.append("✓ Review passed, no issues:")
    lines.append(f'  spec-kitty agent tasks move-task {normalized_wp_id} --to approved --mission {mission_slug} --note "Review passed"')
    lines.append("")
    lines.append("⚠️  Changes requested:")
    lines.append("  1. Write feedback to (in-repo, committed with the project):")
    lines.append(f"     {review_feedback_path}")
    lines.append(
        f"  2. spec-kitty agent tasks move-task {normalized_wp_id} --to planned --review-feedback-file {review_feedback_path} --mission {mission_slug}"
    )
    lines.append("  3. move-task stores feedback reference in the event log and WP frontmatter")
    lines.append("=" * 80)
    lines.append("")
    lines.append("📍 WORKING DIRECTORY:")
    lines.append(f"   cd {workspace_path}")
    if workspace.lane_id:
        lines.append("   # Review the implementation in this workspace")
        lines.append("   # Read code, run tests, check against requirements")
        lines.append(f"   # When done, return to repo root: cd {repo_root}")
    else:
        lines.append("   # Review the planning-artifact changes directly in the repository root")
    lines.append("")
    lines.extend(shared_artifact_guidance(workspace, repo_root, mission_slug))
    lines.append("")
    lines.append("📋 STATUS TRACKING:")
    lines.append(f"   kitty-specs/ status is tracked in {target_branch} branch (visible to all agents)")
    lines.append("   Status changes auto-commit to the coordination branch (visible to all agents)")
    lines.append("   ⚠️  You will see commits from other agents - IGNORE THEM")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Review the implementation against the requirements below.")
    lines.append("Check code quality, tests, documentation, and adherence to spec.")
    lines.append("")
    from specify_cli.review.antipattern_checklist import render_wp_review_antipattern_checklist

    lines.append(render_wp_review_antipattern_checklist())
    lines.append("")

    lines.extend(render_wp_prompt_wrapper(wp.path.read_text(encoding="utf-8")))

    lines.append("=" * 80)
    lines.append("🎯 REVIEW COMPLETE? RUN ONE OF THESE COMMANDS:")
    lines.append("=" * 80)
    lines.append("")
    lines.append("✅ APPROVE (no issues found):")
    lines.append(f'   spec-kitty agent tasks move-task {normalized_wp_id} --to approved --mission {mission_slug} --note "Review passed: <summary>"')
    lines.append("")
    lines.append("❌ REQUEST CHANGES (issues found):")
    lines.append("   1. Write feedback to the in-repo path (committed with the project):")
    lines.append(f"      cat > {review_feedback_path} <<'EOF'")
    lines.append("**Issue 1**: <description and how to fix>")
    lines.append("**Issue 2**: <description and how to fix>")
    lines.append("EOF")
    lines.append("")
    lines.append("   2. Move to planned with feedback:")
    lines.append(
        f"      spec-kitty agent tasks move-task {normalized_wp_id} --to planned --review-feedback-file {review_feedback_path} --mission {mission_slug}"
    )
    lines.append("")
    lines.append("⚠️  NOTE: You MUST run one of these commands to complete the review!")
    lines.append("     The Python script handles all file updates automatically.")
    lines.append("=" * 80)
    return lines


def review_finalize_and_print(
    *,
    prompt_lines: list[str],
    main_repo_root: Path,
    mission_slug: str,
    normalized_wp_id: str,
    workspace: ResolvedWorkspace,
    workspace_path: Path,
    review_ctx: dict[str, object],
    target_branch: str,
    dependents_warning: list[str],
    review_feedback_path: Path,
    wp: WorkPackage,
) -> None:
    """Write the review prompt (with metadata), validate it, and print the
    concise stdout summary."""
    from specify_cli.review.prompt_metadata import (
        build_review_prompt_metadata,
        validate_review_prompt_metadata,
        write_review_prompt_with_metadata,
    )
    from specify_cli.mission_metadata import resolve_mission_identity

    full_content = "\n".join(prompt_lines)
    # FR-005 (#2186): the review-prompt metadata ``mission_id`` is a meta.json
    # read → PRIMARY only. Anchor on the topology-blind PRIMARY dir, not the
    # kind-blind coord-aware resolver (which selects the meta-less husk).
    # read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-004: routed
    # through the kind-aware seam — PRIMARY_METADATA is a PRIMARY-partition
    # kind, so it short-circuits to PRIMARY before any coord probe and never
    # lands on that husk.
    mission_identity = resolve_mission_identity(
        placement_seam(main_repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    )
    review_metadata = build_review_prompt_metadata(
        repo_root=main_repo_root,
        mission_id=mission_identity.mission_id,
        mission_slug=mission_slug,
        work_package_id=normalized_wp_id,
        lane_worktree=Path(workspace_path),
        mission_branch=str(review_ctx.get("mission_branch") or target_branch),
        lane_branch=str(review_ctx.get("lane_branch") or review_ctx.get("branch_name") or "HEAD"),
        base_ref=str(review_ctx.get("base_ref") or review_ctx.get("base_branch") or target_branch),
    )
    prompt_file = write_review_prompt_with_metadata(full_content, review_metadata)
    validate_review_prompt_metadata(prompt_file, review_metadata)

    _review_print_finalize_summary(
        prompt_file=prompt_file,
        mission_slug=mission_slug,
        normalized_wp_id=normalized_wp_id,
        workspace=workspace,
        workspace_path=workspace_path,
        review_ctx=review_ctx,
        dependents_warning=dependents_warning,
        review_feedback_path=review_feedback_path,
        wp=wp,
    )


def _review_print_finalize_summary(
    *,
    prompt_file: Path,
    mission_slug: str,
    normalized_wp_id: str,
    workspace: ResolvedWorkspace,
    workspace_path: Path,
    review_ctx: dict[str, object],
    dependents_warning: list[str],
    review_feedback_path: Path,
    wp: WorkPackage,
) -> None:
    """The concise stdout summary printed after the review prompt is written."""
    print()
    if dependents_warning:
        for line in dependents_warning:
            print(line)
        print()
    print(f"📍 Workspace: cd {workspace_path}")
    if workspace.lane_id:
        shared = ", ".join(workspace.lane_wp_ids or [normalized_wp_id])
        print(f"   Lane workspace: {workspace.lane_id} (shared by {shared})")
    else:
        print("   Repository-root planning workspace")
    if review_ctx["base_branch"] != "unknown":
        base = review_ctx["base_branch"]
        print(f"🔀 Branch: {review_ctx['branch_name']} (based on {base}, {review_ctx['commit_count']} commits)")
        if workspace.resolution_kind == "repo_root":
            wp_meta, _ = read_wp_frontmatter(wp.path)
            pathspecs = build_owned_files_review_pathspecs(list(wp_meta.owned_files or []), mission_slug)
            review_paths = " -- " + " ".join(pathspecs) if pathspecs else ""
            print(f"   Review diff: git log {base}..{review_ctx['branch_name']} --oneline{review_paths}")
        else:
            print(f"   Review diff: git log {base}..{review_ctx['branch_name']} --oneline")
    elif workspace.resolution_kind == "repo_root":
        print("🔀 Review diff unavailable: no deterministic implementation claim commit found for this WP")
    print()
    print("▶▶▶ NEXT STEP: Read the full prompt file now:")
    print(f"    cat {prompt_file}")
    print()
    print("After review, run:")
    print(f'  ✅ spec-kitty agent tasks move-task {normalized_wp_id} --to approved --mission {mission_slug} --note "Review passed"')
    print(f"  ❌ spec-kitty agent tasks move-task {normalized_wp_id} --to planned --review-feedback-file {review_feedback_path} --mission {mission_slug}")


# ---------------------------------------------------------------------------
# ``_resolve_review_context()`` sub-phase extractions (T011)
# ---------------------------------------------------------------------------


def review_context_for_repo_root_workspace(
    *, repo_root: Path, feature_dir: Path, wp_id: str, ctx: dict[str, object]
) -> dict[str, object]:
    """The ``resolution_kind == "repo_root"`` branch of ``_resolve_review_context``:
    a flat/single-branch mission has no lane worktree, so the "branch" IS
    ``HEAD`` and the "base" is the WP's own claim commit."""
    import subprocess

    wp_paths = sorted((feature_dir / "tasks").glob(f"{wp_id}*.md"))
    claim = subprocess.run(
        ["git", "log", "--format=%H%x00%s", "--", *(str(path) for path in wp_paths)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    claim_commit: str | None = None
    for raw in claim.stdout.splitlines():
        commit_hash, _, subject = raw.partition("\x00")
        if not commit_hash:
            continue
        if f"Move {wp_id} to in_progress" in subject or f"{wp_id} claimed for implementation" in subject or f"Start {wp_id} implementation" in subject:
            claim_commit = commit_hash.strip()
            break
    if claim_commit is None:
        return ctx
    count = subprocess.run(
        ["git", "rev-list", "--count", f"{claim_commit}..HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    commit_count = int(count.stdout.strip()) if count.returncode == 0 and count.stdout.strip().isdigit() else 1
    ctx["branch_name"] = "HEAD"
    ctx["base_branch"] = claim_commit
    ctx["lane_branch"] = "HEAD"
    ctx["base_ref"] = claim_commit
    ctx["commit_count"] = commit_count
    return ctx


def review_context_search_unknown_base(
    *, repo_root: Path, mission_slug: str, branch: str, wp_frontmatter: str
) -> tuple[str | None, int]:
    """Search a fixed candidate list (dependency branches + common integration
    branches) for the base with the FEWEST commits unique to *branch*."""
    import subprocess

    from specify_cli.cli.commands.agent.workflow_cores import parse_dependency_wp_ids, pick_best_base_branch

    w = _wf()
    candidates: list[str] = []
    for dep_id in parse_dependency_wp_ids(wp_frontmatter):
        try:
            dep_workspace = w.resolve_workspace_for_wp(repo_root, mission_slug, dep_id)
        except (ValueError, FileNotFoundError):
            continue
        dep_branch = dep_workspace.branch_name
        if dep_branch and dep_branch != branch:
            candidates.append(dep_branch)

    candidates.extend(["main", "2.x", "master", "develop"])
    scored: list[tuple[str, int]] = []
    for candidate in candidates:
        mb = subprocess.run(
            ["git", "merge-base", branch, candidate],
            cwd=repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if mb.returncode != 0:
            continue
        count_r = subprocess.run(
            ["git", "rev-list", "--count", f"{mb.stdout.strip()}..{branch}"],
            cwd=repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        if count_r.returncode != 0:
            continue
        count = int(count_r.stdout.strip()) if count_r.stdout.strip().isdigit() else 0
        scored.append((candidate, count))

    result: tuple[str | None, int] = pick_best_base_branch(scored)
    return result


def review_context_for_worktree_branch(
    *, repo_root: Path, mission_slug: str, workspace: ResolvedWorkspace, workspace_path: Path, mission_branch: str, wp_frontmatter: str, ctx: dict[str, object]
) -> dict[str, object]:
    """The lane-worktree branch of ``_resolve_review_context``: resolve the
    actual checked-out branch name, then its base ref (explicit context,
    the mission branch, or a scored candidate search), then the commit count."""
    import subprocess

    from specify_cli.core.git_ops import get_current_branch

    branch = get_current_branch(workspace_path)
    if not branch:
        return ctx
    ctx["branch_name"] = branch
    ctx["lane_branch"] = branch

    base_ref = "unknown"
    if workspace.context is not None and workspace.context.base_branch:
        base_ref = workspace.context.base_branch
    elif mission_branch != "unknown":
        base_ref = mission_branch

    if base_ref == "unknown":
        best_base, best_count = review_context_search_unknown_base(
            repo_root=repo_root, mission_slug=mission_slug, branch=branch, wp_frontmatter=wp_frontmatter
        )
        if best_base is not None:
            ctx["base_branch"] = best_base
            ctx["base_ref"] = best_base
            ctx["commit_count"] = best_count
        return ctx

    count_r = subprocess.run(
        ["git", "rev-list", "--count", f"{base_ref}..{branch}"],
        cwd=repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    commit_count = int(count_r.stdout.strip()) if count_r.returncode == 0 and count_r.stdout.strip().isdigit() else 0
    ctx["base_branch"] = base_ref
    ctx["base_ref"] = base_ref
    ctx["commit_count"] = commit_count
    return ctx
