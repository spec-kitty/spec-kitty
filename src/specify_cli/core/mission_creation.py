"""Reusable mission-creation logic extracted from the CLI command.

This module provides ``create_mission_core()`` -- the programmatic API
for creating a new mission directory with all scaffolding. The CLI
command ``create()`` is a thin wrapper around this function.

Module map (#5634): this façade keeps ``create_mission_core``,
``_create_mission_core_failure_atomic``, ``_create_mission_core_impl`` and the import
surface (``logger`` included). ``create_mission_core`` delegates to
``_create_mission_core_failure_atomic``, which holds the failure-atomic wrapper and
takes the private identity inputs ``_mission_id`` and ``_created_at`` (the identity
seam: otherwise ``_mint_mission_id`` mints the ULID and the clock stamps
``created_at``). Every other definition moved into a sibling module and is
re-exported here; several leaves were reshaped afterwards by the decision-core and
seam cleanups. The orchestration calls the protected-target mint itself, between
``_build_create_meta`` and ``_write_create_meta``:

===================================  ==============================================  =====================================================================
Module                               Responsibility                                  Key names
===================================  ==============================================  =====================================================================
``mission_creation_errors``          errors, result type, commit-skip set            ``MissionCreationError``, ``MissionCreationResult``
``mission_creation_identity``        identity mint, slug, friendly name, purpose     ``_mint_mission_id``, ``_validate_create_inputs``
``mission_creation_roots``           repository root, write root, current branch     ``_resolve_create_roots``
``mission_creation_duplicates``      live-duplicate detection                        ``_refuse_live_duplicate``
``mission_creation_protected_mint``  protected-target mission-branch mint            ``_ProtectionProbe``, ``_mint_protected_branch_for_topology``
``mission_creation_scaffold``        mission dir scaffold, tasks README, governance  ``_scaffold_mission_dir``
``mission_creation_meta``            ``meta.json`` assembly and write                ``_build_create_meta``, ``_write_create_meta``
``mission_creation_events``          creation events, coordination status seed       ``_emit_create_events``
``mission_creation_commit``          scaffold commit, origin binding, result         ``_commit_create_scaffold``
``mission_creation_rollback``        failure-atomic rollback of a failed create      ``CreateRollbackJournal``, ``_restore_git_state_after_failed_create``
``mission_creation_decisions``       pure decision cores (no I/O)                    ``decide_protected_mint``
===================================  ==============================================  =====================================================================

Routing rule: a leaf calls a name tests patch here (today the routed set is
``{build_mission_created_payload}``), or a function another ``mission_creation*``
module owns, as ``_mc.<name>`` after a function-local
``from specify_cli.core import mission_creation as _mc``; every other call is direct.
Re-exports are import points, not patch points: patching any other re-exported
name here (``ULID``, ``now_utc_iso``, ``locate_project_root``, ``safe_commit``, ...)
no longer reaches the leaf that calls it. Patch the leaf, or use the private
``_mission_id`` / ``_created_at`` inputs of ``_create_mission_core_failure_atomic``.
Pinned by ``tests/core/test_mission_creation_family.py``; see
``docs/api/mission-creation-internals.md``.
"""

from __future__ import annotations

import contextlib as contextlib
import logging as logging
import re as re
import shutil as shutil
import subprocess
from dataclasses import (
    dataclass as dataclass,
    field as field,
    replace as replace,
)
from pathlib import Path
from typing import (
    Any as Any,
    NoReturn as NoReturn,
)
from ulid import ULID as ULID
from specify_cli.core.constants import KITTY_SPECS_DIR as KITTY_SPECS_DIR
from mission_runtime import (
    CommitTarget as CommitTarget,
    MissionArtifactKind as MissionArtifactKind,
    MissionTopology,
    WriteLocation as WriteLocation,
    placement_seam as placement_seam,
    resolve_create_time_write_target,
)
from specify_cli.core.commit_guard import GuardCapability as GuardCapability
from specify_cli.core.mission_creation_decisions import (
    CasReset as CasReset,
    CommitFailureKind as CommitFailureKind,
    Delete as Delete,
    Mint as Mint,
    NoMint as NoMint,
    Noop as Noop,
    ProtectedMintDecision as ProtectedMintDecision,
    ProtectedMintFacts as ProtectedMintFacts,
    ProtectedTargetPolicy as ProtectedTargetPolicy,
    Refuse as Refuse,
    candidate_name_matches as candidate_name_matches,
    classify_scaffold_commit_failure as classify_scaffold_commit_failure,
    coord_rollback_action as coord_rollback_action,
    coord_rollback_needs_current_tip as coord_rollback_needs_current_tip,
    created_file_sets as created_file_sets,
    decide_protected_mint as decide_protected_mint,
    is_abandoned as is_abandoned,
    is_coordination_routed as is_coordination_routed,
    is_same_mission_type as is_same_mission_type,
    meta_flag_patch as meta_flag_patch,
    orphan_scaffold_candidates as orphan_scaffold_candidates,
    plan_orphan_scaffold_removal as plan_orphan_scaffold_removal,
    protected_mint_applies as protected_mint_applies,
    target_is_protected as target_is_protected,
)
from specify_cli.core.git_ops import (
    get_current_branch,
    has_unborn_head as has_unborn_head,
    is_git_repo,
)
from specify_cli.core.mission_payload import (
    build_mission_created_payload as build_mission_created_payload,
    default_mission_display_name as default_mission_display_name,
    default_mission_purpose_context as default_mission_purpose_context,
)
from specify_cli.core.owned_mission import (
    OwnedCreateMission as OwnedCreateMission,
    OwnedCreateRoot,
)
from specify_cli.core.paths import (
    MissionMetaReadError as MissionMetaReadError,
    read_commit_to_target as read_commit_to_target,
    is_worktree_context as is_worktree_context,
    load_meta_fail_closed as load_meta_fail_closed,
    locate_project_root,
)
from kernel.clock import now_utc_iso as now_utc_iso
from kernel.git import (
    GitCommandError as GitCommandError,
    GitPath as GitPath,
    status_entries as status_entries,
    tracked_paths as tracked_paths,
)
from specify_cli.git import (
    preflight_commit as preflight_commit,
    safe_commit as safe_commit,
)
from specify_cli.git.commit_helpers import (
    ProtectedBranchRefused as ProtectedBranchRefused,
    SafeCommitDestinationNotFound as SafeCommitDestinationNotFound,
    SafeCommitHeadMismatch as SafeCommitHeadMismatch,
    SafeCommitStagedTreeUnchanged as SafeCommitStagedTreeUnchanged,
)
from specify_cli.git.ref_advance import (
    RefRestoreError as RefRestoreError,
    restore_branch_ref as restore_branch_ref,
)
from specify_cli.lanes.branch_naming import (
    mission_branch_name as mission_branch_name,
    mission_dir_name,
    resolve_mid8,
    strip_numeric_prefix as strip_numeric_prefix,
)
from specify_cli.mission_metadata import (
    load_meta_or_empty as load_meta_or_empty,
    validate_purpose_summary as validate_purpose_summary,
)

# Moved verbatim to the leaf modules (#5634); re-exported so
# ``mission_creation.<name>`` stays the import and patch surface.
from specify_cli.core.mission_creation_errors import (
    MissionCreationError as MissionCreationError,
    MissionAlreadyExistsError as MissionAlreadyExistsError,
    MissionCreationResult as MissionCreationResult,
    MissionBranchExistsError as MissionBranchExistsError,
    _BOOTSTRAP_META_COMMIT_SKIPS as _BOOTSTRAP_META_COMMIT_SKIPS,
)
from specify_cli.core.mission_creation_identity import (
    KEBAB_CASE_PATTERN as KEBAB_CASE_PATTERN,
    _validate_create_inputs as _validate_create_inputs,
    _Purpose as _Purpose,
    _mint_mission_id as _mint_mission_id,
    _resolve_purpose as _resolve_purpose,
)
from specify_cli.core.mission_creation_roots import (
    _CreateRoots as _CreateRoots,
    _resolve_create_roots as _resolve_create_roots,
)
from specify_cli.core.mission_creation_duplicates import (
    _list_mission_scaffolds as _list_mission_scaffolds,
    _prior_mission_is_abandoned as _prior_mission_is_abandoned,
    _find_live_duplicate_mission as _find_live_duplicate_mission,
    _refuse_live_duplicate as _refuse_live_duplicate,
)
from specify_cli.core.mission_creation_protected_mint import (
    _target_has_commit as _target_has_commit,
    _raise_refusal as _raise_refusal,
    _ProtectionProbe as _ProtectionProbe,
    _target_is_protected as _target_is_protected,
    _protected_mint_applies as _protected_mint_applies,
    _mint_protected_single_branch_mission_branch as _mint_protected_single_branch_mission_branch,
    _check_out_minted_branch as _check_out_minted_branch,
    _gather_and_decide_protected_mint as _gather_and_decide_protected_mint,
    _local_branch_exists as _local_branch_exists,
    _dirty_outside_scaffold as _dirty_outside_scaffold,
    _refuse_protected_recreate as _refuse_protected_recreate,
    _mint_protected_branch_for_topology as _mint_protected_branch_for_topology,
)
from specify_cli.core.mission_creation_scaffold import (
    TASKS_README_TEMPLATE as TASKS_README_TEMPLATE,
    render_tasks_readme_content as render_tasks_readme_content,
    _Governance as _Governance,
    _resolve_create_governance as _resolve_create_governance,
    _Scaffold as _Scaffold,
    _scaffold_mission_dir as _scaffold_mission_dir,
)
from specify_cli.core.mission_creation_meta import (
    _META_KEY_MISSION_TYPE as _META_KEY_MISSION_TYPE,
    _META_KEY_CREATED_AT as _META_KEY_CREATED_AT,
    _MetaBuild as _MetaBuild,
    _build_create_meta as _build_create_meta,
    _write_create_meta as _write_create_meta,
)
from specify_cli.core.mission_creation_events import (
    _emit_create_events as _emit_create_events,
    _commit_coord_create_events as _commit_coord_create_events,
    _CoordCreateSeed as _CoordCreateSeed,
    _seed_coord_surface_for_create as _seed_coord_surface_for_create,
)
from specify_cli.core.mission_creation_commit import (
    _commit_feature_file as _commit_feature_file,
    _CommitOutcome as _CommitOutcome,
    _commit_create_scaffold as _commit_create_scaffold,
    _commit_failure_kind as _commit_failure_kind,
    _build_create_result as _build_create_result,
    _consume_pending_origin_if_present as _consume_pending_origin_if_present,
)
from specify_cli.core.mission_creation_rollback import (
    _COORDINATION_BRANCH_GLOB as _COORDINATION_BRANCH_GLOB,
    _list_coordination_branches as _list_coordination_branches,
    _rev_parse_or_none as _rev_parse_or_none,
    _path_is_tracked_by_git as _path_is_tracked_by_git,
    _failure_is_disposable_create_refusal as _failure_is_disposable_create_refusal,
    _plan_orphan_scaffold_removal as _plan_orphan_scaffold_removal,
    _remove_orphan_mission_scaffolds as _remove_orphan_mission_scaffolds,
    _CoordCreateRollbackContext as _CoordCreateRollbackContext,
    CreateRollbackJournal as CreateRollbackJournal,
    _rollback_coordination_surface as _rollback_coordination_surface,
    _restore_git_state_after_failed_create as _restore_git_state_after_failed_create,
)

# The leaves that log pin ``logging.getLogger("specify_cli.core.mission_creation")``,
# which is the logger this module's ``__name__`` names: one logger object (#5634).
from specify_cli.core.mission_creation_commit import logger as logger


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_mission_core(
    repo_root: Path | None,
    mission_slug: str,
    *,
    mission: str | None = None,
    target_branch: str | None = None,
    friendly_name: str | None = None,
    purpose_tldr: str | None = None,
    purpose_context: str | None = None,
    pr_bound: bool = False,
    topology: MissionTopology = MissionTopology.COORD,
    force_recreate_coordination_branch: bool = False,
    allow_worktree_context: bool = False,
    owned_create_root: OwnedCreateRoot | None = None,
    retain_branches: bool = False,
    retain_worktrees: bool = False,
    commit_to_target: bool = False,
    allow_duplicate: bool = False,
) -> MissionCreationResult:
    """Create a new mission, restoring git state if creation fails (FR-011).

    Failure-atomic wrapper around :func:`_create_mission_core_impl`. It captures
    the operator's branch/checkout, the pre-existing coordination branches, and
    the pre-existing ``kitty-specs/`` scaffolds *before* any mutation. On ANY
    failure it restores the original checkout, deletes the orphan coordination
    branch the aborted run minted (#3339). Disposable commit refusals also
    remove newly created untracked scaffolds; diagnostic failures retain them.
    See :func:`_create_mission_core_impl` for the full parameter contract.
    """
    return _create_mission_core_failure_atomic(
        repo_root,
        mission_slug,
        mission=mission,
        target_branch=target_branch,
        friendly_name=friendly_name,
        purpose_tldr=purpose_tldr,
        purpose_context=purpose_context,
        pr_bound=pr_bound,
        topology=topology,
        force_recreate_coordination_branch=force_recreate_coordination_branch,
        allow_worktree_context=allow_worktree_context,
        owned_create_root=owned_create_root,
        retain_branches=retain_branches,
        retain_worktrees=retain_worktrees,
        commit_to_target=commit_to_target,
        allow_duplicate=allow_duplicate,
    )


def _create_mission_core_failure_atomic(
    repo_root: Path | None,
    mission_slug: str,
    *,
    mission: str | None = None,
    target_branch: str | None = None,
    friendly_name: str | None = None,
    purpose_tldr: str | None = None,
    purpose_context: str | None = None,
    pr_bound: bool = False,
    topology: MissionTopology = MissionTopology.COORD,
    force_recreate_coordination_branch: bool = False,
    allow_worktree_context: bool = False,
    owned_create_root: OwnedCreateRoot | None = None,
    retain_branches: bool = False,
    retain_worktrees: bool = False,
    commit_to_target: bool = False,
    allow_duplicate: bool = False,
    _mission_id: str | None = None,
    _created_at: str | None = None,
) -> MissionCreationResult:
    """The failure-atomic body of :func:`create_mission_core` (#5634).

    Same contract, plus the private identity inputs: ``_mission_id`` (the
    ``mission_id`` to use instead of minting one) and ``_created_at`` (the
    ``created_at`` stamp instead of the clock). Both default to ``None``, which
    mints and reads the clock exactly as before. Callers that need a fixed
    identity (tests, a deterministic re-run) pass them here; the public
    signature of :func:`create_mission_core` stays unchanged (public surface).
    """
    # An explicit owned checkout is the write/commit surface. Snapshot that
    # checkout rather than the canonical primary so a late failure restores
    # the branch ref and index that this invocation actually mutated.
    rollback_root = owned_create_root.checkout if owned_create_root is not None else repo_root
    if rollback_root is None:
        rollback_root = locate_project_root()
    original_branch: str | None = None
    original_commit: str | None = None
    original_index_tree: str | None = None
    pre_existing_coordination_branches: frozenset[str] = frozenset()
    pre_existing_scaffolds: frozenset[str] = frozenset()
    if rollback_root is not None:
        # Snapshot the scaffold set even when the path is not a git repo: the
        # scaffold is written to disk regardless, so the orphan is possible
        # regardless (#4035).
        pre_existing_scaffolds = _list_mission_scaffolds(rollback_root)
    if rollback_root is not None and is_git_repo(rollback_root):
        original_branch = get_current_branch(rollback_root)
        original_commit_result = subprocess.run(
            ["git", "-C", str(rollback_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if original_commit_result.returncode == 0:
            original_commit = original_commit_result.stdout.strip()
        original_index_result = subprocess.run(
            ["git", "-C", str(rollback_root), "write-tree"],
            capture_output=True,
            text=True,
            check=False,
        )
        if original_index_result.returncode == 0:
            original_index_tree = original_index_result.stdout.strip()
        pre_existing_coordination_branches = _list_coordination_branches(rollback_root)

    # T032/FR-002a: ``_create_mission_core_impl`` mints ``mission_slug_formatted``
    # and ``mid8`` internally, so this journal is how it reports the
    # coordination surface it materialized back to this failure-atomic wrapper
    # -- recorded as soon as the coordination branch name is known, before
    # the seed or the creation-events commit can fail.
    rollback_journal = CreateRollbackJournal()
    try:
        return _create_mission_core_impl(
            repo_root,
            mission_slug,
            mission=mission,
            target_branch=target_branch,
            friendly_name=friendly_name,
            purpose_tldr=purpose_tldr,
            purpose_context=purpose_context,
            pr_bound=pr_bound,
            topology=topology,
            force_recreate_coordination_branch=force_recreate_coordination_branch,
            allow_worktree_context=allow_worktree_context,
            owned_create_root=owned_create_root,
            retain_branches=retain_branches,
            retain_worktrees=retain_worktrees,
            commit_to_target=commit_to_target,
            allow_duplicate=allow_duplicate,
            _rollback_journal=rollback_journal,
            _mission_id=_mission_id,
            _created_at=_created_at,
        )
    except BaseException as _create_exc:
        # Re-raised below; the rollback is pure cleanup and must not swallow or
        # replace the original failure (that is why we re-raise unconditionally).
        if rollback_root is not None:
            # Plan before rollback restores the index and branch ref; indexed
            # scaffold content must remain available for diagnosis.
            planned_scaffold_removal: tuple[Path, ...] = ()
            if _failure_is_disposable_create_refusal(_create_exc):
                planned_scaffold_removal = _plan_orphan_scaffold_removal(
                    rollback_root,
                    mission_slug=mission_slug,
                    pre_existing_scaffolds=pre_existing_scaffolds,
                )
            _restore_git_state_after_failed_create(
                rollback_root,
                original_branch=original_branch,
                original_commit=original_commit,
                original_index_tree=original_index_tree,
                pre_existing_coordination_branches=pre_existing_coordination_branches,
                coord_rollback=rollback_journal.coord,
            )
            # #4035: git state alone is not the whole side effect. On a
            # disposable commit refusal the on-disk scaffold outlives the failed
            # create and turns the documented recovery into a second mission,
            # so it goes too. Other failure classes keep theirs (see
            # ``_failure_is_disposable_create_refusal``).
            _remove_orphan_mission_scaffolds(planned_scaffold_removal)
        raise


def _create_mission_core_impl(
    repo_root: Path | None,
    mission_slug: str,
    *,
    mission: str | None = None,
    target_branch: str | None = None,
    friendly_name: str | None = None,
    purpose_tldr: str | None = None,
    purpose_context: str | None = None,
    pr_bound: bool = False,
    topology: MissionTopology = MissionTopology.COORD,
    force_recreate_coordination_branch: bool = False,
    allow_worktree_context: bool = False,
    owned_create_root: OwnedCreateRoot | None = None,
    retain_branches: bool = False,
    retain_worktrees: bool = False,
    commit_to_target: bool = False,
    allow_duplicate: bool = False,
    _rollback_journal: CreateRollbackJournal | None = None,
    _mission_id: str | None = None,
    _created_at: str | None = None,
) -> MissionCreationResult:
    """Create a new feature with all scaffolding.

    This is the programmatic API for feature creation.  Unlike the CLI
    command, it returns a structured result and raises domain exceptions
    instead of calling ``typer.Exit()``.

    Parameters
    ----------
    repo_root:
        Absolute path to the project root (must contain ``.kittify/`` and
        ``kitty-specs/``).  When *None*, ``locate_project_root()`` is called
        automatically.
    mission_slug:
        Bare slug such as ``"user-auth"`` or ``"068-feature"`` (kebab-case).
    mission:
        Optional mission key (e.g. ``"documentation"``, ``"software-dev"``).
        Defaults to ``"software-dev"`` when not provided.
    target_branch:
        Explicit target branch for the feature.  When *None* the current
        git branch is used.
    friendly_name:
        Optional mission title shown on operator-facing surfaces. When omitted,
        it is derived from ``mission_slug``.
    purpose_tldr:
        Optional one-line product/CXO summary for the mission. When omitted,
        it defaults to the resolved ``friendly_name``.
    purpose_context:
        Optional short paragraph explaining the mission in stakeholder terms.
        When omitted, it defaults to a branch-aware summary sentence.
    pr_bound:
        Persist the confirmed pull-request binding in the initial metadata
        write and commit. Defaults to ``False``.
    topology:
        Operator's create-time mission shape (#2218). Defaults to
        :attr:`MissionTopology.COORD` for backward-compat. The coordination
        branch is minted only for the coordination-bearing shapes
        (``COORD`` / ``LANES_WITH_COORD``); ``SINGLE_BRANCH`` / ``LANES`` skip
        the mint and never write ``coordination_branch``. The explicit choice
        is persisted verbatim into ``meta.json`` — never re-derived from
        ``classify_topology`` (which cannot reproduce ``LANES`` pre-finalize).
    allow_worktree_context:
        Bypass the worktree-context guard (step 2) that otherwise raises when
        the *process* ``cwd`` resolves inside a git worktree. Defaults to
        ``False``, preserving the interactive/CLI guard that protects
        operators from accidentally scaffolding a mission inside a lane
        worktree instead of the project root checkout. Intended for
        programmatic callers — notably ``tests/_factories.make_mission()``
        (FR-008) — that pass an explicit ``repo_root`` pointing at an
        isolated (often temporary) repository while the test process itself
        happens to be running from within a lane worktree checkout, which is
        this project's normal execution context for its own test suite.
    owned_create_root:
        The already-validated owned root (WP02's :class:`OwnedCreateRoot`) for
        this invocation, or ``None`` for an unowned (repository root) create.
        Callers holding only a raw ``--owned-checkout`` path resolve it through
        :func:`specify_cli.core.owned_mission.resolve_owned_create_root` first
        (validated exactly once per command, FR-003 spirit) and pass the typed
        result here. ``None`` preserves the existing worktree-context guard and
        write-root behavior exactly.
    retain_branches:
        Create-time retention opt-in (#3131 FR-009). When ``True``, mints
        ``retain_branches: true`` into ``meta.json`` so downstream ``spec-kitty
        merge`` cleanup honors the policy from creation. Defaults to
        ``False``, in which case the field is left ABSENT from ``meta.json``
        (never written as ``false``) so non-retaining missions stay
        byte-identical to pre-#3131 output (FR-010, SC-004).
    retain_worktrees:
        Create-time retention opt-in (#3131 FR-009) for worktrees, mirroring
        ``retain_branches``. Defaults to ``False`` (field left ABSENT).
    commit_to_target:
        Operator override (#5100 FR-008, WP08). When ``True`` on a
        ``SINGLE_BRANCH`` mission, skips the protected-target mission-branch
        mint below and mints ``commit_to_target: true`` into ``meta.json`` so
        the override is durable across the mission's lifetime. Defaults to
        ``False``, in which case the field is left ABSENT from ``meta.json``
        (mirrors ``retain_branches``/``retain_worktrees`` -- never written as
        ``false``).
    allow_duplicate:
        Escape hatch for the idempotency guard (#4033, FR-004). Defaults to
        ``False``, preserving the guard: creation is refused with
        :class:`MissionAlreadyExistsError` when a LIVE prior mission shares the
        same base ``mission_slug`` AND ``mission_type`` (FR-001). Abandoned
        priors (canceled, genesis, or spec never committed) never trigger
        the guard regardless of this flag (FR-003). Pass ``True`` to
        deliberately create a second same-key mission -- programmatic/volume
        callers (e.g. the ``tests/_factories`` mission factory) opt in via
        this keyword when they intentionally need more than one.
    _rollback_journal:
        Private (T032/FR-002a). The empty
        :class:`CreateRollbackJournal` the failure-atomic wrapper
        :func:`create_mission_core` passes in; this function records the
        :class:`_CoordCreateRollbackContext` in it as soon as a real
        coordination branch is known (right after ``_build_create_meta``
        returns), so a later failure in THIS call can still be rolled back by
        the wrapper's ``except`` clause even though
        ``mission_slug_formatted``/``mid8`` are minted only inside this
        function. ``None`` (the default) disables rollback reporting.
    _mission_id, _created_at:
        Private identity inputs: the ``mission_id`` to use instead of
        :func:`_mint_mission_id`, and the ``created_at`` stamp instead of the
        clock. ``None`` (the default) mints and reads the clock.

    Returns
    -------
    MissionCreationResult
        Structured result with all paths and metadata.

    Raises
    ------
    MissionCreationError
        On any validation or creation failure.
    charter.activation.pack_context.CharterPackConfigError
        When the project has no activated mission types (an absent or empty
        ``mission_type_activations`` set). This is the WP04 fail-closed at the
        mission-create / mission-type-use boundary: ``PackContext``
        construction is total, so the "provision your charter" error is
        raised here rather than at construction time.
    specify_cli.runtime.resolver.TemplateConfigurationError
        If the activated mission type cannot resolve its configured ``spec``
        template. Resolution happens before any mission state is created.
    """
    normalized_friendly_name = _validate_create_inputs(mission_slug, friendly_name)
    if commit_to_target and topology is not MissionTopology.SINGLE_BRANCH:
        raise MissionCreationError(
            f"--commit-to-target is only valid for a single_branch mission (got topology '{topology.value}'). "
            "Pass --topology single_branch, or drop --commit-to-target."
        )
    roots = _resolve_create_roots(repo_root, owned_create_root, allow_worktree_context)
    resolved_root = roots.repository_root
    write_root = roots.write_root
    current_branch = roots.current_branch

    # B5' (review cycle 2, ruling reversed): an owned-checkout create
    # combined with a coordination-routed topology (``coord`` /
    # ``lanes_with_coord``) is a SUPPORTED, ratcheted path (FR-022,
    # ``tests/integration/test_owned_lifecycle_acceptance_next.py::
    # TestFr022CoordinationTwin`` -- an owned sibling-checkout
    # ``create --topology lanes_with_coord`` followed by ``next`` must be a
    # non-error decision), not an operator override to refuse. ADR
    # 2026-09-03-1's "owned mode mints only single_branch" covers lifecycle
    # commands (``LIFECYCLE_OWNED_TOPOLOGIES``), not create + ``next``
    # (``NEXT_OWNED_TOPOLOGIES`` includes ``LANES_WITH_COORD``). A prior
    # cycle-2 fix refused this combination with
    # ``ActionContextError(OWNED_TOPOLOGY_UNSUPPORTED)``; that refusal broke
    # the ratchet and was removed. The real gap it was trying to close --
    # ``_scaffold_mission_dir`` keying its coordination-routed scaffold
    # change on ``topology`` alone, dropping ``status.events.jsonl`` from an
    # owned create's own scaffold commit -- is fixed at the source instead
    # (``_scaffold_mission_dir`` / ``_build_create_result`` now also gate on
    # ``owned is None``), so an owned coordination-routed create's status log
    # stays in its own PRIMARY dir, committed exactly as at base
    # (``e7b085d26c``). This is a named residual (INV-COORD-HOME): an owned
    # coordination create is never seeded onto the coordination surface
    # itself -- tracked as a follow-up, not fixed here.

    _refuse_live_duplicate(write_root, mission_slug, mission, allow_duplicate)

    planning_branch = target_branch if target_branch else current_branch
    create_time_target = resolve_create_time_write_target(planning_branch)
    purpose = _resolve_purpose(normalized_friendly_name, purpose_tldr, purpose_context, planning_branch)

    # FR-016 (#5009 1f42f76ea, re-expressed on the decomposed pipeline): the
    # validated write checkout owns charter and template configuration; its
    # activation may intentionally differ from the repository root checkout's.
    governance_root = roots.owned.checkout if roots.owned is not None else resolved_root
    governance = _resolve_create_governance(governance_root, mission)

    # Mint the ULID first so we can derive mid8 for the directory name.
    # resolve_mid8 derives the mid8 from the declared mission_id (authoritative,
    # FR-004/NFR-003); mission_dir_name composes <human-slug>-<mid8> canonically,
    # stripping any NNN- prefix (FR-032, FR-044).
    mission_id = _mission_id if _mission_id is not None else _mint_mission_id()
    # One authoritative derivation (FR-004/NFR-003) feeds both consumers: the
    # directory name below and the ``mid8`` meta backfill in
    # ``_build_create_meta`` (#3474), so the two can never drift.
    mid8 = resolve_mid8("", mission_id=mission_id)
    mission_slug_formatted = mission_dir_name(mission_slug, mid8=mid8)

    # One protection probe per create, shared by the recreate guard
    # and the mint. Making it resolves nothing; the first caller that needs
    # protection resolves it (never earlier than before), the second reuses it.
    protection = _ProtectionProbe(write_root)

    scaffold = _scaffold_mission_dir(
        write_root=write_root,
        resolved_root=resolved_root,
        mission_slug_formatted=mission_slug_formatted,
        planning_branch=planning_branch,
        create_time_target=create_time_target,
        spec_template=governance.spec_template,
        owned=roots.owned,
        topology=topology,
        commit_to_target=commit_to_target,
        protection=protection,
    )

    meta_build = _build_create_meta(
        feature_dir=scaffold.feature_dir,
        mission_id=mission_id,
        mid8=mid8,
        mission_slug_formatted=mission_slug_formatted,
        normalized_friendly_name=normalized_friendly_name,
        purpose=purpose,
        mission=mission,
        planning_branch=planning_branch,
        pr_bound=pr_bound,
        retain_branches=retain_branches,
        retain_worktrees=retain_worktrees,
        commit_to_target=commit_to_target,
        resolved_root=resolved_root,
        topology=topology,
        force_recreate_coordination_branch=force_recreate_coordination_branch,
        created_at=_created_at,
    )
    # Step 6.7: the protected-target mint runs here, after the
    # coordination-branch mint inside ``_build_create_meta`` and before the
    # ``meta.json`` write, which records the ``mission_branch`` it may set.
    minted_mission_branch = _mint_protected_branch_for_topology(
        write_root,
        mission_slug_formatted,
        topology=topology,
        mission_id=mission_id,
        planning_branch=planning_branch,
        meta=meta_build.meta,
        protection=protection,
    )
    _write_create_meta(scaffold.feature_dir, meta_build.meta, mission)
    meta_build = replace(meta_build, minted_mission_branch=minted_mission_branch)
    if meta_build.minted_mission_branch is not None:
        # #5100 (6.7): the scaffold commit must land on the branch the mint
        # just checked out -- `create_time_target` was resolved BEFORE the
        # mint, from the (protected) planning branch. Without this,
        # `safe_commit`'s HEAD-vs-destination check sees the write checkout on
        # the minted branch but a destination of the protected
        # `planning_branch`, raises `SafeCommitHeadMismatch`, and the scaffold
        # commit silently treats it as an ordinary protected-target skip --
        # leaving the just-minted branch with no scaffold commit at all.
        # Re-derived through the SAME create-time seam (no mission identity is
        # readable yet), never a hand-built CommitTarget.
        create_time_target = resolve_create_time_write_target(meta_build.minted_mission_branch)

    # D6/T031: for a coordination-routed topology, materialize + seed the
    # coordination surface BEFORE the creation events are emitted, so they
    # land on the coordination Mission dir from birth instead of the target
    # branch's scaffold (#5440). Runs after ``_write_create_meta`` (the
    # coordination branch must already be minted and ``meta.json`` written,
    # since ``write_dir`` reads it back) and before the target scaffold
    # commit below (D6 "create order").
    coord_seed = _seed_coord_surface_for_create(
        resolved_root=resolved_root,
        mission_slug_formatted=mission_slug_formatted,
        mid8=mid8,
        topology=topology,
        meta_build=meta_build,
        owned=roots.owned,
        rollback_journal=_rollback_journal,
    )

    created_event, phase_event = _emit_create_events(
        feature_dir=scaffold.feature_dir,
        mission_slug_formatted=mission_slug_formatted,
        meta=meta_build.meta,
        planning_branch=planning_branch,
        resolved_root=resolved_root,
        write_root=write_root,
        purpose=purpose,
        normalized_friendly_name=normalized_friendly_name,
        spec_file=scaffold.spec_file,
        lifecycle_root=roots.owned.repository_root if roots.owned is not None else None,
        status_dir=coord_seed.status_dir,
    )

    if coord_seed.status_dir is not None:
        # T031/T032: committed unconditionally, outside the target scaffold
        # commit's bootstrap-skip handling (FR-002a) -- a refusal here raises
        # so the failure-atomic wrapper's rollback (coord_seed.rollback_ctx,
        # recorded above) runs.
        _commit_coord_create_events(resolved_root, mission_slug_formatted, mission_id, coord_seed.status_dir)

    commit_outcome = _commit_create_scaffold(
        scaffold=scaffold,
        resolved_root=resolved_root,
        write_root=write_root,
        create_time_target=create_time_target,
        mission_slug_formatted=mission_slug_formatted,
        planning_branch=planning_branch,
        meta=meta_build.meta,
    )

    return _build_create_result(
        scaffold=scaffold,
        commit_outcome=commit_outcome,
        mission_slug_formatted=mission_slug_formatted,
        planning_branch=planning_branch,
        current_branch=current_branch,
        coordination_branch_created=meta_build.coordination_branch_created,
        resolved_root=resolved_root,
        owned_create_root=roots.owned,
        created_event=created_event,
        phase_event=phase_event,
        status_log_path=(coord_seed.status_dir / "status.events.jsonl") if coord_seed.status_dir is not None else None,
    )
