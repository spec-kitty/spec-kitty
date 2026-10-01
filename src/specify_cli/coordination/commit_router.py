"""Mission-aware planning-commit router (FR-001/002/005).

Extracted from ``cli/commands/agent/mission.py`` to provide a single canonical
``commit_for_mission`` entry point that:

1. Resolves the placement via ``mission_runtime.resolve_placement_only``.
2. If the resolved placement is COORDINATION and the policy marks the target ref
   as protected, materialises the coordination worktree on demand and stages the
   artifacts there before committing.
3. Otherwise commits directly to the primary checkout (flattened / unprotected).

This module owns the extraction described in WP02 / IC-02. The three formerly
open-coded inline commit tails in ``mission.py`` (gap-analysis, generator-config,
finalize-tasks) are folded into this entry point (T027 / #2056).

Design basis: ``plan.md`` (IC-02), ADR ``2026-06-21-1``.

C-001 (no parallel materialiser): every coordination worktree materialisation
goes through the single canonical ``CoordinationWorkspace.resolve()`` path.
NFR-001 (#1718 create-window): materialisation happens at the COMMIT boundary,
not at read time.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Iterator, Mapping
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final, Literal, Protocol, runtime_checkable

from kernel.git import status_entries
from mission_runtime import (
    CommitTarget,
    MissionArtifactKind,
    OwnedCheckout,
    is_primary_artifact_kind,
    kind_for_mission_file,
    resolve_placement_only,
    resolve_topology,
    routes_through_coordination,
)
from specify_cli.coordination.coherence import is_coord_residue_churn
from specify_cli.coordination.surface_authority import Refuse, resolve_surface_authority
from specify_cli.git import safe_commit
from specify_cli.status import FeatureStatusLockTimeoutError


class CoordWorktreeResolutionError(RuntimeError):
    """A coordination-routed mission reached the commit seam in a corrupt state (INV-3 / DIR-043).

    DD-3 / FR-002 (coord-commit-surface-authority WP04): the coord-staging helpers
    (:func:`_materialise_coord_worktree`, :func:`_resolve_commit_worktree_for_kind`)
    are reached ONLY after the caller has decided the mission routes through
    coordination (``use_coord`` / ``routes_through_coordination`` of the STORED
    topology). If, at that point, the mission's ``mission_id`` is unresolvable
    (missing / short / corrupt ``meta.json``) or its coordination worktree fails to
    resolve, the artifact CANNOT reach its authoritative coordination surface. The
    former behavior silently returned the PRIMARY checkout — committing (or
    no-op-ing) a coordination-kind artifact onto the primary tree, the exact
    "silent misroute to primary" defect class INV-3 forbids. This is raised (a
    :class:`RuntimeError` subclass, so the command boundary maps it to a non-zero
    JSON-mode exit — see ``spec_commit_cmd.py``'s ``except RuntimeError`` arm)
    instead of falling back, closing the defect class by construction (DIR-043)
    rather than by comment. Flattened / ``SINGLE_BRANCH`` / ``LANES`` missions never
    reach these helpers, so no legitimate caller relied on the fallback.
    """


class PrimaryKindReachedCoordStagingError(RuntimeError):
    """A PRIMARY-partition kind reached the coordination staging path (DECISION 8).

    write-surface-coherence WP05 / FR-005 / C-004: once planning no longer transits
    the coordination worktree (WP02/WP03), the coord-staging helpers are reachable
    ONLY for coordination-partition writes. A ``_PRIMARY_ARTIFACT_KINDS`` member
    arriving at :func:`_materialise_coord_worktree` / the staging helper would mean
    a planning artifact is being staged onto the coordination branch — the exact
    mis-route the partition was built to forbid. This is raised (not asserted, so
    the invariant holds under ``python -O``) to keep "planning never reaches coord
    staging" an ENFORCED invariant rather than a comment.
    """


@runtime_checkable
class _ProtectionPolicyProtocol(Protocol):
    """Structural protocol for the ProtectionPolicy duck-type used by commit_for_mission.

    Avoids a hard circular import (commit_router → protection_policy → git →
    commit_helpers) by matching on structure rather than on the concrete class.
    """

    def is_protected(self, ref: str) -> bool: ...


logger = logging.getLogger(__name__)


def _mission_scoped(
    policy: _ProtectionPolicyProtocol,
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> _ProtectionPolicyProtocol:
    """Fold the mission's ``commit_to_target`` into *policy* for this mission's own write (#5100 FR-008).

    Only a real ``ProtectionPolicy`` carries the mission-scoped hatch; a duck-typed
    stand-in is returned untouched (no bypass -- fail-closed). On the owned arm
    the ONE owned authority, ``ProtectionPolicy.resolve_for_owned``, folds the
    mission from the fact (owned-checkout-lifecycle-authority) instead of
    re-deriving the repository root from the slug.
    """
    if owned is not None:
        if getattr(policy, "scoped_to_mission", None) is None:
            return policy
        from specify_cli.git.protection_policy import ProtectionPolicy

        return ProtectionPolicy.resolve_for_owned(owned, mission_slug)
    for_mission = getattr(policy, "for_mission", None)
    if for_mission is None:
        return policy
    scoped: _ProtectionPolicyProtocol = for_mission(repo_root, mission_slug)
    return scoped


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

# T021 (Sonar S1192 campsite): the router's outcome vocabulary — named once so
# every ``CommitRouterResult`` construction site (8 across this module) shares
# ONE spelling instead of restating the raw string. This is the "in-band
# strangle vocabulary" the reviewer guidance calls out: the placement-outcome
# literal is domain vocabulary, not incidental formatting, so it earns a name.
_STATUS_COMMITTED: Final = "committed"
_STATUS_UNCHANGED: Final = "unchanged"

# FR-003 (coord-commit-integrity): the re-homed PRIMARY analysis-report basename.
# Named once so the coord-staging skip (mirroring the STATUS_STATE-kind skip,
# WP13-retired ``COORD_OWNED_STATUS_FILES``) does not restate the raw literal.
_ANALYSIS_REPORT_FILENAME: Final = "analysis-report.md"
_STATUS_NO_OP_WRONG_SURFACE: Final = "no_op_wrong_surface"
_STATUS_ERROR: Final = "error"

# #255 fix-round-2 (squad pass 2 MAJOR): the planning SOURCE-doc kinds a
# mission produces BEFORE ``/spec-kitty.tasks`` has run (mirrors the "Planning
# SOURCE docs" grouping in ``mission_runtime.artifacts``). The protected-branch
# refusal below needs to know this membership because the FR-012
# `finalize-tasks --target-branch` escape hatch only persists once
# ``tasks/`` exists -- recommending it for one of these kinds writes the
# override and then silently reverts it (mission_finalize.py's
# ``_revert_unpersisted_target_branch_override``).
_PRE_TASKS_ARTIFACT_KINDS: Final[frozenset[MissionArtifactKind]] = frozenset(
    {
        MissionArtifactKind.SPEC,
        MissionArtifactKind.DATA_MODEL,
        MissionArtifactKind.RESEARCH,
        MissionArtifactKind.CHECKLIST,
    }
)

# #2739 B03: machine-readable ``reason`` strings for the two ``unchanged``
# no-op flavours, so a caller can tell "nothing to do" from "silently wrong".
# Named once (S1192) — every ``_STATUS_UNCHANGED`` construction site carries one.
_REASON_ALREADY_COMMITTED: Final = "no_op_already_committed"
_REASON_NO_CHANGES: Final = "no_op_no_changes"

# #2739 B01: the operator hatch that permits a commit on a protected branch.
# Named once and reused by the protected-refusal diagnostic below (S1192).
_ENV_HATCH: Final = "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"


@dataclass(frozen=True)
class CommitRouterResult:
    """Typed outcome of :func:`commit_for_mission`.

    status values:
    - ``_STATUS_COMMITTED``        — ``safe_commit`` landed a real commit.
    - ``_STATUS_UNCHANGED``        — benign no-op: artifact present + already committed.
    - ``_STATUS_NO_OP_WRONG_SURFACE`` — artifact absent at resolved placement.
    - ``_STATUS_ERROR``            — commit failed unexpectedly.

    ``commit_hash`` / ``placement_ref`` remain the historical single-commit
    projection (the CALLER-partition outcome — see :func:`_merge_group_results`)
    for backward compatibility. ``commit_hashes`` (#2549 facet B) additionally
    carries the FULL commit set as ``(placement_ref, commit_hash)`` pairs, one
    per partition group that actually committed. For the common single-group
    case this holds exactly the same one entry as ``commit_hash`` /
    ``placement_ref``; for a genuinely split (mixed-partition, coord-topology)
    batch it also carries the second commit — e.g. the coordination-branch
    commit alongside the caller-partition (feature-branch) one — that the
    single-value fields alone cannot express.
    """

    status: Literal["committed", "unchanged", "no_op_wrong_surface", "error"]
    placement_ref: str
    commit_hash: str | None = None
    commit_hashes: tuple[tuple[str, str], ...] = ()
    diagnostic: str | None = None
    #: Machine-readable disambiguator for an ``unchanged`` no-op (#2739 B03):
    #: ``no_op_already_committed`` (artifact present + already committed) vs
    #: ``no_op_no_changes`` (nothing to commit / empty changeset). ``None`` for
    #: every non-``unchanged`` status.
    reason: str | None = None


def mission_has_coordination_branch(repo_root: Path, mission_slug: str) -> bool:
    """Return whether the mission's stored topology mints a coordination branch."""
    return routes_through_coordination(resolve_topology(repo_root, mission_slug))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def commit_for_mission(
    repo_root: Path,
    mission_slug: str,
    files: tuple[Path, ...],
    message: str,
    policy: _ProtectionPolicyProtocol,
    *,
    kind: MissionArtifactKind,
    primary_paths_created_this_invocation: frozenset[Path] | None = None,
    target_branch: str | None = None,
    owned: OwnedCheckout | None = None,
    expected_parent_sha: str | None = None,
    expected_path_bytes: Mapping[Path, bytes] | None = None,
) -> CommitRouterResult:
    """Commit a mission artifact to its kind-aware resolved placement.

    This is the single canonical commit entry point for all planning-phase
    artifacts (spec, plan, tasks, gap-analysis, generator-config,
    analysis-report — all PRIMARY-partition) and the coordination-owned ones
    (acceptance-matrix, issue-matrix, status views). It replaces the formerly
    open-coded inline tails in ``agent/mission.py``.

    Args:
        repo_root:   Primary checkout root (where ``kitty-specs/`` lives).
        mission_slug: Mission handle (e.g. ``"001-my-mission"``).
        files:       Absolute paths of artifacts to commit.
        message:     Commit message.
        policy:      A :class:`~specify_cli.git.protection_policy.ProtectionPolicy`
                     instance (accepted via the structural
                     :class:`_ProtectionPolicyProtocol` to avoid a circular import;
                     duck-typed via ``is_protected``).
        kind:        The :class:`~mission_runtime.MissionArtifactKind` being
                     committed. REQUIRED keyword (DECISION 1 / write-surface-coherence
                     WP02): there is no default, mirroring the now-required
                     ``resolve_placement_only`` kind. A primary kind resolves to
                     the primary ``target_branch`` for every topology and NEVER
                     routes through coordination; a coordination kind keeps the
                     topology-routed placement. An un-threaded caller fails to
                     typecheck rather than silently mis-routing (FR-003 / C-005).
        primary_paths_created_this_invocation: Paths the caller materialised this
                     invocation (eligible for residue cleanup after staging, R6).
        target_branch: Short primary branch name for the post-commit ff-advance
                     (WP09 / FR-010 / #1878). Optional; advance is skipped when
                     ``None``.
        expected_parent_sha: Optional captured parent for a conditional ref update.
        expected_path_bytes: Optional exact raw bytes for selected paths in that
                     expected-parent commit; clean-filter rewrites are refused.

    Returns:
        :class:`CommitRouterResult` with the typed outcome.

    Per-file partition awareness (FR-007 / C-006 / contracts/partition-aware-
    commit-seam.md): ``files`` is classified and grouped by PARTITION (PRIMARY
    vs PLACEMENT) *before* placement is resolved — see
    :func:`_group_files_by_partition`. This closes the #2404 class of defect
    (a mixed-partition batch under one ``kind`` misrouting every file to that
    kind's partition) at the seam, with no per-caller patch. A genuinely
    single-partition batch (the common case) still resolves placement exactly
    once and issues exactly one commit (INV: no fast-path regression).
    """
    groups = [(kind, files)] if owned is not None else _group_files_by_partition(repo_root, files, mission_slug, kind=kind)

    if expected_path_bytes is not None and expected_parent_sha is None:
        return CommitRouterResult(
            status=_STATUS_ERROR,
            placement_ref=target_branch or "",
            diagnostic="expected path bytes require an expected-parent commit",
        )

    if expected_parent_sha is not None and len(groups) != 1:
        return CommitRouterResult(
            status=_STATUS_ERROR,
            placement_ref=target_branch or "",
            diagnostic="expected-parent commits require exactly one resolved partition group",
        )

    if len(groups) <= 1:
        effective_kind, effective_files = groups[0] if groups else (kind, files)
        return _commit_partition_group(
            repo_root,
            mission_slug,
            effective_files,
            message,
            policy,
            kind=effective_kind,
            primary_paths_created_this_invocation=primary_paths_created_this_invocation,
            target_branch=target_branch,
            owned=owned,
            expected_parent_sha=expected_parent_sha,
            expected_path_bytes=expected_path_bytes,
        )

    # Split-and-commit (contract (a), pinned by T004): a mixed-partition batch
    # is transparently split into one commit PER partition group, each resolved
    # and committed through the SAME single-group path the fast path uses — no
    # parallel commit logic, no caller-visible change to the entry point.
    results = [
        _commit_partition_group(
            repo_root,
            mission_slug,
            group_files,
            message,
            policy,
            kind=group_kind,
            primary_paths_created_this_invocation=primary_paths_created_this_invocation,
            target_branch=target_branch,
        )
        for group_kind, group_files in groups
    ]
    return _merge_group_results(results, groups, kind)


def _resolve_group_placement(
    repo_root: Path,
    mission_slug: str,
    policy: _ProtectionPolicyProtocol,
    *,
    kind: MissionArtifactKind,
    owned: OwnedCheckout | None,
) -> tuple[CommitTarget, bool, CommitRouterResult | None]:
    """Resolve one group's placement + coord-routing decision (T035 campsite extraction).

    Behaviour-preserving extraction of ``_commit_partition_group``'s former
    placement/``use_coord`` decision (complexity 15 -> <=11, plan Complexity
    note). Returns ``(placement, use_coord, refusal)``; a non-``None``
    ``refusal`` means the caller must return it immediately without
    committing (the protected-primary ``Refuse`` verdict, unchanged).
    """
    if owned is not None:
        placement = resolve_placement_only(repo_root, mission_slug, kind=kind, owned=owned)
    else:
        placement = resolve_placement_only(repo_root, mission_slug, kind=kind)

    # FR-003 / C-005 / NFR-004: derive coord-vs-primary routing from the ONE
    # kind-aware ``placement`` (the single authority), not a second predicate.
    # The placement already encodes the partition: a ``_PRIMARY_ARTIFACT_KINDS``
    # member resolves to the primary ``target_branch`` for EVERY topology shape,
    # so it is a direct primary commit; every other kind keeps the topology-routed
    # destination ref. ``use_coord`` is True iff the mission routes through
    # coordination AND the kind-aware placement did NOT land on the primary target
    # branch — i.e. only coordination kinds materialise the coord worktree (C-001).
    # A primary kind therefore NEVER routes to coordination even under coord
    # topology — this removes the planning→coord arm (write-surface-coherence WP02).
    #
    # owned (review cycle 1 issue 3b): when a fact is present, its stored
    # ``topology`` is used DIRECTLY instead of calling ``resolve_topology``,
    # which walks ``get_main_repo_root(repo_root)`` back to R -- an
    # R-touching read "the fact is the single representation" forbids on the
    # owned path. ``owned.topology`` is the same WP02 stored topology value
    # ``resolve_topology`` would derive for this mission (minted once by
    # ``specify_cli.core.owned_mission`` at the same read that would
    # otherwise re-derive it here), so this is behaviour-preserving.
    topology = owned.topology if owned is not None else resolve_topology(repo_root, mission_slug)
    primary_target = placement.ref if owned is not None else _resolve_mission_target_branch(repo_root, mission_slug)
    use_coord = owned is None and routes_through_coordination(topology) and placement.ref != primary_target

    # T016 / INV-4 (shared-rule consultation): the protected-primary refusal now
    # DERIVES from the single authority :func:`resolve_surface_authority` (contract
    # rules 1–5) instead of a hardcoded ``not use_coord and is_protected`` predicate.
    # A :class:`~specify_cli.coordination.surface_authority.Refuse` verdict maps to
    # ``_STATUS_NO_OP_WRONG_SURFACE`` — the router's exit-1 refusal surface (the CLI
    # maps ``no_op_wrong_surface`` → exit 1); the typed GENUINE no-ops below
    # (``unchanged`` / ``no_op_already_committed`` / ``no_op_no_changes``) stay
    # exit 0 (#2739 contract preserved). ``primary_protected`` already folds the
    # operator hatch (rule 6) via ``policy.is_protected``. In the ``not use_coord``
    # arm ``placement.ref == primary_target`` always holds (a coord-less topology
    # resolves every kind to ``target_branch``; a coord kind that diverged would
    # have set ``use_coord``), so keying protection on ``placement.ref`` matches the
    # rule's ``primary_target`` exactly. ``current_branch`` is informational only
    # (the rule keys on target protection, not the checkout).
    if not use_coord:
        verdict = resolve_surface_authority(
            topology,
            primary_target,
            primary_protected=_mission_scoped(policy, repo_root, mission_slug, owned=owned).is_protected(placement.ref),
            current_branch="",
            artifact_kind=kind,
            coord_ref=placement.ref,
        )
        if isinstance(verdict.non_committable, Refuse):
            # Refuse (rule 3). This mission already exists, so the safe remedy
            # depends on whether tasks exist: pre-tasks overrides are reverted,
            # while later missions can durably retarget through finalize-tasks.
            if kind in _PRE_TASKS_ARTIFACT_KINDS:
                remedy = (
                    f"No tasks have been generated for this mission yet, so the "
                    f"finalize-tasks --target-branch override has nothing durable "
                    f"to attach to and would silently revert. Start a mission on "
                    f"a feature branch instead: 'spec-kitty agent mission create "
                    f"{mission_slug} --start-branch <feature-branch>'."
                )
            else:
                remedy = (
                    f"Check out or create a non-protected feature branch, then "
                    f"persist it onto this mission with: 'spec-kitty agent mission "
                    f"finalize-tasks --mission {mission_slug} --target-branch "
                    f"<feature-branch>'."
                )
            return (
                placement,
                use_coord,
                CommitRouterResult(
                    status=_STATUS_NO_OP_WRONG_SURFACE,
                    placement_ref=placement.ref,
                    diagnostic=(
                        f"Refusing to commit planning artifacts to the protected branch "
                        f"'{placement.ref}'. This mission's target_branch is protected. "
                        f"{remedy} "
                        f"Planning artifacts must land on a feature branch. To commit on "
                        f"the current protected branch anyway, set "
                        f"{_ENV_HATCH}=1."
                    ),
                ),
            )

    return placement, use_coord, None


def _classify_no_commit_paths(
    repo_root: Path,
    files: tuple[Path, ...],
    *,
    use_coord: bool,
    placement: CommitTarget,
) -> CommitRouterResult:
    """Classify an empty ``commit_paths`` result (T035 campsite extraction).

    Behaviour-preserving extraction of ``_commit_partition_group``'s former
    empty-commit-paths / wrong-surface classification.
    """
    # #2739 B16 / #2694: distinguish a genuine no-op (artifact present +
    # already committed) from a WRONG-SURFACE no-op. When the mission routes
    # through coordination and coord staging skipped every artifact (e.g. a
    # STATUS-partition file that ``_stage_artifacts_in_coord_worktree`` never
    # copies), but the SOURCE artifact is still present-and-uncommitted in the
    # primary checkout, the commit landed nowhere — the write would falsely
    # report a benign no-op against the coord branch while the primary tree
    # stays dirty. Mirror the ``_any_path_absent`` wrong-surface detection and
    # refuse instead (T008 surfaces the actionable error).
    if use_coord and _paths_uncommitted_in_primary(repo_root, files):
        return CommitRouterResult(
            status=_STATUS_NO_OP_WRONG_SURFACE,
            placement_ref=placement.ref,
            diagnostic=(
                f"Artifact(s) written to the primary checkout routed to the "
                f"coordination placement ({placement.ref}) where nothing was "
                f"staged; the commit would no-op against the wrong surface and "
                f"the artifact remains uncommitted in the primary tree. Commit "
                f"it to its own (primary) surface instead."
            ),
        )
    # All artifacts already committed (or none present) — genuine no-op.
    return CommitRouterResult(
        status=_STATUS_UNCHANGED,
        placement_ref=placement.ref,
        reason=_REASON_ALREADY_COMMITTED,
    )


def _commit_partition_group(
    repo_root: Path,
    mission_slug: str,
    files: tuple[Path, ...],
    message: str,
    policy: _ProtectionPolicyProtocol,
    *,
    kind: MissionArtifactKind,
    primary_paths_created_this_invocation: frozenset[Path] | None = None,
    target_branch: str | None = None,
    owned: OwnedCheckout | None = None,
    expected_parent_sha: str | None = None,
    expected_path_bytes: Mapping[Path, bytes] | None = None,
) -> CommitRouterResult:
    """Commit ONE single-partition file group to its resolved placement.

    This is the pre-WP01 body of ``commit_for_mission`` verbatim, extracted so
    the public entry point can invoke it once per partition group (T002/T004).
    Every file in ``files`` MUST already belong to the SAME partition as
    ``kind`` — :func:`_group_files_by_partition` guarantees this; this helper
    does not re-validate it (single responsibility: resolve + commit one group).
    """
    placement, use_coord, refusal = _resolve_group_placement(repo_root, mission_slug, policy, kind=kind, owned=owned)
    if refusal is not None:
        return refusal

    if use_coord:
        worktree_root, commit_paths = _materialise_coord_worktree(
            repo_root,
            mission_slug,
            placement,
            files,
            kind=kind,
            primary_paths_created_this_invocation=primary_paths_created_this_invocation,
        )
    else:
        # Flattened or unprotected primary: commit directly.
        worktree_root, commit_paths = owned.owned_root if owned is not None else repo_root, files

    if not commit_paths:
        return _classify_no_commit_paths(repo_root, files, use_coord=use_coord, placement=placement)

    # FR-006 / D-5: detect no-op against the wrong surface.
    if _any_path_absent(commit_paths):
        diagnostic = (
            f"Artifact(s) not present at resolved placement "
            f"({placement.ref}, worktree={worktree_root}); commit would no-op "
            f"against the wrong surface and was not created."
        )
        return CommitRouterResult(
            status=_STATUS_NO_OP_WRONG_SURFACE,
            placement_ref=placement.ref,
            diagnostic=diagnostic,
        )

    commit_result = _safe_commit_group(
        repo_root,
        worktree_root,
        placement,
        message,
        commit_paths,
        use_coord=use_coord,
        owned=owned,
        expected_parent_sha=expected_parent_sha,
        expected_path_bytes=expected_path_bytes,
    )
    if isinstance(commit_result, CommitRouterResult):
        return commit_result

    commit_hash: str | None = None
    if commit_result is not None and hasattr(commit_result, "sha"):
        commit_hash = commit_result.sha

    # WP09 / FR-010 (#1878): best-effort ff-advance after a coord write. This
    # fires ONLY on the coord branch (``use_coord`` True ⇒ a coordination kind),
    # so it now advances ``target_branch`` to a STATUS/bookkeeping-only coord HEAD
    # (write-surface-coherence WP05 / FR-005): planning no longer transits coord,
    # so the coord HEAD never mixes planning+status. The
    # ``is_residue=is_toolchain_generated_churn`` exclusion in
    # ``_try_advance_ref`` (WP13 retired the former ``coord_owned_filenames``
    # param onto the single canonical churn owner) still matches exactly what a
    # status-only coord write produces — no behaviour change for status writes;
    # the planning case is gone.
    if use_coord and target_branch:
        _try_advance_ref(repo_root, target_branch, worktree_root, mission_slug=mission_slug)

    return CommitRouterResult(
        status=_STATUS_COMMITTED,
        placement_ref=placement.ref,
        commit_hash=commit_hash,
        commit_hashes=((placement.ref, commit_hash),) if commit_hash else (),
        diagnostic=getattr(commit_result, "diagnostic", None),
    )


def _coord_status_dirs(worktree_root: Path, commit_paths: tuple[Path, ...]) -> list[Path]:
    """The coord feature dirs of the STATUS_STATE files in a coord commit, sorted (stable lock order)."""
    dirs: set[Path] = set()
    for path in commit_paths:
        try:
            rel = path.relative_to(worktree_root)
        except ValueError:
            continue
        if kind_for_mission_file(rel) is MissionArtifactKind.STATUS_STATE:
            dirs.add(path.parent)
    return sorted(dirs)


@contextmanager
def _coord_status_locks(repo_root: Path, worktree_root: Path, commit_paths: tuple[Path, ...], *, use_coord: bool) -> Iterator[None]:
    """Hold the status lock (L1) of every coord-resident status log this commit carries.

    A coord-resident ``status.events.jsonl`` / ``status.json`` is the log the
    transactional status shell appends to and commits under L1
    (``status_transition._emit_on_coord_then_commit``). Committing it outside
    that lock sweeps a concurrent transition's appended-but-uncommitted row: the
    transition's own commit then finds an empty changeset and its rollback
    truncates a row that already landed (#5353). The lock is taken through the
    shell's own :func:`~specify_cli.coordination.status_transition.coord_status_lock`
    so both sides hold the identical lock; it is re-entrant, so a caller that
    already holds it is not deadlocked.
    """
    if not use_coord:
        yield
        return
    from specify_cli.coordination.status_transition import coord_status_lock

    with ExitStack() as stack:
        for status_dir in _coord_status_dirs(worktree_root, commit_paths):
            stack.enter_context(coord_status_lock(repo_root, status_dir))
        yield


def _safe_commit_group(
    repo_root: Path,
    worktree_root: Path,
    placement: CommitTarget,
    message: str,
    commit_paths: tuple[Path, ...],
    *,
    use_coord: bool,
    owned: OwnedCheckout | None,
    expected_parent_sha: str | None,
    expected_path_bytes: Mapping[Path, bytes] | None,
) -> object:
    """Run ``safe_commit`` for one group; a failure or no-op comes back as a :class:`CommitRouterResult`.

    A status-lock timeout is an ``error`` result naming the contended lock, so a
    caller reports it like any other failed commit.
    """
    try:
        with _coord_status_locks(repo_root, worktree_root, commit_paths, use_coord=use_coord):
            return safe_commit(
                repo_root=repo_root,
                worktree_root=worktree_root,
                target=placement,
                message=message,
                paths=commit_paths,
                owned=owned,
                **({"expected_parent_sha": expected_parent_sha} if expected_parent_sha is not None else {}),
                **({"expected_path_bytes": expected_path_bytes} if expected_path_bytes is not None else {}),
            )
    except FeatureStatusLockTimeoutError as exc:
        return CommitRouterResult(status=_STATUS_ERROR, placement_ref=placement.ref, diagnostic=str(exc))
    except subprocess.CalledProcessError as exc:
        stderr = getattr(exc, "stderr", "") or ""
        if "nothing to commit" in stderr or "nothing added to commit" in stderr:
            return CommitRouterResult(status=_STATUS_UNCHANGED, placement_ref=placement.ref, reason=_REASON_NO_CHANGES)
        return CommitRouterResult(status=_STATUS_ERROR, placement_ref=placement.ref, diagnostic=str(exc))
    except RuntimeError as exc:
        if _is_empty_changeset_error(exc):
            return CommitRouterResult(status=_STATUS_UNCHANGED, placement_ref=placement.ref, reason=_REASON_NO_CHANGES)
        return CommitRouterResult(status=_STATUS_ERROR, placement_ref=placement.ref, diagnostic=str(exc))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


#  FR-005 / C-007: canonical fallback representative kinds used ONLY when a
#  bucket's ref must be resolved but none of its files carry a recognised
#  kind (``kind_for_mission_file`` returns ``None`` for every member — e.g. a
#  solo ``meta.json`` / unrecognised-path batch). The specific member does not
#  matter: ``resolve_placement_only`` resolves the IDENTICAL ref for any kind
#  sharing a partition (see the module docstring below). A COORD bucket never
#  needs this fallback in practice — every coord-residue path already carries
#  a recognised kind by construction (``is_coord_residue_churn``
#  requires a non-``None`` classification to return True) — but a fallback is
#  still supplied defensively so the helper never raises on a malformed input.
_FALLBACK_PRIMARY_KIND: Final = MissionArtifactKind.SPEC
_FALLBACK_COORD_KIND: Final = MissionArtifactKind.STATUS_STATE


def _representative_kind_for_bucket(
    files: list[Path],
    mission_slug: str,
    *,
    expect_primary: bool,
    fallback: MissionArtifactKind,
) -> MissionArtifactKind:
    """Best-effort concrete kind for a partition bucket, for ref resolution only.

    Tries each file's OWN classification (``kind_for_mission_file``) first —
    preferring a kind the bucket's files actually carry, but only when that
    kind's OWN partition agrees with ``expect_primary`` (the partition
    :func:`_group_files_by_partition` already decided this bucket is, via the
    residue predicate) — and falls back to ``fallback`` (a fixed member of the
    target partition) when no file's classification agrees (e.g. every file
    in the bucket is ``kind=None``). The ``expect_primary`` cross-check keeps
    the residue predicate the SOLE partition authority end-to-end: even a
    ``kind_for_mission_file`` classification that disagreed with it (never
    happens for real paths — the two are derived from the same underlying
    classifier and their partitions are disjoint and exhaustive — but is
    cheap to guard) could otherwise mislabel the bucket's ref-resolution kind
    without ever touching MEMBERSHIP (that is decided exclusively by
    :func:`~specify_cli.coordination.coherence.is_coord_residue_churn` in
    :func:`_group_files_by_partition`, never by this helper).
    """
    for file in files:
        kind_f = kind_for_mission_file(file, mission_slug=mission_slug)
        if kind_f is not None and is_primary_artifact_kind(kind_f) == expect_primary:
            return kind_f
    return fallback


def _group_files_by_partition(
    repo_root: Path,
    files: tuple[Path, ...],
    mission_slug: str,
    *,
    kind: MissionArtifactKind,
) -> list[tuple[MissionArtifactKind, tuple[Path, ...]]]:
    """Group ``files`` by PARTITION (PRIMARY vs COORD), not by exact kind (T023).

    FR-005 / C-007 (#2650 / #2533): each file's partition membership is
    decided by the SAME absolute authority the read-side (``implement_cores.
    py::resolve_precondition_ref``) and write-side cli
    (``implement.py::_partition_files_for_commit``) sites already use —
    :func:`~specify_cli.coordination.coherence.is_coord_residue_churn` — instead
    of the divergent ``kind_for_mission_file(file) or kind`` classifier this
    helper used before. A ``None`` classification (``meta.json``, an
    unrecognised path) is NOT coord-residue, so it now routes PRIMARY
    UNCONDITIONALLY — never falling back to (and never inheriting) the
    caller's own partition. This closes the #2533-class hole: previously a
    ``kind=None`` file bundled under a COORD-kind caller (e.g. a ``move_task``
    status commit) silently joined the caller's COORD group instead of its
    own (PRIMARY) home.

    The buckets are ABSOLUTE, not relative to the caller: a PRIMARY-partition
    file always resolves against a PRIMARY ref and a COORD-partition file
    always resolves against the COORD ref, regardless of which partition
    ``kind`` (the caller's own artifact kind) belongs to. ``resolve_placement_
    only`` is still the sole ref-resolution authority for both buckets (the
    swap is classifier-only, not ref-resolution) — see
    :func:`_representative_kind_for_bucket` for how a concrete kind is chosen
    per bucket to drive that call.

    Coordless-topology coincidence (regression guard, #2155): under a topology
    that does not route through coordination (``SINGLE_BRANCH`` / ``LANES``),
    EVERY kind's placement — primary or coord-partition — resolves to the SAME
    ``target_branch``. Splitting a genuinely mixed batch into two commits in
    that case would be a pure regression (an existing atomic-commit caller,
    ``move_task``'s ``WORK_PACKAGE_TASK`` + ``STATUS_STATE`` bundle, expects
    ONE commit) with no benefit — both buckets' own ref IS the same ref. So
    when both buckets are non-empty their refs are resolved and compared, and
    the groups collapse back into the historical single-group call when they
    coincide; only a genuine ref DIVERGENCE is split.

    Returns a list of ``(representative_kind, files)`` groups:

    - Zero groups when ``files`` is empty.
    - One group ``(kind, files)`` when every file shares the caller's OWN
      partition (the byte-identical-to-today fast path — no
      ``resolve_placement_only`` call is made in this branch).
    - One group ``(representative_kind, files)`` when every file belongs to
      the SAME (single) partition even though it disagrees with the caller's
      own ``kind`` — the #2533-class fix: this partition's OWN ref is used,
      never the caller's.
    - One group ``(kind, files)`` when both partitions are present but
      resolve to the SAME ref (the coordless-topology collapse above).
    - Two groups when the batch is genuinely mixed AND the two partitions'
      refs diverge (the #2404 defect shape).
    """
    if not files:
        return []

    caller_is_primary = is_primary_artifact_kind(kind)
    primary_files: list[Path] = []
    coord_files: list[Path] = []
    for file in files:
        if is_coord_residue_churn(file, mission_slug=mission_slug):
            coord_files.append(file)
        else:
            primary_files.append(file)

    caller_partition_holds_everything = (caller_is_primary and not coord_files) or (not caller_is_primary and not primary_files)
    if caller_partition_holds_everything:
        # Every file lands in the caller's own partition — the historical
        # fast path: no extra resolve_placement_only call, byte-identical to
        # the pre-#2650 single-group call.
        return [(kind, files)]

    primary_kind = kind if caller_is_primary else _representative_kind_for_bucket(primary_files, mission_slug, expect_primary=True, fallback=_FALLBACK_PRIMARY_KIND)
    coord_kind = kind if not caller_is_primary else _representative_kind_for_bucket(coord_files, mission_slug, expect_primary=False, fallback=_FALLBACK_COORD_KIND)

    if primary_files and coord_files:
        primary_ref = resolve_placement_only(repo_root, mission_slug, kind=primary_kind).ref
        coord_ref = resolve_placement_only(repo_root, mission_slug, kind=coord_kind).ref
        if primary_ref == coord_ref:
            # No real routing divergence (coordless topology) — keep the
            # historical single-commit fast path instead of a gratuitous
            # second commit.
            return [(kind, files)]

    groups: list[tuple[MissionArtifactKind, tuple[Path, ...]]] = []
    if primary_files:
        groups.append((primary_kind, tuple(primary_files)))
    if coord_files:
        groups.append((coord_kind, tuple(coord_files)))
    return groups


def _merge_group_results(
    results: list[CommitRouterResult],
    groups: list[tuple[MissionArtifactKind, tuple[Path, ...]]],
    caller_kind: MissionArtifactKind,
) -> CommitRouterResult:
    """Merge per-partition-group outcomes into the ONE result callers consume (T004).

    Split-and-commit (contract shape (a)): each partition group is committed to
    its OWN :class:`CommitTarget` (INV-C1) via :func:`_commit_partition_group`,
    but ``commit_for_mission`` still returns a single :class:`CommitRouterResult`
    — the historical shape every existing caller (``spec_commit_cmd.py`` /
    ``mission_finalize.py``) already consumes.

    Priority:
    1. A real git error on ANY group is never silently swallowed — it takes
       priority over a "committed" outcome on another group (an error is
       actionable; masking it behind an unrelated group's success is unsafe).
    2. Otherwise the group matching the CALLER-supplied ``kind``'s own partition
       is authoritative — it is the artifact the caller named in this
       invocation, and its outcome is what existing callers' UI messages
       describe (e.g. "Tasks committed to <ref>").
    3. If no group matches the caller's own partition (should not happen once
       :func:`_group_files_by_partition` always includes it when present),
       fall back to the first group's result deterministically.

    #2549 facet B: regardless of which group is authoritative for the legacy
    single-value ``commit_hash`` / ``placement_ref`` fields, the returned
    result's ``commit_hashes`` is always the UNION of every committed group's
    ``commit_hashes`` — so a genuinely split commit (e.g. feature-branch +
    coordination-branch) reports BOTH hashes, not just the caller-partition one.
    """
    for result in results:
        if result.status == _STATUS_ERROR:
            return result

    all_commit_hashes = tuple(pair for result in results for pair in result.commit_hashes)

    caller_is_primary = is_primary_artifact_kind(caller_kind)
    for (group_kind, _group_files), result in zip(groups, results, strict=True):
        if is_primary_artifact_kind(group_kind) == caller_is_primary:
            return replace(result, commit_hashes=all_commit_hashes)

    return replace(results[0], commit_hashes=all_commit_hashes)


def _resolve_mission_target_branch(repo_root: Path, mission_slug: str) -> str:
    """Resolve the mission's PRIMARY ``target_branch`` ref.

    This is the SAME ref ``resolve_placement_only`` returns for a primary kind
    (it reads ``get_feature_target_branch`` internally), so comparing the
    kind-aware ``placement.ref`` against it cleanly separates a primary commit
    (``placement.ref == primary_target``) from a coordination one. Resolving it
    here keeps ``use_coord`` derived from the ONE kind-aware placement authority
    (NFR-004) rather than re-deriving the partition.
    """
    from specify_cli.core.paths import get_feature_target_branch

    primary_target: str = get_feature_target_branch(repo_root, mission_slug)
    return primary_target


def _materialise_coord_worktree(
    repo_root: Path,
    mission_slug: str,
    _placement: object,
    files: tuple[Path, ...],
    *,
    kind: MissionArtifactKind,
    primary_paths_created_this_invocation: frozenset[Path] | None = None,
) -> tuple[Path, tuple[Path, ...]]:
    """Resolve (materialise on demand) the coordination worktree and stage artifacts.

    Reuses the canonical ``CoordinationWorkspace.resolve()`` path (C-001).
    FAILS LOUD on any resolution failure (DD-3 / FR-002 / INV-3, coord-commit-
    surface-authority WP04): this helper is reached ONLY for a coordination-routed
    mission (``use_coord`` in :func:`_commit_partition_group`), so an unresolvable
    ``mission_id`` or a coordination-worktree resolution error is a CORRUPT coord
    state — silently returning the primary checkout would misroute a coordination-
    kind artifact onto the primary tree (the exact INV-3 defect). Both failure sites
    raise :class:`CoordWorktreeResolutionError` (a ``RuntimeError``, mapped to a
    non-zero JSON-mode exit at the command boundary) instead of the former
    C-004 strangler-safety fallback. Flattened / ``SINGLE_BRANCH`` / ``LANES``
    missions never reach this helper, so no legitimate caller relied on the fallback.

    Args:
        repo_root:    Primary checkout root.
        mission_slug: Mission slug for workspace resolution.
        _placement:   The resolved :class:`~mission_runtime.CommitTarget`; passed
                      for interface symmetry with ``commit_for_mission`` and
                      future callers. Resolution goes through
                      ``CoordinationWorkspace`` internally.
        files:        Artifacts to stage in the coord worktree.
        kind:         The artifact kind being staged. DECISION 8 runtime guard
                      (write-surface-coherence WP05): a PRIMARY-partition kind must
                      NEVER reach coord staging — only coordination kinds do after
                      WP02/WP03 removed the planning→coord route. Reaching here with
                      a primary kind raises :class:`PrimaryKindReachedCoordStagingError`.
        primary_paths_created_this_invocation: Eligible residue paths (R6).

    Returns:
        ``(coord_worktree, coord_paths)`` on success.

    Raises:
        CoordWorktreeResolutionError: the coordination-routed mission has an
            unresolvable ``mission_id`` or its coordination worktree failed to
            resolve — fail loud rather than misroute to primary (DD-3 / INV-3).
        PrimaryKindReachedCoordStagingError: a PRIMARY-partition kind reached coord
            staging (DECISION 8 partition invariant).
    """
    # DECISION 8 / FR-005 / C-004: enforce the partition invariant at the coord
    # staging boundary. ``commit_for_mission`` only routes coordination kinds here
    # (``use_coord`` is False for primary kinds), so a primary kind arriving means a
    # caller mis-routed a planning artifact onto the coordination branch — fail loud.
    if is_primary_artifact_kind(kind):
        raise PrimaryKindReachedCoordStagingError(
            f"PRIMARY-partition kind {kind!r} reached coordination staging for "
            f"mission {mission_slug!r}; planning artifacts must commit directly to "
            f"the primary target branch and never transit the coordination worktree."
        )

    from specify_cli.coordination.workspace import CoordinationWorkspace

    # DD-3 / INV-3 site 1 (fail loud, NOT silent primary fallback): a coordination-
    # routed mission with no resolvable mission_id cannot reach its coord surface.
    mid8 = _resolve_mid8(repo_root, mission_slug)
    if mid8 is None:
        raise CoordWorktreeResolutionError(
            f"Coordination-routed mission {mission_slug!r} has no resolvable "
            f"mission_id (missing / short / corrupt meta.json); its coordination "
            f"worktree cannot be materialised. Refusing to fall back to the primary "
            f"checkout, which would silently misroute a coordination-kind artifact "
            f"(INV-3). Repair meta.json's mission_id and retry."
        )

    # DD-3 / INV-3 site 2 (fail loud): a coord-worktree resolution failure under a
    # coordination-routed mission is a corrupt state, not a primary-fallback cue.
    try:
        coord_wt = CoordinationWorkspace.resolve(repo_root, mission_slug, mid8)
    except Exception as exc:
        raise CoordWorktreeResolutionError(
            f"Coordination worktree resolution failed for mission {mission_slug!r} "
            f"(mid8={mid8!r}): {exc}. Refusing to fall back to the primary checkout, "
            f"which would silently misroute a coordination-kind artifact (INV-3)."
        ) from exc

    coord_paths = _stage_artifacts_in_coord_worktree(
        list(files),
        coord_wt,
        repo_root,
        primary_paths_created_this_invocation=primary_paths_created_this_invocation,
    )
    return coord_wt, tuple(coord_paths)


def _resolve_mid8(repo_root: Path, mission_slug: str) -> str | None:
    """Load meta.json and derive mid8 for worktree resolution."""
    try:
        from mission_runtime import MissionArtifactKind, placement_seam
        from specify_cli.lanes.branch_naming import resolve_mid8
        from specify_cli.mission_metadata import load_meta
        from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

        feature_dir = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        meta = load_meta(feature_dir, allow_missing=True, on_malformed="none")
        raw_mid = meta.get("mission_id") if meta else None
        if not isinstance(raw_mid, str) or len(raw_mid) < 8:
            return None
        result: str | None = resolve_mid8(mission_slug, mission_id=raw_mid)
        return result
    except MissionSelectorAmbiguous:
        # C-002: propagate ambiguity — do not swallow it silently.
        raise
    except Exception:
        return None


def _is_directly_in_worktree(path: Path, worktree: Path) -> bool:
    """True when *path* lives in *worktree* itself, not in a worktree nested inside it."""
    from specify_cli.coordination.surface_resolver import is_under_worktrees_segment

    try:
        rel = path.resolve().relative_to(worktree.resolve())
    except ValueError:
        return False
    return not is_under_worktrees_segment(rel)


def _stage_artifacts_in_coord_worktree(
    files: list[Path],
    coord_worktree: Path,
    repo_root: Path,
    *,
    primary_paths_created_this_invocation: frozenset[Path] | None = None,
) -> list[Path]:
    """Copy artifacts from the primary checkout to the coordination worktree.

    This IS the canonical staging helper (#2056 WP08 / T033 collapsed the former
    ``mission.py::_stage_finalize_artifacts_in_coord_worktree`` near-duplicate into
    this one function; the old name survives only as a backward-compat alias at the
    bottom of this module). Behaviour:
    - Skipping ``MissionArtifactKind.STATUS_STATE`` files (WP13 retired the former
      ``COORD_OWNED_STATUS_FILES`` frozenset onto this single-source kind check) —
      STATUS-partition files authored directly in the coord worktree, never copied
      from a stale primary (#1589).
    - Skipping the re-homed ``analysis-report.md`` (FR-003) — see the loop body.
    - Skipping worktrees-nested paths (#FR-035).
    - Residue cleanup for ``primary_paths_created_this_invocation`` (R6 / #1814).
    """
    from specify_cli.coordination.surface_resolver import is_under_worktrees_segment

    coord_files: list[Path] = []
    staged_sources: list[tuple[Path, Path]] = []

    for src in files:
        rel = src.relative_to(repo_root)
        # A path under ``.worktrees/`` is never copied: it is committed in place when
        # it lives in THIS coordination worktree, and dropped otherwise. This runs
        # before the STATUS_STATE skip below, whose purpose is to never copy a stale
        # PRIMARY status log over the coord one; a log already authored in the coord
        # worktree needs no copy, and dropping it reported ``no_op_already_committed``
        # while the log stayed uncommitted there (#5353). The re-homed
        # ``analysis-report.md`` stays skipped (FR-003, below).
        if is_under_worktrees_segment(rel):
            if src.name != _ANALYSIS_REPORT_FILENAME and _is_directly_in_worktree(src, coord_worktree):
                coord_files.append(src)
            continue
        # WP13 (IC-07c): single-source through the canonical file→kind classifier
        # instead of a locally-duplicated ``{"status.events.jsonl", "status.json"}``
        # literal. Narrow ON PURPOSE (STATUS_STATE only, not the full
        # ``is_coord_residue_churn`` union): ``acceptance-matrix.json`` /
        # ``issue-matrix.md`` (``ACCEPTANCE_MATRIX`` / ``ISSUE_MATRIX``) STAY COORD
        # and must continue to be staged below — only the status log/snapshot are
        # authored directly in the coord worktree and must never be copied from a
        # stale primary.
        if kind_for_mission_file(rel) is MissionArtifactKind.STATUS_STATE:
            continue
        # FR-003 (coord-commit-integrity): ``analysis-report.md`` was re-homed
        # COORD→PRIMARY — it lands on the primary ``target_branch`` and is NEVER
        # a second copy on the coordination worktree. Skip its copy2 staging path
        # (mirroring the STATUS_STATE skip above) so a coord commit that
        # happens to sweep it makes no coord residue. ``acceptance-matrix.json`` /
        # ``issue-matrix.md`` STAY COORD and continue to be staged below.
        #
        # NOTE (coord-commit-integrity SURFACE A #2, DEFERRED): the operator asked
        # to generalise this to a by-construction
        # ``is_primary_artifact_kind(kind_for_mission_file(src))`` skip. That is
        # UNSAFE as specified: this helper legitimately stages OTHER PRIMARY-kind
        # planning artifacts (``tasks.md`` / ``lanes.json``) into the coord worktree
        # for a combined commit — a pinned contract
        # (``test_finalize_coord_staging.py`` / ``test_finalize_clobber_e2e.py``).
        # There is no partition-derived distinction between ``analysis-report.md``
        # (must-skip, re-homed) and ``tasks.md`` (must-stage), so a blanket
        # primary-kind skip regresses those tests. Closing the "next re-home
        # silently regresses" class requires first retiring the tasks.md/lanes.json
        # → coord staging (a separate finalize-flow change); until then this stays
        # the narrow, behaviour-correct analysis-report skip.
        if src.name == _ANALYSIS_REPORT_FILENAME:
            continue
        dst = coord_worktree / rel
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            staged_sources.append((src, dst))
        coord_files.append(dst)

    if primary_paths_created_this_invocation:
        for src, dst in staged_sources:
            if src not in primary_paths_created_this_invocation:
                continue
            if not src.exists() or not dst.exists():
                continue
            try:
                if src.read_bytes() != dst.read_bytes():
                    logger.warning(
                        "commit_router: residue cleanup skipped %s: primary copy diverged",
                        src.relative_to(repo_root),
                    )
                    continue
                src.unlink()
            except OSError as exc:
                logger.warning(
                    "commit_router: residue cleanup failed for %s: %s",
                    src.relative_to(repo_root),
                    exc,
                )

    return coord_files


# ---------------------------------------------------------------------------
# Planning-commit residue (relocated from mission.py — #2056 WP08 / T032).
#
# These were the last planning-commit primitives living in the ``mission`` god
# module. ``tasks.py``'s map-requirements + planning auto-commit paths consume
# them (LIVE on this base), so they are RELOCATED here — the canonical commit
# router — not deleted. ``mission.py`` re-exports them as deliberate shims so
# historical ``mission.<name>`` patch targets keep resolving (WP09 owns the
# final shim sweep). INV-8: one-way — commit_router never imports the mission
# seams; the ``CoordinationWorkspace`` / ``resolve_mid8`` reads use the same
# lower-layer authorities the existing router helpers already use.
# ---------------------------------------------------------------------------


def _resolve_planning_placement(repo_root: Path, mission_slug: str, *, kind: MissionArtifactKind) -> CommitTarget:
    """Resolve the single planning-phase :class:`CommitTarget` for ``mission_slug``.

    WP05 / FR-003 / C-GUARD-3a (#1784): the ONE destination authority for every
    planning-phase commit (spec / plan / tasks / finalize-tasks / doc-mission
    bookkeeping). Routes through ``mission_runtime.resolve_placement_only`` — the
    WP-less projection over the SAME resolution authority the full resolver uses
    — so no planning commit path re-derives a destination from ``meta.json`` or
    the current git checkout (the catch-22 root). The placement is CWD-invariant
    and topology-correct (coordination / flattened / primary).

    ``kind`` is REQUIRED (write-surface-coherence WP02): the projection is now
    kind-aware, so the caller MUST name the artifact kind it is placing — a
    primary kind lands on the primary target branch for every topology.
    """
    return resolve_placement_only(repo_root, mission_slug, kind=kind)


def _resolve_commit_worktree_for_kind(
    repo_root: Path,
    mission_slug: str,
    paths: tuple[Path, ...],
    *,
    kind: MissionArtifactKind = MissionArtifactKind.TASKS_INDEX,
    primary_paths_created_this_invocation: frozenset[Path] | None = None,
) -> tuple[Path, tuple[Path, ...]]:
    """Resolve the worktree a ``kind``-aware commit lands in for ``mission_slug``.

    coord-primary-partition-lock WP04 / T019: renamed from the stale
    ``_planning_commit_worktree`` — the old name lied post-D2 (planning never
    transits coordination since write-surface-coherence WP02/WP03), yet the
    helper is genuinely kind-aware and reachable for COORDINATION-partition
    kinds too (its default ``kind=TASKS_INDEX`` just happens to be the primary
    kind every LIVE planning caller passes). The
    ``_planning_commit_worktree`` alias below is preserved for the historical
    ``mission.<name>`` re-export shim and the existing unit-test surface
    (DECISION: rename-with-alias, not a hard cutover — the blast radius of the
    old name spans ``mission.py``'s deliberate shim re-export plus several
    test modules outside this WP's ownership).

    WP05: ``safe_commit`` requires ``worktree_root`` HEAD to equal the
    destination ref. When :func:`routes_through_coordination` holds for the
    STORED topology the destination is the coordination branch, which is checked
    out in the per-mission coordination worktree — so the commit must run there
    (and the artifacts, written to the main checkout, are copied across for
    staging, skipping coord-owned status files, #1589). For a coord-less topology
    the destination is already HEAD of the main checkout, so it is used directly.

    write-surface-coherence WP03 / T014: this helper is partition-aware. The
    coord-staging body runs ONLY for coordination-partition artifact kinds; a
    PRIMARY kind (the default — every caller here commits planning artifacts)
    resolves to the primary ``target_branch`` for every topology, so it commits
    directly from the primary checkout with NO coord transit (FR-003 / C-005).
    This is the genuine invariant guard (T019): a PRIMARY-partition kind must
    NEVER reach the coord-staging body below — deleting or weakening this
    early return re-opens the planning→coord mis-route the partition exists to
    forbid, so it is preserved verbatim across the rename.

    #2056 WP08 / T033: the coord-staging body reuses the router's existing
    ``_resolve_mid8`` + ``CoordinationWorkspace`` + ``_stage_artifacts_in_coord_
    worktree`` primitives — the reconciliation of the former mission.py
    ``_stage_finalize_artifacts_in_coord_worktree`` near-duplicate into the
    single canonical staging helper.

    Returns ``(worktree_root, paths_to_commit)``.

    Raises:
        CoordWorktreeResolutionError: a coordination-routed (coord-partition-kind)
            commit has an unresolvable ``mission_id`` or its coordination worktree
            failed to resolve — fail loud rather than misroute to primary (DD-3 /
            INV-3, coord-commit-surface-authority WP04).
    """
    # DD-3 fail-loud ledger (coord-commit-surface-authority WP04) — the TWO
    # early-returns below are INTENTIONAL primary-routing (a primary-kind commit,
    # and a coord-less topology, both legitimately committing from the primary
    # checkout), NOT silent misroutes: they are EXCLUDED from hardening on purpose.
    # The two coord-staging fallbacks further down (unresolvable mid8; coord-worktree
    # resolution failure) ARE misroutes and are hardened to fail loud (zero
    # exclusions among the corrupt-state sites).
    #
    # PRIMARY kinds never transit coordination — commit directly from the primary
    # checkout (write-surface-coherence WP03 / T014). The coord-staging body below
    # is reached only by coordination-partition kinds. (T019: the PRIMARY-kind
    # invariant guard — kept verbatim, never deleted, across the rename.)
    if is_primary_artifact_kind(kind):
        return repo_root, paths  # INTENTIONAL primary routing (excluded from DD-3 hardening)

    if not routes_through_coordination(resolve_topology(repo_root, mission_slug)):
        return repo_root, paths  # INTENTIONAL primary routing (coord-less topology)

    # DD-3 / INV-3 site 3 (fail loud): a coordination-routed, coord-partition kind
    # with no resolvable mission_id is a corrupt state, not a primary-fallback cue.
    mid8 = _resolve_mid8(repo_root, mission_slug)
    if mid8 is None:
        raise CoordWorktreeResolutionError(
            f"Coordination-routed mission {mission_slug!r} has no resolvable "
            f"mission_id (missing / short / corrupt meta.json); its coordination "
            f"worktree cannot be materialised. Refusing to fall back to the primary "
            f"checkout, which would silently misroute a coordination-kind artifact "
            f"(INV-3). Repair meta.json's mission_id and retry."
        )

    from specify_cli.coordination.workspace import CoordinationWorkspace

    # Materialize the coordination worktree on demand (the coord branch already
    # exists from ``mission create``). This is the catch-22 killer: the planning
    # commit ALWAYS reaches its resolved coordination placement instead of
    # falling back to the protected main checkout and tripping the guard.
    #
    # DD-3 / INV-3 site 4 (fail loud): a coord-worktree resolution failure under a
    # coordination-routed mission is a corrupt state — the former C-004
    # strangler-safety primary fallback silently misrouted the artifact (INV-3).
    try:
        coord_wt = CoordinationWorkspace.resolve(repo_root, mission_slug, mid8)
    except Exception as exc:
        raise CoordWorktreeResolutionError(
            f"Coordination worktree resolution failed for mission {mission_slug!r} "
            f"(mid8={mid8!r}): {exc}. Refusing to fall back to the primary checkout, "
            f"which would silently misroute a coordination-kind artifact (INV-3)."
        ) from exc

    coord_paths = _stage_artifacts_in_coord_worktree(
        list(paths),
        coord_wt,
        repo_root,
        primary_paths_created_this_invocation=primary_paths_created_this_invocation,
    )
    return coord_wt, tuple(coord_paths)


# Backwards-compatible alias (T019): the historical name. ``mission.py`` still
# re-exports ``_planning_commit_worktree as _planning_commit_worktree`` (a
# deliberate shim for historical ``mission.<name>`` patch targets — WP09 owns
# the final shim sweep) and several existing unit tests call
# ``commit_router._planning_commit_worktree`` / ``commit_router_mod.
# _planning_commit_worktree`` directly. Aliasing here keeps every one of those
# resolving without touching files outside this WP's ownership.
_planning_commit_worktree = _resolve_commit_worktree_for_kind


# Backwards-compatible alias: the former mission.py name for the staging helper.
# #2056 WP08 / T033 collapsed the near-duplicate into the canonical router
# helper; this alias preserves the historical
# ``_stage_finalize_artifacts_in_coord_worktree`` symbol for the existing
# coord-staging unit tests (and the ``mission`` re-export shim) without forking
# a second copy.
_stage_finalize_artifacts_in_coord_worktree = _stage_artifacts_in_coord_worktree


def _any_path_absent(paths: tuple[Path, ...]) -> bool:
    """Return True iff any path in *paths* does not exist on disk."""
    return any(not path.exists() for path in paths)


def _paths_uncommitted_in_primary(repo_root: Path, files: tuple[Path, ...]) -> bool:
    """Return True iff any source path is present on disk under *repo_root* AND
    carries uncommitted content (untracked or modified) in the primary checkout.

    #2739 B16: the wrong-surface discriminator for an empty coord commit. A file
    the operator wrote into the PRIMARY tree that then routed to the coordination
    partition (where staging skipped it) leaves the primary tree dirty and lands
    nowhere — ``git status --porcelain`` on the path is non-empty. A file that was
    already committed (genuine no-op) reports clean, and a coord-authored artifact
    living in a linked worktree is not tracked by the primary checkout, so both
    correctly return ``False``.
    """
    for path in files:
        if not path.exists():
            continue
        try:
            rel = path.resolve().relative_to(repo_root.resolve())
        except ValueError:
            continue
        # Guard (FR-013): an unreadable status must not read as "clean" and let a
        # wrong-surface no-op pass as benign, so ``GitCommandError`` propagates.
        if status_entries(repo_root, pathspecs=(rel.as_posix(),), untracked=None):
            return True
    return False


def _is_empty_changeset_error(exc: RuntimeError) -> bool:
    # Match ONLY the genuine empty-changeset signal safe_commit now raises with a
    # distinct message. A generic "safe_commit: git commit failed …" (a rejecting
    # pre-commit hook, a lock error, etc.) must fall through to a real error,
    # never be silently reported as "unchanged".
    return "safe_commit: nothing to commit" in str(exc)


def _try_advance_ref(
    repo_root: Path,
    primary_branch: str,
    coord_worktree: Path,
    *,
    mission_slug: str | None = None,
) -> None:
    """Best-effort fast-forward of *primary_branch* to the coord HEAD (#1878).

    ``advance_branch_ref`` advances the ref to a *SHA* (it does not accept a
    worktree path), so resolve the coordination worktree's HEAD here first.
    Toolchain-generated churn (coordination status residue, spec-kitty's own
    bookkeeping) on the primary checkout is legitimate after a coord-branch
    write, so exclude it from the dirty gate via the single canonical churn
    owner (#1878 / #2795 / FR-012 / WP13-IC-07c) — mirrors the merge-pipeline
    call sites.
    """
    try:
        import functools

        from specify_cli.coordination.coherence import is_toolchain_generated_churn
        from specify_cli.git.ref_advance import advance_branch_ref

        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(coord_worktree),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        advance_branch_ref(
            repo_root,
            primary_branch,
            head,
            is_residue=functools.partial(is_toolchain_generated_churn, mission_slug=mission_slug),
        )
    except Exception:  # noqa: BLE001  # best-effort only
        logger.debug(
            "commit_router: _try_advance_ref best-effort advance failed silently",
        )


__all__ = [
    "CommitRouterResult",
    "commit_for_mission",
]
