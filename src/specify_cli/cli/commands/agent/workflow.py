"""Action commands for AI agents - display prompts and instructions.

WP04 (#676) — Review-cycle counter inventory
============================================
The ``review-cycle-N.md`` artifact and the implicit counter ``N`` (computed
from ``len(glob("review-cycle-*.md")) + 1``) are mutated by
``_persist_review_feedback``, which lives in
``src/specify_cli/cli/commands/agent/tasks_materialization.py`` — see that
function's own docstring for the current behaviour rather than a line-number
pin here, which would only go stale again (``tasks.py`` re-exports the same
symbol as a compatibility shim; it does not define it). That helper is
invoked from a single call site — ``move-task ... --to planned
--review-feedback-file <path>`` — which is the canonical reviewer-rejection
event.

**Correction (WP16/T072, review-cycle-verdict-seam-rebuild-01KZ2W7W):** the
original claim above — that this is the **exactly one** mutation point for a
review-cycle verdict across the whole runtime — was already false when
written, and more so after this mission's WP07/WP10/WP12 landed. The
authoritative count of verdict writers, location resolvers, and frontmatter
readers is no longer restated as a number in this docstring. Live code is the
authority; this docstring intentionally carries no second frozen count that
can go stale silently.

Sites in this module that **mention** ``review-cycle-*`` artifacts but do
**not** mutate the counter or write any artifact:

* ``_resolve_review_feedback_pointer``'s docstring, describing the canonical
  pointer scheme.
* ``_has_prior_rejection``, which performs a read-only ``glob`` check.
* fix-mode prompt rendering, which reads the latest artifact via
  ``ReviewCycleArtifact.from_file`` / ``.latest``; no write.
* review-prompt rendering, which reads the counter to compute a *placeholder*
  path ``review-feedback-{next_cycle}.md``
  (:func:`specify_cli.review.cycle.review_feedback_source_path`) for
  inclusion in instructional output to the human reviewer. Nothing is
  written; the reviewer authors that file and the ``review-cycle-N.md``
  artifact only materialises when they subsequently run ``move-task --to
  planned``.

Re-running ``spec-kitty agent action implement WPNN`` is therefore a
counter-no-op by construction: this module never calls
``ReviewCycleArtifact.write`` or ``ReviewCycleArtifact.next_cycle_number``.
The unit and integration tests under
``tests/specify_cli/cli/commands/agent/test_review_cycle_counter.py`` and
``tests/integration/test_review_cycle_rejection_only.py`` lock in this
contract.
"""

from __future__ import annotations

from specify_cli.core.constants import (
    MISSION_TYPE_RESEARCH,
)
import json
import logging
import re
import subprocess
import contextlib
from pathlib import Path
from collections.abc import Callable
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from rich.console import Console

    from mission_runtime import PlacementSeam
    from specify_cli.bulk_edit.gate import DiffCheckResult
    from specify_cli.invocation.record import OpStartedEvent

from charter.activation.context import build_charter_context
from specify_cli.cli.commands.agent.tasks import _collect_status_artifacts
from specify_cli.cli.commands.implement import implement as top_level_implement
from specify_cli.cli.selector_resolution import resolve_mission_handle
from specify_cli.coordination.types import CommitReceipt
from specify_cli.core.dependency_graph import (
    build_dependency_graph,
    dependency_readiness_for_wp,
    get_dependents,
)
from specify_cli.core.paths import get_feature_target_branch, get_main_repo_root, is_worktree_context, locate_project_root
from specify_cli.core.utils import write_text_within_directory
from mission_runtime import CommitTarget, MissionArtifactKind
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.git import safe_commit
from specify_cli.git.commit_helpers import SafeCommitRecoveryFailed
from specify_cli.mission import get_deliverables_path, get_mission_type
from specify_cli.mission_metadata import resolve_mission_identity
from specify_cli.review.prompt_metadata import (
    build_review_prompt_metadata,
    validate_review_prompt_metadata,
    write_review_prompt_with_metadata,
)
from specify_cli.review.antipattern_checklist import render_wp_review_antipattern_checklist
from specify_cli.review.cycle import (
    REVIEW_FEEDBACK_SENTINELS,
    resolve_review_cycle_pointer,
    review_feedback_source_path,
)
from specify_cli.status import feature_status_lock
from specify_cli.status import AgentAssignment, Lane
from specify_cli.status import (
    ResolvedBinding,
    WorkPackageClaimConflict,
    WorkPackageStartRejected,
    read_wp_frontmatter,
    start_implementation_status,
    start_review_status,
)
from specify_cli.task_utils import (
    append_activity_log,
    build_document,
    extract_scalar,
    locate_work_package,
    set_scalar,
    split_frontmatter,
)
from specify_cli.workspace.context import (
    ResolvedWorkspace,
    husk_resolution_error,
    resolve_workspace_for_wp,
)

# WP02 (coord-authority-trio-degod-01KX7094, T013): bare re-export shims for
# the god-function pieces moved to workflow_cores.py / workflow_executor.py.
# NOT added to __all__ (this module defines none, and stays that way) --
# existing ``from specify_cli.cli.commands.agent.workflow import <name>``
# imports and ``monkeypatch.setattr(workflow, "<name>", ...)`` call sites
# resolve identically to before the split.
from specify_cli.cli.commands.agent.workflow_cores import (
    ImplementRequest,
    ReviewRequest,
    auto_claim_failure_message as _auto_claim_failure_message,
    has_prior_rejection as _has_prior_rejection,
    is_missing_canonical_status_error as _is_missing_canonical_status_error,
    latest_review_feedback_reference as _latest_review_feedback_reference,
    missing_canonical_status_message as _missing_canonical_status_message,
    normalize_wp_id as _normalize_wp_id,
    read_wp_events as _read_wp_events,
    render_isolation_banner as _render_isolation_banner,
    render_resolved_agent_identity as _render_resolved_agent_identity,
    render_wp_prompt_wrapper as _render_wp_prompt_wrapper,
    resolve_review_feedback_context as _resolve_review_feedback_context,
    resolve_review_feedback_pointer as _resolve_review_feedback_pointer,
    review_feedback_root as _review_feedback_root,
    shared_artifact_guidance as _shared_artifact_guidance,
    workspace_contract_description as _workspace_contract_description,
)
from specify_cli.cli.commands.agent.workflow_executor import (
    commit_workflow_change as _commit_workflow_change,
    ensure_workspace_materialized as _ensure_workspace_materialized,
    write_prompt_to_file as _write_prompt_to_file,
)

# Phase functions the implement()/review()/_resolve_review_context() shells
# delegate to (T009/T010/T011) -- new names, no prior test/import surface to
# preserve, so imported under their own names (no shim needed).
from specify_cli.cli.commands.agent import workflow_executor as _executor

logger = logging.getLogger(__name__)

_REVIEW_FEEDBACK_SENTINELS = REVIEW_FEEDBACK_SENTINELS
_STATUS_EVENTS_FILENAME = "status.events.jsonl"
_STATUS_FILENAME = "status.json"


# ---------------------------------------------------------------------------
# WP06 T027/T029 -- BookkeepingTransaction routing helpers
# ---------------------------------------------------------------------------
#
# These small helpers centralize the policy: when the mission has a
# coordination_branch in meta.json (post-WP03 missions), every lifecycle
# write is routed through BookkeepingTransaction so the event-log append
# is atomically reversible on commit failure (FR-010, fixes #1348).
# Legacy missions fall back to the bare safe_commit path that WP08 will
# replace.

# Module-level accumulator of CommitReceipts for the T029 terminal
# summary. Reset by each top-level invocation.
_WORKFLOW_COMMIT_RECEIPTS: list[dict[str, object]] = []


def _enforce_bulk_edit_diff_compliance(
    *,
    feature_dir: Path,
    main_repo_root: Path,
    mission_slug: str,
    target_branch: str,
    review_workspace: ResolvedWorkspace,
    check_review_diff_compliance: Callable[..., DiffCheckResult | None],
    render_diff_check_failure: Callable[..., None],
    rich_console: Console,
) -> None:
    """Enforce per-file bulk-edit diff compliance for a WP under review (FR-007/8).

    Inspects the WP's diff against its lane base branch and rejects modifications
    to forbidden or unclassified surfaces. Raises ``typer.Exit(1)`` on failure;
    surfaces ``manual_review`` warnings without blocking.
    """
    # The mission branch is the canonical base for a WP lane diff. If the
    # review is running from the main repo (not a lane worktree), this
    # still resolves because the mission branch exists until merge
    # cleanup. If the branch cannot be resolved, fall back to the
    # target_branch captured earlier in this function.
    #
    # #3439 / FR-004 / C-001: LANE_STATE is a PRIMARY-partition kind. On a
    # coord-topology mission ``feature_dir`` is the STATUS-only ``-coord`` husk,
    # which carries no ``lanes.json`` — a direct ``read_lanes_json(feature_dir)``
    # returned ``None`` and silently fell back to ``target_branch``, diffing the
    # entire target-branch delta and false-blocking the gate. Route the read
    # through the placement seam (the existing SSOT — no predicate fork) so the
    # canonical mission_branch base is resolved on every topology.
    try:
        from mission_runtime import MissionArtifactKind, placement_seam

        from specify_cli.lanes.persistence import read_lanes_json as _read_lanes_json

        _lane_state_dir = placement_seam(main_repo_root, mission_slug).read_dir(
            MissionArtifactKind.LANE_STATE
        )
        _lanes_manifest = _read_lanes_json(_lane_state_dir)
        _base_ref = _lanes_manifest.mission_branch if _lanes_manifest is not None else target_branch
    except Exception:
        _base_ref = target_branch
    # The WP diff must be the lane branch's changes on top of the mission
    # branch, NOT `HEAD`. When review runs from the main repo checkout,
    # `HEAD` is the mission's *target* branch (e.g. feat/...), so diffing
    # base..HEAD surfaces the entire target-branch delta (hundreds of
    # unrelated files) and the bulk-edit gate false-blocks. Use the WP's
    # resolved lane branch as head; fall back to HEAD only for repo_root
    # (direct-to-target / planning) workspaces where the changes really
    # are on the current HEAD.
    _head_ref = review_workspace.branch_name or "HEAD"
    _diff_result = check_review_diff_compliance(
        feature_dir=feature_dir,
        repo_root=main_repo_root,
        base_ref=_base_ref,
        head_ref=_head_ref,
    )
    if _diff_result is None:
        # Non-bulk-edit mission — skip silently. check_review_diff_compliance
        # returns None when change_mode is not bulk_edit, which shouldn't
        # happen here given the outer guard, but belt-and-braces.
        pass
    elif not _diff_result.passed:
        render_diff_check_failure(_diff_result, rich_console)
        raise typer.Exit(1)
    elif _diff_result.warnings:
        # Surface manual_review notes but don't block.
        for _w in _diff_result.warnings:
            rich_console.print(f"[yellow]manual_review:[/] {_w}")


def _reset_workflow_receipts() -> None:
    """Clear the per-invocation commit-receipt accumulator."""
    _WORKFLOW_COMMIT_RECEIPTS.clear()


def _record_receipt(
    destination_ref: str,
    message: str,
    outcome: str,
    *,
    sha: str | None = None,
    wp_id: str | None = None,
) -> None:
    """Record a single workflow commit receipt for the T029 summary."""
    _WORKFLOW_COMMIT_RECEIPTS.append({
        "destination_ref": destination_ref,
        "message": message,
        "outcome": outcome,  # "committed" or "refused"
        "sha": sha,
        "wp_id": wp_id,
    })


def _mark_receipt_refused(*, commit_sha: str) -> None:
    """Mark a previously committed receipt refused after rollback."""
    for receipt in reversed(_WORKFLOW_COMMIT_RECEIPTS):
        if receipt.get("sha") == commit_sha:
            receipt["outcome"] = "refused"
            return


def _restore_status_artifacts(
    *,
    events_path: Path,
    pre_emit_event_size: int,
    status_path: Path,
    pre_emit_status_bytes: bytes | None,
) -> None:
    """Restore canonical status files after a failed workflow commit."""
    try:
        if events_path.exists():
            with events_path.open("ab") as _fh:
                _fh.truncate(pre_emit_event_size)
    except OSError:
        logger.exception("Could not truncate %s on commit failure", events_path)

    try:
        if pre_emit_status_bytes is None:
            status_path.unlink(missing_ok=True)
        else:
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_bytes(pre_emit_status_bytes)
    except OSError:
        logger.exception("Could not restore %s on commit failure", status_path)


def _safe_commit_recovery_commit_sha(exc: BaseException) -> str | None:
    """Return commit SHA when a chained safe_commit recovery failure committed."""
    current: BaseException | None = exc
    while current is not None:
        if isinstance(current, SafeCommitRecoveryFailed) and current.commit_sha is not None:
            return current.commit_sha
        current = current.__cause__
    return None


def _transaction_path_for(
    *,
    source_path: Path,
    repo_root: Path,
    worktree_root: Path,
) -> Path:
    """Map a canonical-repo path to the same relative path in a worktree."""
    source_path = source_path.resolve()
    try:
        relative_path = source_path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ValueError(
            f"Refusing to mirror path outside repo/worktree scope: {source_path}"
        ) from exc
    return worktree_root / relative_path


def _load_coord_branch_meta(feature_dir: Path) -> tuple[str | None, str | None, str | None]:
    """Read (coordination_branch, mission_id, mid8) from meta.json.

    Returns ``(None, None, None)`` for legacy missions or when meta.json
    is missing / unreadable. Never raises.
    """
    from specify_cli.lanes.branch_naming import resolve_mid8
    from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed

    try:
        meta = load_meta_fail_closed(feature_dir)
    except (OSError, MissionMetaReadError):  # corrupt/unreadable meta.json is legacy-tolerated here
        return (None, None, None)
    if not isinstance(meta, dict):
        return (None, None, None)
    coord = meta.get("coordination_branch") or None
    mid = meta.get("mission_id") or None
    # Route the mission_id truncation through the canonical resolver (FR-001);
    # the isinstance/>= 8 guard keeps the ``else None`` fallback byte-identical.
    mid8 = meta.get("mid8") or (
        resolve_mid8(feature_dir.name, mission_id=mid)
        if isinstance(mid, str) and len(mid) >= 8
        else None
    )
    return (coord, mid, mid8)


def _canonical_status_feature_dir(main_repo_root: Path, mission_slug: str) -> Path:
    """Resolve the canonical read-side mission directory for status state.

    Routes through the single guarded read-side seam
    (:func:`resolve_handle_to_read_path`, WP01/IC-01): the seam reads the
    PRIMARY ``meta.json`` to learn the declared identity, runs the ONE
    sanctioned mid8 cascade (``resolve_declared_mid8``), and returns the
    existence-gated topology-aware directory. This subsumes the prior bespoke
    ``candidate_feature_dir_for_mission`` → ``_load_coord_branch_meta`` →
    ``resolve_mid8`` → ``resolve_mission_read_path`` cascade. (FR-002, C-007)

    Subsumption note: the retired ``_mid8_for_mission_read_path`` read the COORD
    branch's meta via ``_load_coord_branch_meta`` to derive mid8, while the seam
    anchors on PRIMARY meta. mid8 is mission *identity* (``mission_id`` / ``mid8``
    are identical on both surfaces), so the primary anchor yields the same mid8;
    no caller of ``_canonical_status_feature_dir`` consumed any coord-branch-only
    meta field (all three read callers only need the resolved directory).
    """
    from specify_cli.missions._read_path_resolver import resolve_handle_to_read_path

    return resolve_handle_to_read_path(main_repo_root, mission_slug)


def _merge_event_log_bytes(existing: bytes, incoming: bytes) -> bytes:
    """Compatibility wrapper for the explicit coordination merge contract."""
    from specify_cli.coordination.status_service import (
        merge_append_preserving_coordination_event_log_bytes,
    )

    return merge_append_preserving_coordination_event_log_bytes(existing, incoming)


def _commit_via_coordination_transaction(
    *,
    coord_branch: str,
    repo_root: Path,
    mission_slug: str,
    paths: list[Path],
    message: str,
    operation: str,
    mission_id: str,
    mid8: str,
    wp_id: str,
) -> CommitReceipt:
    """Commit workflow changes via BookkeepingTransaction."""
    from specify_cli.coordination.transaction import (
        BookkeepingPolicyRefused,
        BookkeepingTransaction,
    )

    try:
        with BookkeepingTransaction.acquire(
            repo_root=repo_root,
            mission_id=mission_id,
            mission_slug=mission_slug,
            mid8=mid8,
            destination_ref=coord_branch,
            operation=operation,
        ) as txn:
            for path in paths:
                if not path.exists():
                    continue
                if path.resolve().is_relative_to(txn.worktree_root.resolve()):
                    txn.stage_path(path)
                    continue
                txn_path = _transaction_path_for(
                    source_path=path,
                    repo_root=repo_root,
                    worktree_root=txn.worktree_root,
                )
                if txn_path.resolve() == path.resolve():
                    txn.stage_path(path)
                else:
                    incoming = path.read_bytes()
                    # #1602: the canonical event log is append-only. Never let a
                    # main-checkout copy overwrite (clobber) the coordination
                    # branch's lane history — union-merge instead so existing
                    # coord events always survive.
                    if path.name == _STATUS_EVENTS_FILENAME and txn_path.exists():
                        incoming = _merge_event_log_bytes(
                            txn_path.read_bytes(), incoming
                        )
                    txn.write_artifact(txn_path, incoming)
            # WP04/T015 (FR-004, #2861): the transactional status emit already
            # committed this lane transition to the coord worktree, so the
            # staged paths are byte-identical to HEAD. Use the idempotent commit
            # so that empty second commit is a clean no-op (pinned at HEAD)
            # instead of the "nothing to commit" refusal that blocked #2861.
            receipt = txn.commit_idempotent(message)
    except BookkeepingPolicyRefused as policy_exc:
        _record_receipt(
            coord_branch,
            message,
            "refused",
            wp_id=wp_id,
        )
        print(
            f"Error: Bookkeeping policy refused {operation}: "
            f"{policy_exc.verdict.error_code}: {policy_exc.verdict.message}"
        )
        raise typer.Exit(1) from policy_exc

    _record_receipt(
        coord_branch,
        message,
        "committed",
        sha=receipt.commit_sha,
        wp_id=wp_id,
    )
    return receipt


def _render_lane_auto_rebase_failure(exc: BaseException) -> None:
    from specify_cli.lanes.lifecycle_sync import LaneAutoRebaseSyncError

    if not isinstance(exc, LaneAutoRebaseSyncError):
        print(f"Error: {exc}")
        return

    payload = exc.to_dict()
    print(f"Error: {payload['error_code']}: {payload['halt_reason']}")
    print(f"  lane_id: {payload['lane_id']}")
    print(f"  lane_worktree_path: {payload['lane_worktree_path']}")
    print(f"  coordination_branch: {payload['coordination_branch']}")
    print(f"  coordination_head: {payload['coordination_head']}")


def _sync_lane_after_coordination_commit(
    *,
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    coord_branch: str,
) -> None:
    from specify_cli.lanes.lifecycle_sync import sync_lane_after_coordination_commit

    # No ``feature_dir``: ``sync_lane_after_coordination_commit`` self-resolves the
    # LANE_STATE (lanes.json) read onto the PRIMARY anchor (#2185). Passing the
    # coord-aware STATUS dir here previously routed the lanes read onto the husk.
    sync_lane_after_coordination_commit(
        repo_root=repo_root,
        mission_slug=mission_slug,
        wp_id=wp_id,
        coordination_branch=coord_branch,
    )


def _revert_coordination_commit(receipt: CommitReceipt) -> None:
    """Undo a lifecycle coordination commit after lane sync refusal."""
    # WP04/T015 (FR-004, #2861): a no-op receipt means THIS transaction created
    # no commit — the transition commit belongs to the prior transactional emit
    # (single write authority). ``receipt.commit_sha`` merely pins that
    # pre-existing HEAD, so reverting it would wrongly undo a durable, separate
    # commit. Nothing to roll back here.
    if receipt.is_noop:
        return
    head_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=receipt.worktree_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if head_result.returncode != 0:
        raise RuntimeError(
            "could not inspect coordination worktree HEAD before rollback: "
            f"{(head_result.stderr or head_result.stdout).strip()}"
        )
    if head_result.stdout.strip() != receipt.commit_sha:
        raise RuntimeError(
            "refusing to rollback lifecycle commit because coordination branch "
            f"advanced from {receipt.commit_sha} to {head_result.stdout.strip()}"
        )

    revert_result = subprocess.run(
        [
            "git",
            "-c",
            "commit.gpgsign=false",
            "revert",
            "--no-edit",
            receipt.commit_sha,
        ],
        cwd=receipt.worktree_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if revert_result.returncode != 0:
        raise RuntimeError(
            "failed to rollback lifecycle coordination commit after lane sync "
            f"refusal: {(revert_result.stderr or revert_result.stdout).strip()}"
        )


def _workflow_placement_seam(repo_root: Path, mission_slug: str) -> PlacementSeam:
    """Construct the ONE placement-seam instance every workflow.py wrapper shares.

    read-surface-ssot-closeout WP04 (T017/T018): the pre-existing
    ``_resolve_workflow_placement`` (coord-primary-partition-lock) was the
    lone raw ``placement_seam(...)`` construction in this module — a pinned
    invariant (``test_workflow_has_exactly_one_placement_seam_call_site``).
    Adding the sibling READ-side wrapper (:func:`_resolve_workflow_read_dir`)
    for IC-04's routing without a SECOND raw construction means both wrappers
    now share this one constructor instead of each importing/calling
    ``placement_seam`` independently — the invariant's *intent* (no per-site
    re-derivation) is preserved even though its enclosing-function detail
    moves here.
    """
    from mission_runtime import placement_seam

    return placement_seam(repo_root, mission_slug)


def _resolve_workflow_placement(
    *, repo_root: Path, mission_slug: str, kind: MissionArtifactKind
) -> CommitTarget:
    """Resolve the write :class:`CommitTarget` for ``kind`` via the placement seam.

    The SINGLE choke point every workflow.py lifecycle/status write site
    routes through (coord-primary-partition-lock C-001 / C-005): a thin
    wrapper over :func:`_workflow_placement_seam` — never re-derived
    inline at each write site (reviewer guidance explicitly forbids 4x
    inlining the seam call across a 2800-line module). Callers that already
    hold identity metadata for a DIFFERENT purpose (e.g. the
    ``coord_branch``/``mission_id``/``mid8`` triple
    :func:`_load_coord_branch_meta` reads to select the BookkeepingTransaction
    mechanism) keep reading that separately — this helper answers only "where
    does a write of this kind land", the seam's one job.
    """
    return _workflow_placement_seam(repo_root, mission_slug).write_target(kind)


def _resolve_workflow_read_dir(
    *, repo_root: Path, mission_slug: str, kind: MissionArtifactKind
) -> Path:
    """Resolve the read directory for ``kind`` via the placement seam (IC-04/T017).

    The sibling READ-side choke point to :func:`_resolve_workflow_placement`:
    every workflow.py site that read a mission directory through the
    kind-blind ``resolve_feature_dir_for_mission`` husk (NFR-001 /
    Directive-041 — do not pin the old kind-blind coord husk) now routes
    through this ONE wrapper over :func:`_workflow_placement_seam`
    ``.read_dir(kind)`` instead of re-deriving the seam call inline at each
    read site.
    """
    read_dir: Path = _workflow_placement_seam(repo_root, mission_slug).read_dir(kind)
    return read_dir


def _resolve_legacy_porcelain_root(
    repo_root: Path, mission_slug: str | None, mid8: str | None
) -> Path:
    """Return the git worktree root the legacy porcelain pre-check must run in.

    coord-commit-integrity WP01/T004 (FR-002(b), #2684). A status file that
    lives in a materialized ``.worktrees/<slug>-<mid8>-coord`` sub-worktree is
    *gitignored* from ``repo_root``: ``git status --porcelain`` at ``repo_root``
    reports it as clean, which the caller reads as a phantom "already committed"
    early-return. Run the pre-check in the coord worktree instead, so the file
    is correctly seen as dirty.

    The coord sub-worktree is resolved through the ONE canonical authority,
    :meth:`CoordinationWorkspace.resolve` (shared with WP04 — do NOT fork a
    second resolver). :meth:`CoordinationWorkspace.worktree_path` is pure, so
    the existence pre-check never materializes a spurious worktree for a
    genuinely coord-less / flat mission whose paths really do live in
    ``repo_root`` (the correct root in that case).
    """
    if not mid8 or not mission_slug:
        return repo_root
    from specify_cli.coordination.workspace import (
        CoordinationWorkspace,
        CoordinationWorkspaceBranchMismatch,
        CoordinationWorkspaceIdentityUnresolved,
    )

    try:
        coord_worktree = CoordinationWorkspace.worktree_path(repo_root, mission_slug, mid8)
    except CoordinationWorkspaceIdentityUnresolved:
        # Unresolved identity ⇒ paths live in repo_root (mid8 is guarded non-empty
        # above, so this is belt-and-suspenders; a genuine programming error is no
        # longer masked as a repo_root fallback — renata #3 narrowing).
        return repo_root
    if not coord_worktree.exists():
        # No coord worktree on disk ⇒ this mission's paths live in repo_root.
        return repo_root
    try:
        return CoordinationWorkspace.resolve(repo_root, mission_slug, mid8)
    except (
        OSError,
        subprocess.SubprocessError,
        CoordinationWorkspaceBranchMismatch,
        CoordinationWorkspaceIdentityUnresolved,
    ):
        # Resolve genuinely refused (git worktree add / branch-mismatch / OS
        # error) ⇒ fall back to repo_root for the porcelain pre-check. Narrowed
        # from a blind ``except Exception`` so an unexpected programming error
        # propagates (observable) instead of masquerading as a repo_root fallback.
        return repo_root


def _commit_via_legacy_safe_commit(
    *,
    repo_root: Path,
    target_branch: str,
    paths: list[Path],
    message: str,
    wp_id: str,
    mission_slug: str | None = None,
    mid8: str | None = None,
) -> None:
    """Commit workflow changes directly on legacy mission branches."""
    # #2684: nothing-to-commit is a benign no-op, not a hard failure. When the
    # phase-1 snapshot authority is ON, the claim's status transition is emitted
    # AND committed by the transactional emit path (``start_implementation_status``)
    # *before* this legacy follow-up commit runs, and the WP-file dual-write is
    # disabled — so every requested path is already byte-identical to HEAD and
    # there is genuinely nothing left to stage. Pre-#2684 the redundant ``git
    # commit`` merely warned; the mission's stricter transactional emit now makes
    # the empty commit hard-fail (and rolls the event log back), refusing an
    # already-persisted claim. Detect the no-op and return successfully WITHOUT
    # rolling back the (correctly-persisted) event log. ``git status --porcelain``
    # reports both modified AND untracked paths, so a genuine first-time write
    # (new status.json) still has a non-empty pending set and proceeds to commit.
    #
    # WP01/T004 (FR-002(b)): run the pre-check in the resolved worktree root, not
    # ``repo_root`` — a gitignored ``.worktrees/`` status file reads as clean
    # from ``repo_root`` and would trip a phantom "already committed" no-op.
    porcelain_root = _resolve_legacy_porcelain_root(repo_root, mission_slug, mid8)
    porcelain = subprocess.run(
        ["git", "status", "--porcelain", "--", *[str(p) for p in paths]],
        cwd=porcelain_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if porcelain.returncode == 0 and not porcelain.stdout.strip():
        # State already present at HEAD (persisted by the transactional emit).
        _record_receipt(
            target_branch,
            message,
            "committed",
            sha=None,
            wp_id=wp_id,
        )
        return

    # Legacy mission-branch workflow commits land on ``target_branch`` (a lane /
    # mission branch), which is normally not protected. STANDARD asserts no
    # protected-branch flow: a protected ``target_branch`` (legacy missions
    # tracking ``main``) is REFUSED by the guard, never waived (FR-008).
    result = safe_commit(
        repo_root=repo_root,
        worktree_root=repo_root,
        target=CommitTarget(ref=target_branch),
        message=message,
        paths=tuple(paths),
        capability=GuardCapability.STANDARD,
    )
    _record_receipt(
        target_branch,
        message,
        "committed",
        sha=getattr(result, "sha", None),
        wp_id=wp_id,
    )


def _print_commit_summary(*, command_name: str, json_output: bool = False) -> None:
    """T029: render the accumulated commit summary to the terminal.

    Human format::

        [implement] Commits recorded:
          - <branch>  <message>  ✓ committed
          - <branch>  <message>  ✗ refused

    JSON format: prints ``{"commits": [...]}`` on its own line so
    machine consumers can parse the trailing record.
    """
    if not _WORKFLOW_COMMIT_RECEIPTS:
        return
    if json_output:
        import json as _json
        print(_json.dumps({"commits": list(_WORKFLOW_COMMIT_RECEIPTS)}))
        return
    print(f"[{command_name}] Commits recorded:")
    for receipt in _WORKFLOW_COMMIT_RECEIPTS:
        glyph = "[ok]" if receipt.get("outcome") == "committed" else "[refused]"
        print(
            f"  - {receipt['destination_ref']}  {receipt['message']}  {glyph}"
        )


def _render_charter_context(
    repo_root: Path, action: str, *, mission_type: str | None = None
) -> str:
    """Render charter context for workflow prompts.

    WP11 (T062/B-8/FR-012): ``mission_type`` is forwarded so the action
    doctrine bundle resolves for the mission grain instead of degrading to a
    typeless (empty) bundle.
    """
    try:
        context = build_charter_context(
            repo_root, action=action, mark_loaded=True, mission_type=mission_type
        )
        return context.text
    except Exception as exc:
        return f"Governance: unavailable ({exc})"


app = typer.Typer(name="action", help="Mission action commands that display prompts and instructions for agents", no_args_is_help=True)


def _ensure_target_branch_checked_out(repo_root: Path, mission_slug: str) -> tuple[Path, str]:
    """Resolve branch context without auto-checkout (respects user's current branch).

    Returns the planning repo root and the user's current branch.
    Shows a consistent branch banner.

    Routes target-branch resolution through ``resolve_action_context`` (FR-033:
    MissionExecutionContext hardening — route residue surfaces).  This is the canonical
    OHS entry point; ``target_branch`` is read from its returned MissionExecutionContext
    rather than derived independently.
    """
    from mission_runtime import ActionContextError, resolve_action_context
    from specify_cli.core.git_ops import get_current_branch

    main_repo_root = get_main_repo_root(repo_root)

    # Check for detached HEAD using robust branch detection
    current_branch = get_current_branch(main_repo_root)
    if current_branch is None:
        print("Error: Detached HEAD — checkout a branch before continuing.")
        raise typer.Exit(1)

    # Canonical target-branch resolution through the OHS entry point.
    try:
        _ctx = resolve_action_context(
            main_repo_root,
            action="tasks",
            feature=mission_slug,
        )
        target = _ctx.target_branch
    except ActionContextError:
        # Fall back to the direct helper if execution context cannot be resolved
        # (e.g. mission directory not yet created during early planning).
        target = get_feature_target_branch(main_repo_root, mission_slug)

    # Show consistent branch banner
    if current_branch == target:
        print(f"Branch: {current_branch} (target for this mission)")
    else:
        print(f"Branch: on '{current_branch}', mission targets '{target}'")

    # Return current branch (no checkout performed)
    return main_repo_root, current_branch


def _find_mission_slug(
    explicit_mission: str | None = None,
    repo_root: Path | None = None,
) -> str:
    """Require an explicit mission slug (no auto-detection).

    When repo_root is supplied the handle is resolved via the canonical
    mission resolver which handles ambiguous numeric-prefix handles, mid8
    prefixes, and full ULID forms.

    Args:
        explicit_mission: Mission slug provided explicitly.
        repo_root: Repository root; if provided, enables canonical resolver.

    Returns:
        Mission slug (e.g., "008-unified-python-cli")

    Raises:
        typer.Exit: If mission slug is not provided.
    """
    if not explicit_mission or not explicit_mission.strip():
        print("Error: --mission <slug> is required")
        raise typer.Exit(1)

    raw_handle = explicit_mission.strip()
    if repo_root is not None:
        from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

        try:
            legacy_dir = _resolve_workflow_read_dir(
                repo_root=get_main_repo_root(repo_root),
                mission_slug=raw_handle,
                kind=MissionArtifactKind.PRIMARY_METADATA,
            )
        except MissionSelectorAmbiguous as exc:
            # #450: this short-circuit call runs BEFORE resolve_mission_handle
            # below, so an ambiguous handle must not propagate uncaught — these
            # commands have no --json mode, so a plain "Error: ..." + exit 1
            # (matching this function's other --mission-required error case
            # above) is the whole fix, mirroring #241's try/except shape.
            print(f"Error: {exc}")
            raise typer.Exit(1) from exc
        if legacy_dir.exists():
            # F-001: the candidate resolver canonicalizes mid8/ULID/numeric
            # handles, so the resolved directory's NAME — not the raw operator
            # handle — is the canonical mission slug downstream consumers need.
            return legacy_dir.name
        try:
            resolved = resolve_mission_handle(raw_handle, repo_root)
            return resolved.mission_slug
        except (SystemExit, typer.Exit):
            if legacy_dir.exists():
                return legacy_dir.name
            raise

    return raw_handle




def _preview_claimable_wp_for_mission(repo_root: Path, mission_slug: str):
    """Return the shared claimable preview for *mission_slug*, if tasks exist.

    WP04 / T016 / FR-002: tasks/ and dependency reads route to the PRIMARY
    checkout via ``PlacementSeam.read_dir(WORK_PACKAGE_TASK)`` so a
    coord-topology mission (whose tasks/ live on PRIMARY, not the STATUS-only
    coord surface) is never reported as having no tasks. The status-event read
    uses ``PlacementSeam.read_dir(STATUS_STATE)`` so lanes come from the
    authoritative coord surface — never a worktree-local copy, which may lag
    the latest status commit (dependency gate invariant preserved).
    """
    from runtime.next.discovery import preview_claimable_wp

    main_root = get_main_repo_root(repo_root)
    # WORK_PACKAGE_TASK is PRIMARY-partition: routes to the primary checkout
    # regardless of coord topology (no shadowing by STATUS-only coord husk).
    planning_dir = _resolve_workflow_read_dir(
        repo_root=main_root,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.WORK_PACKAGE_TASK,
    )
    if not (planning_dir / "tasks").is_dir():
        return None
    # status_dir: coord-aware so events come from the coord surface under coord
    # topology (STATUS_STATE is the COORD-partition leg).
    status_dir = _resolve_workflow_read_dir(
        repo_root=main_root,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.STATUS_STATE,
    )
    return preview_claimable_wp(planning_dir, status_dir=status_dir)




def _analysis_report_gate_dir(main_repo_root: Path, mission_slug: str) -> Path:
    """Resolve the mission dir the implement gate reads ``analysis-report.md`` from.

    #1989: this MUST be the topology-blind primary checkout — where
    ``record-analysis`` writes the report — NOT the coord-aware
    ``candidate_feature_dir_for_mission`` (which resolves to the coordination
    worktree once one exists, and that worktree lacks the report + ``spec.md`` for
    the freshness hash, so the gate would falsely report it missing). Extracted as
    a named seam so the read-anchor decision is unit-testable in isolation.
    """
    # read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-004: routed
    # through the kind-aware seam (ANALYSIS_REPORT is a PRIMARY-partition kind)
    # instead of the kind-blind coord husk. For a PRIMARY-partition kind the
    # seam short-circuits to PRIMARY before any coord probe, so it never lands
    # on the coordination worktree the way ``candidate_feature_dir_for_mission``
    # / ``resolve_feature_dir_for_mission`` (both kind-blind) can.
    return _resolve_workflow_read_dir(
        repo_root=main_repo_root,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.ANALYSIS_REPORT,
    )


def _mission_id_for_claim(main_repo_root: Path, mission_slug: str) -> str:
    """Resolve claim identity from the canonical primary planning surface."""
    # read-side-seam-primary-primitive-closure-01KYKMMT WP05/FR-004: meta.json
    # lives only on PRIMARY (PRIMARY_METADATA is a PRIMARY-partition kind), so
    # the kind-aware seam resolves it identically for every topology without
    # ever consulting the coordination worktree.
    primary_dir = _resolve_workflow_read_dir(
        repo_root=main_repo_root,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.PRIMARY_METADATA,
    )
    return resolve_mission_identity(primary_dir).mission_id


def _require_current_analysis_report(feature_dir: Path, repo_root: Path, mission_slug: str) -> None:
    """Block implementation until `/spec-kitty.analyze` is persisted and fresh."""
    from specify_cli.analysis_report import (
        ANALYSIS_REPORT_REASON_CARRIER_FORMAT,
        check_analysis_report_current,
    )

    analysis_freshness = check_analysis_report_current(feature_dir, repo_root)
    if analysis_freshness.ok:
        return

    # Header line is always emitted first, in every branch.
    print("Error: analysis_report_required: /spec-kitty.analyze must be run before implementation.")

    if analysis_freshness.reason == ANALYSIS_REPORT_REASON_CARRIER_FORMAT:
        print(
            "  Reason: analysis-report.md is in carrier format (analysis-findings/v1) — written directly\n"
            "          rather than via record-analysis. The implement gate requires the persisted\n"
            "          outer-wrapper format (artifact_type: spec-kitty.analysis-report)."
        )
        print(
            "  Recovery: spec-kitty agent mission record-analysis "
            f"--mission {mission_slug} --input-file {analysis_freshness.path}"
        )
    elif analysis_freshness.missing:
        print(f"  Missing: {analysis_freshness.path}")
        print("  Run step 1: /spec-kitty.analyze")
        print(
            "  Run step 2: spec-kitty agent mission record-analysis "
            f"--mission {mission_slug} --input-file -"
        )
    elif analysis_freshness.mismatches:
        print(f"  Reason: {analysis_freshness.reason}")
        print("  Stale inputs:")
        for artifact_name in sorted(analysis_freshness.mismatches):
            print(f"    - {artifact_name}")
        print(f"  Run: /spec-kitty.analyze --mission {mission_slug}")
    else:
        if analysis_freshness.reason:
            print(f"  Reason: {analysis_freshness.reason}")
        print(f"  Run: /spec-kitty.analyze --mission {mission_slug}")

    raise typer.Exit(1)


#: Help text for the dispatch→claim resolved-binding options (FR-014). Shared by
#: ``implement()`` and ``review()`` so the wording stays canonical in both.
_MODEL_OPT_HELP = "Dispatch-resolved model asserted against the correlated Op record (requires --invocation-id; never the frontmatter recommendation)"
_PROFILE_OPT_HELP = (
    "Agent profile id — a dispatch registry / Op record profile or a local "
    "charter profile (the same ids `agent profile show` resolves). When "
    "omitted, the work package's frontmatter agent_profile is used."
)
_INVOCATION_ID_OPT_HELP = "Correlated Op record ULID whose mission, WP, action, profile, and model are authoritative"


def _read_op_started_event(invocation_id: str, repo_root: Path) -> OpStartedEvent:
    """Read and validate the durable started event for an invocation assertion.

    The ID is validated before path composition. ``InvocationWriter`` then
    enforces resolved containment under ``kitty-ops``. The embedded ID must
    equal the requested ID so a renamed or substituted record cannot supply
    provenance for another claim.
    """
    from specify_cli.invocation.record import (
        OpStartedEvent,
        parse_op_event,
        validate_invocation_id,
    )
    from specify_cli.invocation.writer import InvocationWriter

    validate_invocation_id(invocation_id)
    try:
        path = InvocationWriter(repo_root).invocation_path(invocation_id)
        if not path.exists():
            raise ValueError(f"Op record not found for invocation_id={invocation_id!r}")
        lines = path.read_text(encoding="utf-8").splitlines()
        if not lines:
            raise ValueError(f"Op record is empty for invocation_id={invocation_id!r}")
        event = parse_op_event(json.loads(lines[0]))
        if not isinstance(event, OpStartedEvent):
            raise ValueError(
                f"First Op record is not a started event for invocation_id={invocation_id!r}"
            )
        if event.invocation_id != invocation_id:
            raise ValueError(
                "Op record invocation_id "
                f"{event.invocation_id!r} does not match requested {invocation_id!r}"
            )
        return event
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            f"Could not read Op record for invocation_id={invocation_id!r}: {exc}"
        ) from exc


def _validate_op_claim_correlation(
    *,
    event: OpStartedEvent,
    mission_id: str | None,
    wp_id: str | None,
    action: str | None,
) -> None:
    """Reject durable Op evidence that does not identify this exact claim."""
    recorded_mission_id = getattr(event, "mission_id", None)
    recorded_wp_id = getattr(event, "wp_id", None)
    recorded_action = getattr(event, "action", None)
    if mission_id is None or recorded_mission_id != mission_id:
        raise ValueError(
            "Dispatch Op mission identity does not match claim target: "
            f"recorded={recorded_mission_id!r}, target={mission_id!r}"
        )
    if wp_id is None or recorded_wp_id != wp_id:
        raise ValueError(
            "Dispatch Op work package does not match claim target: "
            f"recorded={recorded_wp_id!r}, target={wp_id!r}"
        )
    if action is None or recorded_action != action:
        raise ValueError(
            "Dispatch Op action does not match claim target: "
            f"recorded={recorded_action!r}, target={action!r}"
        )


def _resolved_profile_version(profile_id: str | None, repo_root: Path) -> str | None:
    """Read the resolved profile schema version from the canonical registry.

    #4120: resolves through ``ProfileRegistry.resolve_local`` — every local
    layer, same activation gate — not the dispatch routing catalog
    (``resolve``), which excludes the doctrine project layer by design and
    therefore rejected every project-local charter-activated profile id with
    an empty ``Available: []``. An operator-supplied ``--profile <id>`` names
    the same ids ``agent profile show`` resolves and ``finalize-tasks``
    records in WP ``agent_profile`` frontmatter; those must resolve here even
    with no hosted registry / dispatch Op in play.
    """
    if profile_id is None:
        return None
    try:
        from specify_cli.invocation.registry import ProfileRegistry

        return str(
            ProfileRegistry(repo_root).resolve_local(profile_id).schema_version
        )
    except Exception as exc:
        raise ValueError(
            f"Could not resolve --profile {profile_id!r}: {exc}. "
            "Omit --profile to use the work package's own frontmatter "
            "agent_profile instead."
        ) from exc


def _resolved_model_provider(model_id: str | None) -> str | None:
    """Look up a dispatch model's provider in the canonical routing catalog."""
    if model_id is None:
        return None
    try:
        from charter.model_routing import load as routing_load

        loaded = routing_load()
        if loaded is None:
            raise ValueError("the canonical routing catalog is unavailable")
        model = next(
            (candidate for candidate in loaded.catalog.models if candidate.id == model_id),
            None,
        )
        if model is None:
            raise ValueError("model is absent from the canonical routing catalog")
        return str(model.provider)
    except Exception as exc:
        raise ValueError(
            f"Could not resolve dispatched model {model_id!r}: {exc}"
        ) from exc


def _resolve_dispatch_binding(
    *,
    model: str | None,
    profile: str | None,
    invocation_id: str | None,
    repo_root: Path,
    mission_id: str | None = None,
    wp_id: str | None = None,
    action: str | None = None,
) -> ResolvedBinding:
    """Build the genuinely dispatch-resolved binding for a claim seam (FR-014, T037).

    Sources the resolved ``model`` + ``agent_profile`` from the invocation/Op
    path — the ``--model``/``--profile`` values the orchestrator threaded from
    ``invocation/executor.py``'s winning candidate + ``registry.resolve``, and,
    when ``--invocation-id`` is supplied, the authoritative ``profile_id`` read
    back from the Op record. Any supplied value that disagrees with the durable
    Op evidence is rejected; no caller label silently overrides provenance.

    **NEVER** reads the frontmatter ``agent_profile`` string (C-007 / INV-6) —
    this function has no access to frontmatter by construction, so a resolved
    binding can never be a frontmatter copy. When no dispatch context was
    supplied, returns an explicit-absence binding: the claim seam records the
    model-absent sentinel rather than fabricating one (SC-011).
    """
    resolved_profile = profile
    resolved_model: str | None = None
    if invocation_id:
        event = _read_op_started_event(invocation_id, repo_root)
        _validate_op_claim_correlation(
            event=event,
            mission_id=mission_id,
            wp_id=wp_id,
            action=action,
        )
        op_profile = event.profile_id
        op_model = event.model_id
        if profile is not None and profile != op_profile:
            raise ValueError(
                "Dispatch Op profile does not match --profile: "
                f"recorded={op_profile!r}, supplied={profile!r}"
            )
        if model is not None and model != op_model:
            raise ValueError(
                "Dispatch Op model does not match --model: "
                f"recorded={op_model!r}, supplied={model!r}"
            )
        resolved_profile = op_profile
        resolved_model = op_model
    elif model is not None:
        raise ValueError(
            "--model cannot be recorded as resolved actual without correlated "
            "durable dispatch evidence; pass --invocation-id"
        )
    return ResolvedBinding(
        agent_profile=resolved_profile,
        agent_profile_version=_resolved_profile_version(resolved_profile, repo_root),
        model=resolved_model,
        provider=_resolved_model_provider(resolved_model),
    )


@app.command(name="implement")
def implement(
    wp_id: Annotated[str | None, typer.Argument(help="Work package ID (e.g., WP01, wp01, WP01-slug) - auto-detects first planned if omitted")] = None,
    mission: Annotated[str | None, typer.Option("--mission", help="Mission slug")] = None,
    agent: Annotated[str | None, typer.Option("--agent", help="Agent name (required for auto-move to in_progress)")] = None,
    model: Annotated[str | None, typer.Option("--model", help=_MODEL_OPT_HELP)] = None,
    profile: Annotated[str | None, typer.Option("--profile", help=_PROFILE_OPT_HELP)] = None,
    invocation_id: Annotated[str | None, typer.Option("--invocation-id", help=_INVOCATION_ID_OPT_HELP)] = None,
    allow_sparse_checkout: Annotated[
        bool,
        typer.Option(
            "--allow-sparse-checkout",
            help=(
                "Proceed even if legacy sparse-checkout state is detected. "
                "Use of this override is logged. Does not bypass the commit-time "
                "data-loss backstop."
            ),
        ),
    ] = False,
    acknowledge_not_bulk_edit: Annotated[
        bool,
        typer.Option(
            "--acknowledge-not-bulk-edit",
            help="Suppress the bulk-edit inference warning when spec language resembles a bulk edit but the mission is not one.",
        ),
    ] = False,
) -> None:
    """Display work package prompt with implementation instructions.

    This command outputs the full work package prompt content so agents can
    immediately see what to implement, without navigating the file system.

    Automatically moves WP from planned to in_progress (requires --agent to track who is working).

    Examples:
        spec-kitty agent action implement WP01 --agent claude
        spec-kitty agent action implement WP02 --agent claude
        spec-kitty agent action implement wp01 --agent codex
        spec-kitty agent action implement --agent gemini  # auto-detects first planned WP
    """
    # T009: the raw CLI-option surface, unresolved -- threaded through the
    # early preflight phases below instead of five separate positional args.
    request = ImplementRequest(
        wp_id=wp_id,
        mission=mission,
        agent=agent,
        allow_sparse_checkout=allow_sparse_checkout,
        acknowledge_not_bulk_edit=acknowledge_not_bulk_edit,
    )

    # WP06 T029: reset the commit-receipt accumulator for this invocation.
    _reset_workflow_receipts()
    try:
        # Get repo root and feature slug
        repo_root = locate_project_root()
        if repo_root is None:
            print("Error: Could not locate project root")
            raise typer.Exit(1)
        repo_root = get_main_repo_root(repo_root)

        mission_slug = _find_mission_slug(explicit_mission=request.mission, repo_root=repo_root)

        # -- WP05/T021 FR-007: Sparse-checkout preflight -- runs BEFORE any
        # worktree creation or state changes (same surface as merge).
        _executor.implement_sparse_checkout_preflight(repo_root, mission_slug, request.agent, request.allow_sparse_checkout)

        # Ensure planning repo is on the target branch before we start
        # (needed for auto-commits and status tracking inside this command)
        main_repo_root, target_branch = _ensure_target_branch_checked_out(repo_root, mission_slug)

        # Determine which WP to implement
        if request.wp_id:
            normalized_wp_id = _normalize_wp_id(request.wp_id)
        else:
            # Auto-detect first planned WP
            _claimable_preview = _preview_claimable_wp_for_mission(repo_root, mission_slug)
            normalized_wp_id = getattr(_claimable_preview, "wp_id", None)
            if not normalized_wp_id:
                print(f"Error: {_auto_claim_failure_message(_claimable_preview)}")
                raise typer.Exit(1)

        # Find WP file to read dependencies
        wp = _executor.implement_locate_wp(repo_root, mission_slug, normalized_wp_id)

        # C-006 charter precondition: check BEFORE any worktree creation or
        # status transition.
        _executor.implement_check_wp_charter_precondition(main_repo_root, wp, normalized_wp_id)

        wp_meta, _ = read_wp_frontmatter(wp.path)

        # Only gate the not-yet-started claim transition (resumes on an
        # already-in-flight WP are never re-gated).
        _executor.implement_check_dependency_gate(main_repo_root, mission_slug, normalized_wp_id, wp_meta)

        (
            feature_dir,
            has_feedback,
            review_feedback_ref,
            review_feedback_file,
            _review_feedback_source,
        ) = _executor.implement_resolve_feedback_and_gate(main_repo_root, mission_slug, normalized_wp_id, wp)

        # FR-008/#1832 (C-IC05): SINGLE resolution path. Resolve the workspace
        # exactly once here, then *consume* that resolved context for the rest
        # of the implement flow (creation + verification) via
        # ``_ensure_workspace_materialized`` — never re-resolve through a second
        # authority that could independently report "no workspace could be
        # resolved" on a verified read-path.
        #
        # Seam-B (WP03, #3128 / FR-005): this is the canonical `agent action
        # implement` WP-execution write site — refuse a claim invoked from a
        # checkout the mission does not own. write_intent gates the
        # checkout-identity refusal (pure reads leave it False).
        workspace = resolve_workspace_for_wp(main_repo_root, mission_slug, normalized_wp_id, write_intent=True)
        status_execution_mode = "direct_repo" if workspace.resolution_kind == "repo_root" else "worktree"

        def _create_workspace() -> None:
            top_level_implement(
                wp_id=normalized_wp_id,
                mission=mission_slug,
                json_output=False,
                recover=False,
                acknowledge_not_bulk_edit=request.acknowledge_not_bulk_edit,
                actor=agent,
            )

        # FR-005/#3281 (C-006): a retry over an already-materialized lane
        # worktree re-enters the allocator's idempotent reuse-path self-heal
        # instead of the prior bare `workspace.exists: return` short-circuit.
        from specify_cli.lanes.implement_support import reenter_lane_self_heal

        def _reenter_self_heal() -> None:
            reenter_lane_self_heal(main_repo_root, mission_slug, normalized_wp_id)

        _ensure_workspace_materialized(workspace, normalized_wp_id, _create_workspace, _reenter_self_heal)
        workspace_path = workspace.worktree_path

        # Seam C-005 (#3281/FR-007): the claim-ancestry gate runs HERE --
        # POST-materialize (after the self-heal above re-runs the planning-
        # commit + dependency-tip merges), keyed on the MERGED tip, BEFORE any
        # claim status event is emitted below. Never move this above
        # ``_ensure_workspace_materialized`` (or before it in the call
        # sequence) -- evaluating ancestry against a pre-merge HEAD deadlocks
        # an already-approved same-mission dependency that simply has not
        # been merged into this lane's worktree yet.
        from specify_cli.lanes.implement_support import resolve_claim_ancestry_gate

        # The predicate's dependency-status lookup reads the STATUS event log,
        # which is a DIFFERENT surface than the PRIMARY ``feature_dir`` above
        # (WORK_PACKAGE_TASK) for coord-topology missions -- reuse the same
        # coord-aware resolver ``implement_claim_transition`` below consults.
        status_feature_dir = _canonical_status_feature_dir(main_repo_root, mission_slug)
        ancestry = resolve_claim_ancestry_gate(
            main_repo_root, mission_slug, status_feature_dir, normalized_wp_id, workspace_path
        )
        if not ancestry.ok:
            print(
                f"Error: cannot claim {normalized_wp_id}: ancestry could not be "
                f"established after self-heal for: {', '.join(ancestry.missing_refs)}"
            )
            raise typer.Exit(1)

        subtask_ids = [str(item) for item in wp_meta.subtasks if isinstance(item, str)]
        subtask_cmd = " ".join(subtask_ids) if subtask_ids else "<subtask-ids>"

        resolved_binding = _resolve_dispatch_binding(
            model=model,
            profile=profile,
            invocation_id=invocation_id,
            repo_root=main_repo_root,
            mission_id=(
                _mission_id_for_claim(main_repo_root, mission_slug)
                if invocation_id is not None
                else None
            ),
            wp_id=normalized_wp_id,
            action="implement",
        )

        claim_result = _executor.implement_claim_transition(
            repo_root=repo_root,
            main_repo_root=main_repo_root,
            mission_slug=mission_slug,
            normalized_wp_id=normalized_wp_id,
            wp=wp,
            wp_meta=wp_meta,
            feature_dir=feature_dir,
            agent=agent,
            target_branch=target_branch,
            workspace_path=workspace_path,
            status_execution_mode=status_execution_mode,
            resolved_binding=resolved_binding,
        )
        wp = claim_result.wp
        wp_slug = claim_result.wp_slug

        # Fix-mode detection: if the WP was rejected and has review-cycle
        # artifacts, generate a focused fix-mode prompt instead of the full
        # WP prompt. The fix-prompt completely replaces the full WP prompt
        # (not appended to it).
        fix_prompt_file = _executor.implement_try_render_fix_mode_prompt(
            fix_mode_active=claim_result.fix_mode_active,
            feature_dir=feature_dir,
            wp_slug=wp_slug,
            review_feedback_ref=review_feedback_ref,
            review_feedback_file=review_feedback_file,
            workspace_path=workspace_path,
            mission_slug=mission_slug,
            normalized_wp_id=normalized_wp_id,
            repo_root=repo_root,
        )
        if fix_prompt_file is not None:
            return

        # Detect mission type and get deliverables_path for research missions.
        mission_type, deliverables_path = _executor.implement_resolve_mission_type(repo_root, mission_slug)

        # Capture baseline test results (one-time, cached) before the agent starts coding
        _executor.implement_capture_baseline(
            workspace_path=workspace_path,
            target_branch=target_branch,
            normalized_wp_id=normalized_wp_id,
            mission_slug=mission_slug,
            feature_dir=feature_dir,
            wp_slug=wp_slug,
            main_repo_root=main_repo_root,
        )

        prompt_lines = _executor.build_implement_prompt_lines(
            normalized_wp_id=normalized_wp_id,
            wp=wp,
            workspace=workspace,
            workspace_path=workspace_path,
            wp_agent_assignment=claim_result.wp_agent_assignment,
            repo_root=repo_root,
            mission_slug=mission_slug,
            target_branch=target_branch,
            subtask_cmd=subtask_cmd,
            has_feedback=has_feedback,
            review_feedback_ref=review_feedback_ref,
            review_feedback_file=review_feedback_file,
            mission_type=mission_type,
            deliverables_path=deliverables_path,
        )

        _executor.implement_finalize_and_print(
            prompt_lines=prompt_lines,
            mission_slug=mission_slug,
            normalized_wp_id=normalized_wp_id,
            repo_root=repo_root,
            workspace=workspace,
            workspace_path=workspace_path,
            has_feedback=has_feedback,
            review_feedback_ref=review_feedback_ref,
            mission_type=mission_type,
            deliverables_path=deliverables_path,
            subtask_cmd=subtask_cmd,
        )

    except typer.Exit:
        with contextlib.suppress(Exception):
            _print_commit_summary(command_name="implement")
        raise
    except Exception as e:
        # WP06 T029: surface any partial commit summary before exiting,
        # so operators see what got recorded vs. refused.
        with contextlib.suppress(Exception):
            _print_commit_summary(command_name="implement")
        print(f"Error: {e}")
        raise typer.Exit(1)

    # WP06 T029: terminal commit summary for the implement command.
    _print_commit_summary(command_name="implement")


def _resolve_review_context(
    workspace_path: Path,
    repo_root: Path,
    mission_slug: str,
    wp_id: str,
    wp_frontmatter: str,
) -> dict:
    """Resolve git branch and base context for review prompts.

    Determines the WP's branch name, its base branch (what it was branched
    from), and the number of commits unique to this WP so reviewers know
    exactly what to diff against instead of guessing.

    Strategy:
    1. Get actual branch name from the worktree.
    2. Read canonical mission/lane branch state from workspace context and
       lanes.json.
    3. Use that state directly for review diffs; do not reconstruct branch
       names from slug strings.
    """
    ctx: dict = {
        "branch_name": "unknown",
        "base_branch": "unknown",
        "mission_branch": "unknown",
        "lane_branch": "unknown",
        "base_ref": "unknown",
        "commit_count": 0,
    }

    if not workspace_path.exists():
        return ctx

    workspace = resolve_workspace_for_wp(repo_root, mission_slug, wp_id)
    # WP04 / T017 / FR-002: lanes.json (LANE_STATE — PRIMARY-partition) and
    # tasks/ (WORK_PACKAGE_TASK — PRIMARY-partition) both route to the primary
    # checkout.  Under coord topology, candidate_feature_dir_for_mission returned
    # the STATUS-only coord husk (no lanes.json, no tasks/) — a wrong-leg read.
    feature_dir = _resolve_workflow_read_dir(
        repo_root=repo_root,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.WORK_PACKAGE_TASK,
    )
    # lanes.json is LANE_STATE (PRIMARY-partition) — use its truthful kind so a
    # future LANE_STATE re-partition does not silently misroute.
    _lanes_dir = _resolve_workflow_read_dir(
        repo_root=repo_root,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.LANE_STATE,
    )
    lanes_manifest = None
    try:
        from specify_cli.lanes.persistence import read_lanes_json

        lanes_manifest = read_lanes_json(_lanes_dir)
    except Exception:
        lanes_manifest = None

    mission_branch = "unknown"
    if lanes_manifest is not None and lanes_manifest.mission_branch:
        mission_branch = lanes_manifest.mission_branch
    elif workspace.context is not None and workspace.context.base_branch:
        mission_branch = workspace.context.base_branch
    ctx["mission_branch"] = mission_branch

    if workspace.resolution_kind == "repo_root":
        return _executor.review_context_for_repo_root_workspace(
            repo_root=repo_root, feature_dir=feature_dir, wp_id=wp_id, ctx=ctx
        )

    return _executor.review_context_for_worktree_branch(
        repo_root=repo_root,
        mission_slug=mission_slug,
        workspace=workspace,
        workspace_path=workspace_path,
        mission_branch=mission_branch,
        wp_frontmatter=wp_frontmatter,
        ctx=ctx,
    )


def _find_first_for_review_wp(repo_root: Path, mission_slug: str) -> str | None:
    """Find the first WP file with lane: "for_review".

    Args:
        repo_root: Repository root path
        mission_slug: Feature slug

    Returns:
        WP ID of first for_review task, or None if not found
    """
    # WP04 / T017 / FR-002: tasks/ reads route through the planning seam
    # (WORK_PACKAGE_TASK → PRIMARY) so coord-topology missions find tasks/ on
    # the primary checkout, not the STATUS-only coord husk.
    # resolve_planning_read_dir is cwd-invariant for PRIMARY-partition kinds:
    # primary_feature_dir_for_mission anchors on get_main_repo_root(repo_root),
    # so cwd / walk-up / repo_root all resolve the same primary dir — the
    # multi-branch walk was vestigial after WP04.
    # The STATUS leg uses PlacementSeam.read_dir(STATUS_STATE) so events come
    # from the authoritative coord surface under coord topology (C-001).
    tasks_dir = (
        _resolve_workflow_read_dir(
            repo_root=repo_root,
            mission_slug=mission_slug,
            kind=MissionArtifactKind.WORK_PACKAGE_TASK,
        )
        / "tasks"
    )

    if not tasks_dir.exists():
        return None

    # Find all WP files
    wp_files = sorted(tasks_dir.glob("WP*.md"))

    # Load lanes from canonical event log (lane is event-log-only).
    # WP04: status events stay on the coord-aware resolver so coord-topology
    # missions read the authoritative event log, not the primary decoy (C-001).
    _status_feature_dir = _resolve_workflow_read_dir(
        repo_root=repo_root,
        mission_slug=mission_slug,
        kind=MissionArtifactKind.STATUS_STATE,
    )
    _fr_events = []
    try:
        from specify_cli.status import read_events as _fr_read_events
        from specify_cli.status import reduce as _fr_reduce

        _fr_events = _fr_read_events(_status_feature_dir)
        _fr_snapshot = _fr_reduce(_fr_events) if _fr_events else None
        _fr_lanes: dict = {}
        if _fr_snapshot:
            for _fr_wp_id, _fr_state in _fr_snapshot.work_packages.items():
                _fr_lanes[_fr_wp_id] = Lane(_fr_state.get("lane", Lane.PLANNED))
    except Exception:
        _fr_lanes = {}

    def _is_review_claimed(_wp_id: str) -> bool:
        for _event in reversed(_fr_events):
            if getattr(_event, "wp_id", None) == _wp_id:
                return bool(
                    _event.to_lane == Lane.IN_REVIEW  # new canonical shape
                    or (
                        _event.to_lane == Lane.IN_PROGRESS  # legacy shape
                        and _event.review_ref == "action-review-claim"
                    )
                )
        return False

    for wp_file in wp_files:
        content = wp_file.read_text(encoding="utf-8-sig")
        frontmatter, _, _ = split_frontmatter(content)
        wp_id = extract_scalar(frontmatter, "work_package_id")
        if wp_id and _fr_lanes.get(wp_id, Lane.PLANNED) == Lane.FOR_REVIEW:
            return wp_id

    for wp_file in wp_files:
        content = wp_file.read_text(encoding="utf-8-sig")
        frontmatter, _, _ = split_frontmatter(content)
        wp_id = extract_scalar(frontmatter, "work_package_id")
        if wp_id and _fr_lanes.get(wp_id, Lane.PLANNED) in {Lane.IN_PROGRESS, Lane.IN_REVIEW} and _is_review_claimed(wp_id):
            return wp_id

    return None


def _prepare_review_workspace(
    workspace: ResolvedWorkspace,
    main_repo_root: Path,
    wp_id: str,
    agent: str | None,
) -> ResolvedWorkspace:
    """Validate/create the review workspace, then acquire review isolation.

    Order is load-bearing (#1833 AC-D2): ``ReviewLock`` persists its lock file
    INSIDE the workspace (``.spec-kitty/review-lock.json``), so acquiring it
    before the worktree exists used to mint a husk directory. The workspace
    existence/creation block must succeed first; only then is the lock
    acquired, and a failed ``git worktree add`` is a hard error (not a
    warning), leaving no lock behind.
    """
    workspace_path = workspace.worktree_path

    # A husk (directory without a .git entry) is absent-but-blocked: never
    # silently recreate a worktree on top of it — that hides the anomaly.
    if workspace.is_husk:
        print(f"Error: {husk_resolution_error(workspace_path)}")
        raise typer.Exit(1)

    if not workspace.exists:
        # Ensure .worktrees directory exists
        worktrees_dir = main_repo_root / ".worktrees"
        worktrees_dir.mkdir(parents=True, exist_ok=True)

        branch_name = workspace.branch_name
        if branch_name is None:
            print(f"Error: cannot create review workspace {workspace_path} for {wp_id}: resolved workspace has no branch name.")
            raise typer.Exit(1)
        branch_exists = subprocess.run(
            ["git", "rev-parse", "--verify", branch_name],
            cwd=main_repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if branch_exists.returncode == 0:
            worktree_cmd = ["git", "worktree", "add", str(workspace_path), branch_name]
        else:
            worktree_cmd = ["git", "worktree", "add", str(workspace_path), "-b", branch_name]
        result = subprocess.run(worktree_cmd, cwd=main_repo_root, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)

        if result.returncode != 0:
            print(
                f"Error: could not create review workspace {workspace_path} for {wp_id}: "
                f"`{' '.join(worktree_cmd)}` failed: {result.stderr.strip()}"
            )
            raise typer.Exit(1)

        print(f"✓ Created workspace: {workspace_path}")
        if not workspace.exists:
            print(f"Error: workspace creation reported success but {workspace_path} is not a git worktree.")
            raise typer.Exit(1)

    # Concurrent review isolation: acquire review lock or apply env-var
    # isolation — only after the workspace is proven to exist.
    from rich.markup import escape

    from specify_cli.cli.console import console
    from specify_cli.review.lock import ReviewLock, ReviewLockError, _get_isolation_config, _apply_env_var_isolation

    isolation_config = _get_isolation_config(main_repo_root)
    if isolation_config and isolation_config.get("strategy") == "env_var":
        _apply_env_var_isolation(isolation_config, agent or "unknown", wp_id)
    else:
        try:
            ReviewLock.acquire(Path(workspace.worktree_path), wp_id, agent or "unknown")
        except ReviewLockError as e:
            # #4163: the builtin ``print`` echoed these tags literally, and the
            # lock message carries arbitrary text (agent handles, paths), so it
            # is escaped before it reaches the markup renderer.
            console.print(f"[red]{escape(str(e))}[/red]")
            raise typer.Exit(1) from e

    return workspace


@app.command(name="review")
def review(
    wp_id: Annotated[str | None, typer.Argument(help="Work package ID (e.g., WP01) - auto-detects first for_review if omitted")] = None,
    mission: Annotated[str | None, typer.Option("--mission", help="Mission slug")] = None,
    agent: Annotated[str | None, typer.Option("--agent", help="Agent name (required for auto-move to in_progress)")] = None,
    model: Annotated[str | None, typer.Option("--model", help=_MODEL_OPT_HELP)] = None,
    profile: Annotated[str | None, typer.Option("--profile", help=_PROFILE_OPT_HELP)] = None,
    invocation_id: Annotated[str | None, typer.Option("--invocation-id", help=_INVOCATION_ID_OPT_HELP)] = None,
) -> None:
    """Display work package prompt with review instructions.

    This command outputs the full work package prompt (including any review
    feedback from previous reviews) so agents can review the implementation.

    Automatically moves WP from for_review to in_review (requires --agent to track who is reviewing).

    Examples:
        spec-kitty agent action review WP01 --agent claude
        spec-kitty agent action review wp02 --agent codex
        spec-kitty agent action review --agent gemini  # auto-detects first for_review WP
    """
    # T010: the raw CLI-option surface, unresolved.
    request = ReviewRequest(wp_id=wp_id, mission=mission, agent=agent)

    # WP06 T029: reset the commit-receipt accumulator for this invocation.
    _reset_workflow_receipts()
    try:
        # Get repo root and feature slug
        repo_root = locate_project_root()
        if repo_root is None:
            print("Error: Could not locate project root")
            raise typer.Exit(1)

        mission_slug = _find_mission_slug(explicit_mission=request.mission, repo_root=repo_root)

        # Ensure planning repo is on the target branch before we start
        # (needed for auto-commits and status tracking inside this command)
        main_repo_root, target_branch = _ensure_target_branch_checked_out(repo_root, mission_slug)

        # Determine which WP to review
        if request.wp_id:
            normalized_wp_id = _normalize_wp_id(request.wp_id)
        else:
            # Auto-detect first for_review WP
            normalized_wp_id = _find_first_for_review_wp(repo_root, mission_slug)
            if not normalized_wp_id:
                print("Error: No work packages ready for review. Specify a WP ID explicitly.")
                raise typer.Exit(1)

        lane_ctx = _executor.review_resolve_wp_and_lane_gate(repo_root, main_repo_root, mission_slug, normalized_wp_id)
        wp = lane_ctx.wp
        feature_dir = lane_ctx.feature_dir
        current_lane = lane_ctx.current_lane
        review_workspace = lane_ctx.review_workspace
        status_execution_mode = lane_ctx.status_execution_mode

        # Bulk edit occurrence classification + per-file diff compliance gate (FR-006/7/8).
        _executor.review_enforce_bulk_edit_gate(
            feature_dir=feature_dir,
            main_repo_root=main_repo_root,
            mission_slug=mission_slug,
            target_branch=target_branch,
            review_workspace=review_workspace,
        )

        resolved_binding = _resolve_dispatch_binding(
            model=model,
            profile=profile,
            invocation_id=invocation_id,
            repo_root=main_repo_root,
            mission_id=(
                _mission_id_for_claim(main_repo_root, mission_slug)
                if invocation_id is not None
                else None
            ),
            wp_id=normalized_wp_id,
            action="review",
        )

        wp = _executor.review_claim_transition(
            wp=wp,
            feature_dir=feature_dir,
            current_lane=current_lane,
            agent=agent,
            main_repo_root=main_repo_root,
            mission_slug=mission_slug,
            normalized_wp_id=normalized_wp_id,
            target_branch=target_branch,
            status_execution_mode=status_execution_mode,
            repo_root=repo_root,
            resolved_binding=resolved_binding,
        )

        workspace = resolve_workspace_for_wp(main_repo_root, mission_slug, normalized_wp_id)
        workspace = _prepare_review_workspace(workspace, main_repo_root, normalized_wp_id, agent)
        workspace_path = workspace.worktree_path

        # Resolve git context (branch name, base branch, commit count)
        review_ctx = _resolve_review_context(workspace_path, main_repo_root, mission_slug, normalized_wp_id, wp.frontmatter)

        dependents_warning = _executor.review_compute_dependents_warning(repo_root, mission_slug, normalized_wp_id)

        # WP03 (#833): resolve the agent identity 4-tuple so the review prompt
        # surfaces model / profile_id / role rather than silently dropping them.
        try:
            _review_wp_meta, _ = read_wp_frontmatter(wp.path)
            _review_agent_assignment = _review_wp_meta.resolved_agent()
        except Exception as _agent_err:
            logger.warning("Could not resolve agent identity for review prompt: %s", _agent_err)
            _review_agent_assignment = None

        # IC-04/T018: review-cycle sub-artifact WRITE (mkdir). WORK_PACKAGE_TASK
        # is a PRIMARY-partition kind: the placement seam's write and read
        # projections resolve to the SAME on-disk directory for a PRIMARY kind
        # (INV-5 full read/write symmetry) -- this genuine filesystem write is
        # therefore resolved via the read-side projection.
        wp_slug = wp.path.stem
        sub_artifact_dir = (
            _resolve_workflow_read_dir(
                repo_root=main_repo_root, mission_slug=mission_slug, kind=MissionArtifactKind.WORK_PACKAGE_TASK
            )
            / "tasks"
            / wp_slug
        )
        sub_artifact_dir.mkdir(parents=True, exist_ok=True)
        existing_cycles = sorted(sub_artifact_dir.glob("review-cycle-*.md"))
        next_cycle = len(existing_cycles) + 1
        review_feedback_path = review_feedback_source_path(sub_artifact_dir, next_cycle)

        prompt_lines = _executor.build_review_prompt_lines(
            normalized_wp_id=normalized_wp_id,
            wp=wp,
            workspace=workspace,
            workspace_path=workspace_path,
            review_agent_assignment=_review_agent_assignment,
            repo_root=repo_root,
            mission_slug=mission_slug,
            target_branch=target_branch,
            dependents_warning=dependents_warning,
            review_ctx=review_ctx,
            main_repo_root=main_repo_root,
            review_feedback_path=review_feedback_path,
        )

        _executor.review_finalize_and_print(
            prompt_lines=prompt_lines,
            main_repo_root=main_repo_root,
            mission_slug=mission_slug,
            normalized_wp_id=normalized_wp_id,
            workspace=workspace,
            workspace_path=workspace_path,
            review_ctx=review_ctx,
            target_branch=target_branch,
            dependents_warning=dependents_warning,
            review_feedback_path=review_feedback_path,
            wp=wp,
        )

    except typer.Exit:
        with contextlib.suppress(Exception):
            _print_commit_summary(command_name="review")
        raise
    except Exception as e:
        with contextlib.suppress(Exception):
            _print_commit_summary(command_name="review")
        print(f"Error: {e}")
        raise typer.Exit(1)

    # WP06 T029: terminal commit summary for the review command.
    _print_commit_summary(command_name="review")
