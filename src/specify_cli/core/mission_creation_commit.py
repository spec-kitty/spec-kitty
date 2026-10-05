"""The create-scaffold commit, origin-binding consumption and the result.

Moved verbatim from ``mission_creation.py`` (#5634). ``mission_creation`` re-exports
every name defined here. A call to a name tests patch on ``mission_creation``, or to a
function another ``mission_creation*`` module owns, goes through a lazy in-function
``from specify_cli.core import mission_creation as _mc`` import (never at module scope).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    placement_seam,
)
from specify_cli.core.commit_guard import GuardCapability
from specify_cli.core.git_ops import get_current_branch
from specify_cli.core.mission_creation_decisions import (
    CommitFailureKind,
    classify_scaffold_commit_failure,
    created_file_sets,
)
from specify_cli.core.owned_mission import OwnedCreateMission, OwnedCreateRoot
from specify_cli.git import safe_commit
from specify_cli.git.commit_helpers import (
    SafeCommitStagedTreeUnchanged,
)
from specify_cli.core.mission_creation_errors import MissionAlreadyExistsError, MissionCreationError, MissionCreationResult, _BOOTSTRAP_META_COMMIT_SKIPS
from specify_cli.core.mission_creation_scaffold import _Scaffold

logger = logging.getLogger("specify_cli.core.mission_creation")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _commit_feature_file(
    file_paths: tuple[Path, ...],
    mission_slug: str,
    artifact_type: str,
    repo_root: Path,
    *,
    worktree_root: Path | None = None,
    create_time_target: CommitTarget | None = None,
    owned: OwnedCreateMission | None = None,
) -> None:
    """Commit one or more create-owned artifacts in ONE transactional commit.

    This is a slim, typer-free version of the ``_commit_to_branch`` helper
    in the CLI module. It delegates straight to ``safe_commit`` with no
    try/except of its own, so it raises on BOTH a hard git failure and an
    empty changeset (``safe_commit`` itself raises ``RuntimeError`` when
    there is nothing to commit -- it does NOT silently no-op). Callers that
    know their changeset is always non-empty (e.g. the FR-001 create-scaffold
    commit call site, where the files genuinely differ from HEAD at create
    time) can safely treat any raise here as a hard failure.

    #2693: ``file_paths`` is a tuple so the whole create-owned generated set
    (``meta.json`` + ``status.events.jsonl`` + ``tasks/README.md`` +
    ``tasks/.gitkeep``) lands in a SINGLE commit rather than committing
    ``meta.json`` alone and leaving the rest untracked. ``safe_commit`` stages
    exactly these paths, so the commit is transactionally complete over the
    set the caller owns.

    coord-primary-partition-lock WP02 (T007 / C-001 / C-006): the commit
    destination is derived from ``placement_seam(...).write_target(SPEC)``,
    NOT from the operator's current checkout. Pre-fix this constructed
    ``CommitTarget(ref=current_branch)`` directly, which is the create-time
    split-brain root (research.md D5) -- under a coord-routing mission whose
    resolved ``target_branch`` differs from the checkout, the metadata commit
    silently landed on whatever branch the operator happened to be parked on
    instead of the mission's actual primary home. ``SPEC`` is a
    ``_PRIMARY_ARTIFACT_KINDS`` member (same as ``PRIMARY_METADATA``, the kind
    the committed ``meta.json`` file itself belongs to): both resolve to the
    identical primary ``target_branch`` for every topology, so this is a pure
    derivation-source fix (seam vs. checkout), not a placement change.
    """

    if get_current_branch(repo_root) is None:
        raise MissionCreationError("Not in a git repository")

    # Mission creation runs pre-spec: the destination is the branch ``create``
    # reports (the planning destination), which is a non-protected planning
    # branch. Capability is STANDARD — the placement-matched commit needs no
    # protected-branch bookkeeping authorization. If a project legitimately
    # plans on a protected branch, WP05's placement projection routes the
    # commit; this caller does not duplicate that decision (T010).
    commit_msg = f"Add {artifact_type} for feature {mission_slug}"
    effective_worktree = worktree_root or repo_root
    seam_target = create_time_target if create_time_target is not None else placement_seam(repo_root, mission_slug).write_target(MissionArtifactKind.SPEC)
    safe_commit(
        repo_root=repo_root,
        worktree_root=effective_worktree,
        target=seam_target,
        message=commit_msg,
        paths=file_paths,
        capability=GuardCapability.STANDARD,
        # Owned create: the mission-scoped commit_to_target fold reads the new
        # mission from the validated create fact, never the repository root.
        owned=owned,
    )


@dataclass(slots=True)
class _CommitOutcome:
    """Outcome of the scaffold commit + pending-origin consumption (T051)."""

    scaffold_commit_skipped: bool
    origin_binding_attempted: bool
    origin_binding_succeeded: bool
    origin_binding_error: str | None
    meta: dict[str, Any]


def _commit_create_scaffold(
    *,
    scaffold: _Scaffold,
    resolved_root: Path,
    write_root: Path,
    create_time_target: CommitTarget,
    mission_slug_formatted: str,
    planning_branch: str,
    meta: dict[str, Any],
) -> _CommitOutcome:
    """Commit the scaffold, then consume + commit a pending origin binding.

    Sections 8.5, 9 and 9.5 of the pre-decomposition body (T051): ONE
    transactional commit for the create-owned generated set (#2693), then the
    ticket-first pending-origin consumption, then -- only on a successful
    bind -- a SECOND commit landing the updated ``origin_ticket`` subtree
    through the same sanctioned commit surface (squad follow-on to
    #2739/#2693), so the tree never sits modified-uncommitted after a
    successful origin bind.

    FR-001 (#3673): do NOT suppress -- a hard git failure must raise so
    ``create_mission_core``'s rollback
    (``_restore_git_state_after_failed_create``) fires. ``_commit_feature_file``
    calls ``safe_commit`` directly (no empty-changeset no-op); every path here
    genuinely differs from HEAD at create time, so the commit is non-empty.
    """

    scaffold_commit_skipped = False
    try:
        _commit_feature_file(
            scaffold.scaffold_paths,
            mission_slug_formatted,
            "scaffold",
            resolved_root,
            worktree_root=write_root,
            create_time_target=create_time_target,
            owned=scaffold.owned_mission,
        )
    except Exception as exc:
        outcome = classify_scaffold_commit_failure(_commit_failure_kind(exc))
        if outcome == "already_exists":
            # #3861: a byte-identical scaffold already committed is the same
            # duplicate-mission signature the #4033 guard refuses pre-write (the
            # residual path the guard can allow through, e.g. ``allow_duplicate``
            # callers re-running with a frozen ``mission_id``). Surface the TYPED
            # already-exists signal, never the prose.
            raise MissionAlreadyExistsError(f"meta.json commit failed: {exc}") from exc
        if outcome == "raise":
            raise RuntimeError(f"meta.json commit failed: {exc}") from exc
        scaffold_commit_skipped = True
        logger.info(
            "Skipping bootstrap scaffold commit for %s on planning branch %s: %s",
            mission_slug_formatted,
            planning_branch,
            exc,
        )

    (
        origin_binding_attempted,
        origin_binding_succeeded,
        origin_binding_error,
        meta,
    ) = _consume_pending_origin_if_present(
        repo_root=resolved_root,
        feature_dir=scaffold.feature_dir,
        meta=meta,
    )

    if origin_binding_succeeded:
        meta_file = scaffold.feature_dir / "meta.json"
        try:
            _commit_feature_file(
                (meta_file,),
                mission_slug_formatted,
                "origin-ticket binding",
                resolved_root,
                worktree_root=write_root,
                create_time_target=create_time_target,
                owned=scaffold.owned_mission,
            )
        except _BOOTSTRAP_META_COMMIT_SKIPS as exc:
            scaffold_commit_skipped = True
            logger.info(
                "Skipping origin-ticket binding commit for %s on planning branch %s: %s",
                mission_slug_formatted,
                planning_branch,
                exc,
            )
        except Exception as exc:
            raise RuntimeError(f"origin-ticket binding commit failed: {exc}") from exc

    return _CommitOutcome(
        scaffold_commit_skipped=scaffold_commit_skipped,
        origin_binding_attempted=origin_binding_attempted,
        origin_binding_succeeded=origin_binding_succeeded,
        origin_binding_error=origin_binding_error,
        meta=meta,
    )


def _commit_failure_kind(exc: Exception) -> CommitFailureKind:
    """Map a scaffold-commit exception to its kind, in the order of the former except-ladder."""
    if isinstance(exc, _BOOTSTRAP_META_COMMIT_SKIPS):
        return CommitFailureKind.BOOTSTRAP_REFUSAL
    if isinstance(exc, SafeCommitStagedTreeUnchanged):
        return CommitFailureKind.STAGED_TREE_UNCHANGED
    return CommitFailureKind.OTHER


def _build_create_result(
    *,
    scaffold: _Scaffold,
    commit_outcome: _CommitOutcome,
    mission_slug_formatted: str,
    planning_branch: str,
    current_branch: str,
    coordination_branch_created: bool,
    resolved_root: Path,
    owned_create_root: OwnedCreateRoot | None,
    created_event: dict[str, Any],
    phase_event: dict[str, Any] | None,
    status_log_path: Path | None = None,
) -> MissionCreationResult:
    """Build the final result and fan out the local events (section 10, T051).

    Publishing happens after local creation has fully succeeded, including
    main's explicitly disclosed bootstrap skips: a hard scaffold/origin
    failure must leave no hosted events whose local authority was rolled
    back.

    ``status_log_path`` (T031): the ``status.events.jsonl`` a reader should
    follow for this create -- the coordination Mission dir's copy for an
    UNOWNED coordination-routed create (already committed separately, on the
    coordination branch, unconditionally), ``scaffold.feature_dir``'s for
    every other topology (unchanged, C-008) -- including an OWNED
    coordination-routed create (review cycle 2, B5' ruling reversed): the
    caller never passes a non-``None`` ``status_log_path`` for one (the
    coordination surface is never seeded when ``owned`` is set), but
    ``owned_create_root is None`` is checked explicitly here too, not only
    relied on transitively, so this function's own invariant holds even if a
    future caller's wiring drifts. Defaults to the latter.
    """
    # This site keys on the seeded status log, not on the topology:
    # a skipped coordination seed leaves ``status_log_path`` unset.
    coordination_routed = status_log_path is not None and owned_create_root is None
    log_path = status_log_path if status_log_path is not None else scaffold.feature_dir / "status.events.jsonl"
    # The coordination log already committed separately (unconditionally,
    # outside the target scaffold commit's own bootstrap-skip handling, T032),
    # so a coordination-routed create's skipped-scaffold list never repeats it
    # -- it was never part of the target scaffold tuple.
    created_files, uncommitted_files = created_file_sets(
        spec_file=scaffold.spec_file,
        meta_file=scaffold.feature_dir / "meta.json",
        tasks_readme=scaffold.tasks_readme,
        tasks_gitkeep=scaffold.feature_dir / "tasks" / ".gitkeep",
        log_path=log_path,
        coordination_routed=coordination_routed,
        scaffold_commit_skipped=commit_outcome.scaffold_commit_skipped,
    )

    from specify_cli.status import fanout_lifecycle_event_hosted

    if created_event is not None:
        fanout_lifecycle_event_hosted(created_event, log_path=log_path)
    if phase_event is not None:
        fanout_lifecycle_event_hosted(phase_event, log_path=log_path)

    return MissionCreationResult(
        feature_dir=scaffold.feature_dir,
        mission_slug=mission_slug_formatted,
        mission_number=None,  # pre-merge: no display number assigned (FR-044)
        meta=commit_outcome.meta,
        target_branch=planning_branch,
        current_branch=current_branch,
        created_files=created_files,
        uncommitted_files=uncommitted_files,
        origin_binding_attempted=commit_outcome.origin_binding_attempted,
        origin_binding_succeeded=commit_outcome.origin_binding_succeeded,
        origin_binding_error=commit_outcome.origin_binding_error,
        coordination_branch=commit_outcome.meta.get("coordination_branch"),
        coordination_branch_created=coordination_branch_created,
        owned_checkout=owned_create_root,
        canonical_repo_root=resolved_root,
    )


def _consume_pending_origin_if_present(
    *,
    repo_root: Path,
    feature_dir: Path,
    meta: dict[str, Any],
) -> tuple[bool, bool, str | None, dict[str, Any]]:
    """Bind a staged pending origin after mission creation, if present.

    Dispatches to the registered PendingOriginConsumer via
    ``core.adapters.consume_pending_origin`` so that this module carries no
    direct INTEGRATION imports (FR-004/FR-006).  The concrete implementation
    lives in ``tracker/origin_consumer.py`` and is registered at tracker
    startup.  When no consumer is registered the call is a safe no-op
    that returns ``(False, False, None, meta)``.
    """
    from specify_cli.core.adapters import consume_pending_origin

    # Typed binding required: mypy uses follow_imports=skip for specify_cli.*
    # so the return of consume_pending_origin is seen as Any here; the
    # explicit annotation re-introduces the correct return type so the caller
    # does not propagate Any (no blanket suppression needed).
    result: tuple[bool, bool, str | None, dict[str, Any]] = consume_pending_origin(repo_root, feature_dir, meta)
    return result
