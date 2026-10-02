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
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal, Protocol, runtime_checkable

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
from specify_cli.coordination import commit_outcome
from specify_cli.coordination.coherence import is_coord_residue_churn
from specify_cli.coordination.commit_outcome import PathFate, SurfaceOutcome
from specify_cli.coordination.surface_authority import Refuse, resolve_surface_authority
from specify_cli.git import safe_commit
from specify_cli.status import FeatureStatusLockTimeoutError

if TYPE_CHECKING:
    # WP05 (T027): only needed for the ``_translate_to_owning_surface`` /
    # ``_resolve_owning_write_dir`` type annotations -- resolving the real
    # ``write_dir`` seam happens via a lazy import inside the function that
    # needs it (this module's existing style for ``coordination.*`` seams).
    from mission_runtime import WriteLocation


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
#
# WP05 (T024 CORRECTION, brownfield scout round 3): these four aliases now
# import their VALUE from ``commit_outcome`` — the single canonical owner —
# instead of each restating the same string (the duplicate previously also
# lived in ``surface_authority.py``). This file keeps its own private names
# (``_STATUS_COMMITTED`` etc.) so none of its 8+ existing construction sites
# need renaming.
_STATUS_COMMITTED: Final = commit_outcome.STATUS_COMMITTED
_STATUS_UNCHANGED: Final = commit_outcome.STATUS_UNCHANGED
_STATUS_NO_OP_WRONG_SURFACE: Final = commit_outcome.STATUS_NO_OP_WRONG_SURFACE
_STATUS_ERROR: Final = commit_outcome.STATUS_ERROR

# FR-003 (coord-commit-integrity): the re-homed PRIMARY analysis-report basename.
# Named once so the coord-staging skip (mirroring the STATUS_STATE-kind skip,
# WP13-retired ``COORD_OWNED_STATUS_FILES``) does not restate the raw literal.
_ANALYSIS_REPORT_FILENAME: Final = "analysis-report.md"

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
# WP05: values owned by ``commit_outcome`` (single owner — see above).
_REASON_ALREADY_COMMITTED: Final = commit_outcome.REASON_ALREADY_COMMITTED
_REASON_NO_CHANGES: Final = commit_outcome.REASON_NO_CHANGES

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
    #: WP05 (FR-007, contracts/commit-outcome.md rule 1): one
    #: :class:`~specify_cli.coordination.commit_outcome.SurfaceOutcome` per
    #: partition group this request touched, ordered PRIMARY then
    #: coordination. Additive — defaults empty for every pre-existing caller
    #: and construction site this WP did not touch. The four legacy fields
    #: above keep today's CALLER-partition projection (rule 4); ``surfaces``
    #: is the only place a caller can see BOTH groups' outcomes when a batch
    #: was split (:func:`_group_files_by_partition`). An early argument-error
    #: return (mismatched ``expected_parent_sha``/``expected_path_bytes``, or
    #: more than one resolved group with an ``expected_parent_sha``) carries
    #: ``surfaces=()`` — it is a caller contract violation, never a surface
    #: outcome.
    surfaces: tuple[SurfaceOutcome, ...] = ()


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
    primary_ref: str | None = None,
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
        target_branch: Short TARGET branch name (the sense: the mission's own
                     primary/target ref, not the repository-root checkout).
                     R12 / FR-008 (#5440, WP05): this no longer drives a
                     post-commit fast-forward — that best-effort advance
                     (``_try_advance_ref``, WP09 / FR-010 / #1878) is RETIRED,
                     because it silently carried coordination-only commits
                     onto the target once the target became an ancestor of
                     the coordination tip (post-create-seed, WP06). It still
                     feeds the owned-placement early returns. It does not
                     select the commit ref: ``spec-commit --target-branch``
                     and write-seam callers keep that previous meaning.
        primary_ref: Accept-only PRIMARY commit ref (decision
                     ``plan.design.accept-primary-leg-ref``). When set, the
                     PRIMARY group commits on this branch — the unprotected
                     HEAD the acceptance-metadata commit used. Coordination
                     groups ignore it. Other callers leave it unset, so an
                     unprotected value cannot bypass a protected stored target.
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
            owned=owned,
            expected_parent_sha=expected_parent_sha,
            expected_path_bytes=expected_path_bytes,
            primary_ref_override=primary_ref,
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
            primary_ref_override=primary_ref,
        )
        for group_kind, group_files in groups
    ]
    return _log_split_commit_outcome(_merge_group_results(results, groups, kind))


def _log_split_commit_outcome(result: CommitRouterResult) -> CommitRouterResult:
    """Log a split (multi-group) commit's full per-surface outcome, then return it unchanged.

    A split commit's legacy top-level fields describe only the CALLER-partition
    group (:func:`_merge_group_results` priority rules); the OTHER group's
    outcome would otherwise reach only a caller that itself inspects
    ``surfaces``. Rendering through the canonical trio here gives every reader
    a full per-surface trail in the log regardless of whether that caller has
    been migrated onto ``surfaces`` yet (WP07-WP16) — a genuine production use
    of :func:`~specify_cli.coordination.commit_outcome.render_commit_outcome`
    and :func:`~specify_cli.coordination.commit_outcome.commit_outcome_exit_code`
    inside this WP, per the "prefer zero-red" guidance for the dead-symbol gate.
    """
    level = logging.WARNING if commit_outcome.commit_outcome_exit_code(result) != 0 else logging.DEBUG
    for line in commit_outcome.render_commit_outcome(result):
        logger.log(level, "commit_router: %s", line)
    logger.debug("commit_router: outcome payload %s", commit_outcome.commit_outcome_payload(result))
    return result


def _apply_primary_ref_override(placement: CommitTarget, override: str | None, *, use_coord: bool) -> CommitTarget:
    """Retarget a primary group onto an explicit ref.

    Decision ``plan.design.accept-primary-leg-ref``: accept's PRIMARY residual
    leg commits on the same branch as the acceptance-metadata commit. A
    coordination group keeps its resolved ref. ``None`` and an identical ref
    leave placement unchanged, so a caller passing the stored target is a no-op.
    """
    if use_coord or not override or override == placement.ref:
        return placement
    return replace(placement, ref=override)


def _resolve_group_placement(
    repo_root: Path,
    mission_slug: str,
    policy: _ProtectionPolicyProtocol,
    *,
    kind: MissionArtifactKind,
    owned: OwnedCheckout | None,
    primary_ref_override: str | None = None,
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
    placement = _apply_primary_ref_override(placement, primary_ref_override, use_coord=use_coord)
    if not use_coord and primary_ref_override:
        primary_target = placement.ref

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
    surface_name: Literal["primary", "coordination"] = "coordination" if use_coord else "primary"
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
        diagnostic = (
            f"Artifact(s) written to the primary checkout routed to the "
            f"coordination placement ({placement.ref}) where nothing was "
            f"staged; the commit would no-op against the wrong surface and "
            f"the artifact remains uncommitted in the primary tree. Commit "
            f"it to its own (primary) surface instead."
        )
        refused = tuple(PathFate(path=_relpath(repo_root, f), reason=commit_outcome.WRONG_SURFACE) for f in files)
        return CommitRouterResult(
            status=_STATUS_NO_OP_WRONG_SURFACE,
            placement_ref=placement.ref,
            diagnostic=diagnostic,
            surfaces=(SurfaceOutcome(surface=surface_name, branch=placement.ref, status="refused", commit_hash=None, refused=refused, diagnostic=diagnostic),),
        )
    # All artifacts already committed (or none present) — genuine no-op.
    skipped = tuple(PathFate(path=_relpath(repo_root, f), reason=_REASON_ALREADY_COMMITTED) for f in files)
    return CommitRouterResult(
        status=_STATUS_UNCHANGED,
        placement_ref=placement.ref,
        reason=_REASON_ALREADY_COMMITTED,
        surfaces=(SurfaceOutcome(surface=surface_name, branch=placement.ref, status="unchanged", commit_hash=None, skipped=skipped),),
    )


def _refine_unchanged_for_root_checkout_dirt(
    result: CommitRouterResult,
    repo_root: Path,
    files: tuple[Path, ...],
    *,
    use_coord: bool,
    surface_name: Literal["primary", "coordination"],
    placement: CommitTarget,
) -> CommitRouterResult:
    """Re-classify a genuine ``unchanged`` owning-surface commit when a root copy is ALSO dirty (T028 contract rule 3).

    T027 translates a root-checkout COORD-record path to its owning
    (coordination) copy BEFORE this group ever reaches :func:`_safe_commit_group`
    -- so ``commit_paths`` already names the OWNING path, and an ``unchanged``
    result here means the OWNING copy is genuinely clean. That is not the same
    fact as "the caller's root-checkout copy is clean": an operator who edited
    the root copy directly (never committed) would otherwise see a bare
    ``no_op_no_changes`` with no hint that their edit never reaches the target.
    When any of the ORIGINAL *files* this group was asked to commit is ALSO
    dirty in the PRIMARY checkout, this swaps the generic no-op reason for the
    named ``COORD_RECORD_IN_ROOT_CHECKOUT`` skip for exactly those paths — the
    owning-surface verdict (``unchanged``) is unchanged, only the per-path
    reason becomes actionable.
    """
    if result.status != _STATUS_UNCHANGED or not use_coord:
        return result
    dirty_root_files = _dirty_paths_in_checkout(repo_root, files)
    if not dirty_root_files:
        return result
    dirty_rel = {_relpath(repo_root, f) for f in dirty_root_files}
    skipped = tuple(
        PathFate(path=path, reason=commit_outcome.COORD_RECORD_IN_ROOT_CHECKOUT if path in dirty_rel else _REASON_ALREADY_COMMITTED)
        for path in sorted({_relpath(repo_root, f) for f in files})
    )
    refined_surface = SurfaceOutcome(surface=surface_name, branch=placement.ref, status="unchanged", commit_hash=None, skipped=skipped)
    return replace(result, surfaces=(refined_surface,))


def _commit_partition_group(
    repo_root: Path,
    mission_slug: str,
    files: tuple[Path, ...],
    message: str,
    policy: _ProtectionPolicyProtocol,
    *,
    kind: MissionArtifactKind,
    primary_paths_created_this_invocation: frozenset[Path] | None = None,
    owned: OwnedCheckout | None = None,
    expected_parent_sha: str | None = None,
    expected_path_bytes: Mapping[Path, bytes] | None = None,
    primary_ref_override: str | None = None,
) -> CommitRouterResult:
    """Commit ONE single-partition file group to its resolved placement.

    This is the pre-WP01 body of ``commit_for_mission`` verbatim, extracted so
    the public entry point can invoke it once per partition group (T002/T004).
    Every file in ``files`` MUST already belong to the SAME partition as
    ``kind`` — :func:`_group_files_by_partition` guarantees this; this helper
    does not re-validate it (single responsibility: resolve + commit one group).
    """
    placement, use_coord, refusal = _resolve_group_placement(
        repo_root,
        mission_slug,
        policy,
        kind=kind,
        owned=owned,
        primary_ref_override=primary_ref_override,
    )
    # FR-007 (contract rule 1): every return site below names this group's
    # surface -- "coordination" iff this group routes through coordination,
    # else "primary". ``refusal`` can only occur in the ``not use_coord`` arm
    # of ``_resolve_group_placement`` (a protected-PRIMARY refusal), so it is
    # always "primary" there.
    surface_name: Literal["primary", "coordination"] = "coordination" if use_coord else "primary"
    if refusal is not None:
        refused = tuple(PathFate(path=_relpath(repo_root, f), reason=commit_outcome.PROTECTED_BRANCH_REFUSED) for f in files)
        refused_surface = SurfaceOutcome(
            surface=surface_name,
            branch=placement.ref,
            status="refused",
            commit_hash=None,
            refused=refused,
            diagnostic=refusal.diagnostic,
        )
        return replace(refusal, surfaces=(refused_surface,))

    if use_coord:
        try:
            # NOTE (reviewer ruling L1, WP05 cycle 1): ``owned`` is NOT
            # threaded into this call. The real guarantee this arm can never
            # see ``owned is not None`` is ``use_coord = owned is None and
            # routes_through_coordination(topology)`` in
            # ``_resolve_group_placement`` ABOVE -- a gate owned entirely by
            # THIS module, true regardless of which owned topologies a
            # caller is later allowed to request. (``core.owned_mission.
            # LIFECYCLE_OWNED_TOPOLOGIES`` happens to be ``{SINGLE_BRANCH}``
            # today, but that fact lives upstream and already has a wider
            # sibling, ``NEXT_OWNED_TOPOLOGIES`` — including
            # ``LANES_WITH_COORD`` — staged for a future command; citing it
            # here would go stale the day that fact changes, while this
            # module's own gate would not.) Several existing unit fixtures
            # (outside this WP's ownership) stub
            # ``_materialise_coord_worktree`` without an ``owned`` kwarg, so
            # omitting it here (its default stays ``None``) keeps them green
            # — a convenience this gate also happens to provide.
            worktree_root, commit_paths = _materialise_coord_worktree(
                repo_root,
                mission_slug,
                placement,
                files,
                kind=kind,
                primary_paths_created_this_invocation=primary_paths_created_this_invocation,
            )
        except _OwningSurfaceRefused as exc:
            # T029: a named write_dir refusal (PROTECTED_BRANCH_REFUSED /
            # COORDINATION_BRANCH_DELETED / COORDINATION_WORKTREE_UNMATERIALIZED /
            # COORD_SEED_FORK_REFUSED / its siblings / PATH_UNROUTABLE) translating
            # a root-path COORD record to its owning surface — never swallowed,
            # always a named refused surfaces[*] entry.
            refused = (PathFate(path=exc.path, reason=exc.reason),)
            refused_surface = SurfaceOutcome(
                surface=surface_name,
                branch=placement.ref,
                status="refused",
                commit_hash=None,
                refused=refused,
                diagnostic=exc.diagnostic,
            )
            return CommitRouterResult(
                status=_STATUS_ERROR,
                placement_ref=placement.ref,
                diagnostic=exc.diagnostic,
                surfaces=(refused_surface,),
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
        refused = tuple(PathFate(path=_relpath(repo_root, p), reason=commit_outcome.WRONG_SURFACE) for p in commit_paths if not p.exists())
        return CommitRouterResult(
            status=_STATUS_NO_OP_WRONG_SURFACE,
            placement_ref=placement.ref,
            diagnostic=diagnostic,
            surfaces=(SurfaceOutcome(surface=surface_name, branch=placement.ref, status="refused", commit_hash=None, refused=refused, diagnostic=diagnostic),),
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
        return _refine_unchanged_for_root_checkout_dirt(commit_result, repo_root, files, use_coord=use_coord, surface_name=surface_name, placement=placement)

    commit_hash: str | None = None
    if commit_result is not None and hasattr(commit_result, "sha"):
        commit_hash = commit_result.sha

    # R12 / FR-008 (#5440, coord-artifact-single-home-01M3V4BE WP05): the
    # former WP09 / FR-010 (#1878) best-effort post-commit ff-advance of
    # ``target_branch`` to the coordination HEAD is RETIRED. After /spec-kitty.
    # create seeds the coordination branch from the target (WP06), the target
    # is already an ancestor of the coordination tip, so a fast-forward there
    # would silently carry every coordination-only (STATUS/bookkeeping) commit
    # onto the target -- re-mixing the two surfaces the partition exists to
    # keep apart. ``_try_advance_ref`` is deleted outright; a coordination
    # commit now advances ONLY the coordination branch, never the target.
    committed = tuple(_relpath(repo_root, p) for p in commit_paths)
    return CommitRouterResult(
        status=_STATUS_COMMITTED,
        placement_ref=placement.ref,
        commit_hash=commit_hash,
        commit_hashes=((placement.ref, commit_hash),) if commit_hash else (),
        diagnostic=getattr(commit_result, "diagnostic", None),
        surfaces=(SurfaceOutcome(surface=surface_name, branch=placement.ref, status="committed", commit_hash=commit_hash, committed=committed),),
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


def _safe_commit_error_result(
    repo_root: Path,
    placement: CommitTarget,
    surface_name: Literal["primary", "coordination"],
    commit_paths: tuple[Path, ...],
    *,
    reason: str,
    diagnostic: str,
) -> CommitRouterResult:
    """Build the ``error`` :class:`CommitRouterResult` a :func:`_safe_commit_group` except-arm returns (WP05 T025/T029)."""
    refused = tuple(PathFate(path=_relpath(repo_root, p), reason=reason) for p in commit_paths)
    return CommitRouterResult(
        status=_STATUS_ERROR,
        placement_ref=placement.ref,
        diagnostic=diagnostic,
        surfaces=(SurfaceOutcome(surface=surface_name, branch=placement.ref, status="error", commit_hash=None, refused=refused, diagnostic=diagnostic),),
    )


def _safe_commit_unchanged_result(
    repo_root: Path,
    placement: CommitTarget,
    surface_name: Literal["primary", "coordination"],
    commit_paths: tuple[Path, ...],
) -> CommitRouterResult:
    """Build the ``unchanged`` / ``no_op_no_changes`` :class:`CommitRouterResult` an empty changeset yields (WP05 T025)."""
    skipped = tuple(PathFate(path=_relpath(repo_root, p), reason=_REASON_NO_CHANGES) for p in commit_paths)
    return CommitRouterResult(
        status=_STATUS_UNCHANGED,
        placement_ref=placement.ref,
        reason=_REASON_NO_CHANGES,
        surfaces=(SurfaceOutcome(surface=surface_name, branch=placement.ref, status="unchanged", commit_hash=None, skipped=skipped),),
    )


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
    caller reports it like any other failed commit. WP05 (T029): the lock
    timeout's ``surfaces[*].refused`` reason is the lock's own
    ``error_code`` (``STATUS_LOCK_HELD``, WP03) rather than a generic string.
    """
    surface_name: Literal["primary", "coordination"] = "coordination" if use_coord else "primary"
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
        reason = getattr(exc, "error_code", None) or commit_outcome.STATUS_LOCK_HELD
        return _safe_commit_error_result(repo_root, placement, surface_name, commit_paths, reason=reason, diagnostic=str(exc))
    except subprocess.CalledProcessError as exc:
        stderr = getattr(exc, "stderr", "") or ""
        if "nothing to commit" in stderr or "nothing added to commit" in stderr:
            return _safe_commit_unchanged_result(repo_root, placement, surface_name, commit_paths)
        return _safe_commit_error_result(repo_root, placement, surface_name, commit_paths, reason=_STATUS_ERROR, diagnostic=str(exc))
    except RuntimeError as exc:
        if _is_empty_changeset_error(exc):
            return _safe_commit_unchanged_result(repo_root, placement, surface_name, commit_paths)
        return _safe_commit_error_result(repo_root, placement, surface_name, commit_paths, reason=_STATUS_ERROR, diagnostic=str(exc))


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


def partition_for_mission_path(
    repo_root: Path,
    mission_slug: str,
    path: Path,
    *,
    owned: OwnedCheckout | None = None,
) -> Literal["primary", "coordination"]:
    """The per-path partition verdict :func:`_group_files_by_partition` uses (WP05 T025, P-M5).

    Re-added to ``__all__`` by WP16 (coord-artifact-single-home-01M3V4BE,
    carried forward from WP05's reviewer ruling B3): WP16's accept dirty gate
    (``acceptance/__init__.py::_filter_coordination_residue``) is the first
    cross-module caller this symbol needed, so it now satisfies the
    symbol-level dead-code gate's "caller outside the declaring module"
    requirement (``tests/architectural/test_no_dead_symbols.py``) and is
    re-exported per the gate's sanctioned fix option 2.

    :func:`_group_files_by_partition` calls this function too (not a parallel
    copy); their verdicts can never drift apart.

    ``repo_root`` / ``owned`` are accepted for interface symmetry with this
    module's other kind-aware public helpers, but are not consulted: the
    underlying residue classifier,
    :func:`~specify_cli.coordination.coherence.is_coord_residue_churn`, is
    deliberately called the SAME topology-blind way
    :func:`_group_files_by_partition` has always called it (no ``topology``
    argument) — passing one here would risk a verdict that disagrees with the
    router's own grouping, the exact drift this predicate exists to prevent.
    A caller that needs a topology-aware (e.g. destructive dirty-gate) verdict
    calls :func:`~specify_cli.coordination.coherence.is_coord_residue_churn`
    directly with its own resolved topology, per that function's own
    documented requirement.
    """
    del repo_root, owned  # interface symmetry only (see docstring)
    return "coordination" if is_coord_residue_churn(path, mission_slug=mission_slug) else "primary"


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
        if partition_for_mission_path(repo_root, mission_slug, file) == "coordination":
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

    WP05 (FR-007 contract rule 1): ``surfaces`` is likewise ALWAYS the union of
    every group's own ``surfaces`` entry (each group carries exactly one, from
    :func:`_commit_partition_group`), ordered PRIMARY then coordination
    (``groups``/``results`` are already in that order — see
    :func:`_group_files_by_partition`). This holds on EVERY return path below,
    including the error early-return: masking a coordination group's refusal
    behind a PRIMARY group's "committed" result is exactly the defect FR-007
    forbids (a caller must see BOTH groups' outcomes via ``surfaces`` even when
    the legacy top-level fields still select only one).
    """
    all_surfaces = tuple(surface for result in results for surface in result.surfaces)
    for result in results:
        if result.status == _STATUS_ERROR:
            return replace(result, surfaces=all_surfaces)

    all_commit_hashes = tuple(pair for result in results for pair in result.commit_hashes)

    caller_is_primary = is_primary_artifact_kind(caller_kind)
    for (group_kind, _group_files), result in zip(groups, results, strict=True):
        if is_primary_artifact_kind(group_kind) == caller_is_primary:
            return replace(result, commit_hashes=all_commit_hashes, surfaces=all_surfaces)

    return replace(results[0], commit_hashes=all_commit_hashes, surfaces=all_surfaces)


def _resolve_mission_target_branch(repo_root: Path, mission_slug: str) -> str:
    """Resolve the mission's PRIMARY ``target_branch`` ref.

    B1 fix (cycle 2 review, `plan.design.published-status-state-write`):
    delegates to :func:`resolve_placement_only` with a guaranteed PRIMARY-
    partition kind (:data:`_FALLBACK_PRIMARY_KIND`) instead of reading
    ``get_feature_target_branch`` directly. Those two were byte-identical for
    PRE_CONSOLIDATION/CONSOLIDATED phases (the common case, unaffected here),
    but silently DIVERGED for a PUBLISHED (E2) mission: ``resolve_placement_
    only`` redirects a PRIMARY kind to the resolved Primary Branch (D23), while
    a raw ``get_feature_target_branch`` read kept returning the mission's OWN
    (possibly long-deleted) ``target_branch`` literal. ``use_coord``'s own
    ``placement.ref != primary_target`` comparison then spuriously fired TRUE
    for a batch mixing a PRIMARY kind with a COORD kind BOTH redirected to the
    SAME Primary Branch (e.g. retrospect's RETROSPECTIVE+STATUS_STATE batch,
    #5513/#5501) — misrouting the whole group into coordination staging and
    raising ``PrimaryKindReachedCoordStagingError``. Delegating closes the gap
    by construction: this function is now LITERALLY the same authority
    ``placement.ref`` itself came from, so the two can never disagree (no
    split-brain), matching the ONE-shared-predicate requirement this ruling's
    ``PlacementSeam.write_dir`` extension already holds for the write-location
    accessor.
    """
    placement = resolve_placement_only(repo_root, mission_slug, kind=_FALLBACK_PRIMARY_KIND)
    return placement.ref


def _materialise_coord_worktree(
    repo_root: Path,
    mission_slug: str,
    _placement: object,
    files: tuple[Path, ...],
    *,
    kind: MissionArtifactKind,
    primary_paths_created_this_invocation: frozenset[Path] | None = None,
    owned: OwnedCheckout | None = None,
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
        owned: WP05 forward guard (brownfield scout round 3 CORRECTION;
            reviewer ruling L1, WP05 cycle 1): this helper is reached only
            when ``use_coord`` is ``True`` in :func:`_commit_partition_group`,
            and ``use_coord = owned is None and
            routes_through_coordination(topology)`` there — a gate owned
            entirely by THIS module — so it is never actually reached with
            ``owned is not None`` in practice, regardless of which owned
            topologies a caller is allowed to request upstream (see the
            longer note at the ``_materialise_coord_worktree`` call site in
            :func:`_commit_partition_group` for why this cites that gate
            rather than ``core.owned_mission.LIFECYCLE_OWNED_TOPOLOGIES`` —
            that fact already has a wider sibling, ``NEXT_OWNED_TOPOLOGIES``,
            staged for a future command). Accepted and threaded through to
            :func:`_stage_artifacts_in_coord_worktree`'s own ``owned`` purely
            for interface symmetry / forward-compat, never exercised by a
            live caller.

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
        mission_slug=mission_slug,
        owned=owned,
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


class _StagePlan(Enum):
    """Per-path staging disposition for :func:`_stage_artifacts_in_coord_worktree`.

    Six outcomes (binding correction, brownfield scout round 3 — the prompt's
    original four-outcome sketch missed one; WP05 T027 adds a sixth):

    - ``IN_PLACE``: the path already lives directly in THIS coordination
      worktree; it is committed where it sits, never copied.
    - ``SKIP_STATUS_LOG`` / ``SKIP_DECISION_LOG``: a ``STATUS_STATE`` /
      ``DECISION_LOG`` path outside ``.worktrees/`` — an append-only log that
      is NEVER copied from a (possibly stale) primary (#1589). WP05 T027:
      removed from :data:`_STAGE_PLAN_NO_COPY` — the act step now TRANSLATES
      it to its owning (coordination) copy instead of bare-skipping it (D7).
    - ``SKIP_ANALYSIS_REPORT``: the re-homed ``analysis-report.md`` (FR-003) —
      never a second copy on the coordination worktree.
    - ``DROP_FOREIGN_WORKTREE``: a path under ``.worktrees/`` that is NOT
      directly in this worktree (a sibling mission's coord worktree, a worktree
      nested inside this one, or an ``analysis-report.md`` anywhere under
      ``.worktrees/``) — dropped entirely. Kept distinct from the SKIP
      members on purpose: a SKIP is a copy-destination-aware decision the act
      step may translate into a different action, while a foreign worktree
      path has no copy destination to translate.
    - ``COPY``: staged into the coordination worktree at the mirrored relative
      path (the only outcome the caller still derives ``dst`` for) — the
      LEGACY ``shutil.copy2``, unconditional, for every non-log COORD kind
      (``TRACER_FILE`` / ``REVIEW_CYCLE`` / ``ISSUE_MATRIX`` / ``ACCEPTANCE_
      MATRIX``) as well as every PRIMARY-kind artifact this helper legitimately
      stages into a combined commit (``tasks.md`` / ``lanes.json``).

      **Reviewer ruling (WP05 cycle 1, B1, DECISION plan.design.translate-if-
      present-kinds):** an earlier revision of this WP made the act step prefer
      an EXISTING owning (coordination) copy over a fresh one for these four
      kinds ("the owning copy wins"). That silently dropped every writer's
      update for a kind whose writer still writes the ROOT copy (none of
      TRACER_FILE/REVIEW_CYCLE/ISSUE_MATRIX/ACCEPTANCE_MATRIX has migrated to
      ``write_dir`` yet — WP08 migrates REVIEW_CYCLE, WP10 migrates TRACER_FILE
      and ISSUE_MATRIX, WP15 migrates ACCEPTANCE_MATRIX) — a real data-loss
      regression (four integration guards went red:
      ``test_accept_matrix_coord_partition.py``,
      ``test_issue_verdict_coord_legacy_md_preservation.py`` (both),
      ``test_issue_verdict_selfmat_hardening.py::test_materialized_coord_
      verdicts_succeed``). REVERTED: these four kinds keep the unconditional
      legacy overwrite (root always wins, exactly pre-WP05) until each kind's
      writer is migrated to ``write_dir`` in its own WP, which is also where
      the "owning copy wins" switch is re-introduced, one kind at a time.
      STATUS_STATE / DECISION_LOG are UNAFFECTED by this reversion — they are
      genuinely append-only logs with no legacy root writer at all, so T027's
      owning-surface translation (never a copy, see the two SKIP members
      above) is the correct behaviour for them from day one.
    """

    IN_PLACE = "in_place"
    SKIP_STATUS_LOG = "skip_status_log"
    SKIP_DECISION_LOG = "skip_decision_log"
    SKIP_ANALYSIS_REPORT = "skip_analysis_report"
    DROP_FOREIGN_WORKTREE = "drop_foreign_worktree"
    COPY = "copy"


#: WP05 T027: the two append-only-log plans the act step ALWAYS translates
#: (never falls back to a copy, with or without ``mission_slug``).
_STAGE_PLAN_LOGS: Final = frozenset({_StagePlan.SKIP_STATUS_LOG, _StagePlan.SKIP_DECISION_LOG})
_STAGE_PLAN_NO_COPY: Final = frozenset({_StagePlan.DROP_FOREIGN_WORKTREE, _StagePlan.SKIP_ANALYSIS_REPORT})


def _classify_stage_path(src: Path, rel: Path, coord_worktree: Path) -> _StagePlan:
    """Classify how *src* (relative path *rel* under ``repo_root``) must be staged.

    Pure per-path decision extracted from :func:`_stage_artifacts_in_coord_worktree`
    (T005, campsite-clean WP01) — behaviour-preserving, verbatim rationale kept
    inline. The only I/O is ``_is_directly_in_worktree``'s ``.resolve()`` (the
    symlinked-``repo_root`` pin depends on it staying there). WP05 (T027): this
    classifier stays pure and ``mission_slug``-free — it names WHICH plan
    applies, never resolving ``write_dir`` itself (that I/O lives in the act
    step, :func:`_act_on_stage_plan`, per the WP04 reviewer's binding note).
    """
    from specify_cli.coordination.surface_resolver import is_under_worktrees_segment

    # A path under ``.worktrees/`` is never copied: it is committed in place when
    # it lives in THIS coordination worktree, and dropped otherwise. This runs
    # before the log skip below, whose purpose is to never copy a stale
    # PRIMARY log over the coord one; a log already authored in the coord
    # worktree needs no copy, and dropping it reported ``no_op_already_committed``
    # while the log stayed uncommitted there (#5353). An ``analysis-report.md``
    # found under ``.worktrees/`` (this worktree's own, or a foreign one) is
    # always dropped here, never committed in place — its only legitimate home
    # is the primary re-home skip below (FR-003).
    if is_under_worktrees_segment(rel):
        if src.name != _ANALYSIS_REPORT_FILENAME and _is_directly_in_worktree(src, coord_worktree):
            return _StagePlan.IN_PLACE
        return _StagePlan.DROP_FOREIGN_WORKTREE
    # WP13 (IC-07c): single-source through the canonical file→kind classifier
    # instead of a locally-duplicated ``{"status.events.jsonl", "status.json"}``
    # literal. Narrow ON PURPOSE (the two append-only logs, not the full
    # ``is_coord_residue_churn`` union): ``acceptance-matrix.json`` /
    # ``issue-matrix.md`` (``ACCEPTANCE_MATRIX`` / ``ISSUE_MATRIX``) STAY COORD
    # and must continue to be staged below — only the status/decision logs are
    # authored directly in the coord worktree and must never be copied from a
    # stale primary.
    path_kind = kind_for_mission_file(rel)
    if path_kind is MissionArtifactKind.STATUS_STATE:
        return _StagePlan.SKIP_STATUS_LOG
    if path_kind is MissionArtifactKind.DECISION_LOG:
        return _StagePlan.SKIP_DECISION_LOG
    # FR-003 (coord-commit-integrity): ``analysis-report.md`` was re-homed
    # COORD→PRIMARY — it lands on the primary ``target_branch`` and is NEVER
    # a second copy on the coordination worktree. Skip its copy2 staging path
    # (mirroring the log skips above) so a coord commit that
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
        return _StagePlan.SKIP_ANALYSIS_REPORT
    return _StagePlan.COPY


class _OwningSurfaceRefused(RuntimeError):
    """A root-path COORD-kind input could not be translated to its owning surface (WP05 T027/T029).

    Raised by :func:`_translate_to_owning_surface` / :func:`_resolve_owning_write_dir`
    and caught where :func:`_materialise_coord_worktree` is invoked (inside
    :func:`_commit_partition_group`), where it becomes a named ``refused``
    :class:`CommitRouterResult` — NEVER silently swallowed (T029).
    """

    def __init__(self, *, path: str, reason: str, diagnostic: str) -> None:
        super().__init__(diagnostic)
        self.path = path
        self.reason = reason
        self.diagnostic = diagnostic


def _mission_relative_subpath(rel: Path) -> Path | None:
    """The portion of *rel* AFTER ``kitty-specs/<mission-slug>/`` (WP05 T027).

    Pure path arithmetic mirroring the split
    :func:`~mission_runtime.kind_for_mission_file` performs internally to
    locate the Mission-relative tail — never a second classification
    authority, just "which segment comes after the Mission directory".
    Returns ``None`` when *rel* does not contain a ``kitty-specs/<slug>/...``
    shape with at least one segment after the slug.
    """
    from specify_cli.core.constants import KITTY_SPECS_DIR

    parts = rel.parts
    try:
        specs_index = parts.index(KITTY_SPECS_DIR)
    except ValueError:
        return None
    rel_index = specs_index + 2
    if rel_index >= len(parts):
        return None
    return Path(*parts[rel_index:])


def _resolve_owning_write_dir(
    repo_root: Path,
    kind: MissionArtifactKind,
    *,
    mission_slug: str,
    owned: OwnedCheckout | None,
    rel: Path,
) -> WriteLocation:
    """Resolve *kind*'s owning :class:`~mission_runtime.WriteLocation` via ``write_dir`` (T027).

    ``write_dir`` may materialise an UNMATERIALIZED local-head coordination
    worktree, or seed/restore a pre-/post-fix EMPTY surface (WP03/WP04) — that
    is intended (single home): a commit of a COORD record must land on its
    one true surface. Every NAMED failure ``write_dir`` can raise is
    translated here into :class:`_OwningSurfaceRefused` instead of
    propagating as a bare exception (T029):

    - :class:`~specify_cli.coordination.surface_resolver.CoordinationBranchDeleted`
      and the remote-only :class:`~specify_cli.coordination.surface_resolver.
      CoordinationWorktreeUnmaterialized` are
      :class:`~specify_cli.missions._read_path_resolver.StatusReadPathNotFound`
      subclasses, NOT :class:`~mission_runtime.ActionContextError` (WP04
      reviewer note) — caught explicitly, first.
    - :class:`~specify_cli.coordination.coord_seed.CoordSeedForkRefused` and its
      siblings (``COORD_SEED_EVENT_LOG_MALFORMED`` / ``COORD_SEED_DUPLICATE_EVENT_ID``
      / ``COORD_SEED_GIT_PROBE_FAILED``) arrive as plain
      :class:`~mission_runtime.ActionContextError` with a ``.code``.
    - :class:`~specify_cli.status.locking.FeatureStatusLockTimeoutError` carries
      its own stable ``.error_code`` (``STATUS_LOCK_HELD``, WP03).
    """
    from mission_runtime import ActionContextError, placement_seam
    from specify_cli.coordination.coord_seed import CoordSeedForkRefused
    from specify_cli.coordination.surface_resolver import (
        CoordinationBranchDeleted,
        CoordinationWorktreeUnmaterialized,
    )
    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    try:
        location: WriteLocation = placement_seam(repo_root, mission_slug, owned=owned).write_dir(kind)
        return location
    # Order matters: both subclass StatusReadPathNotFound (WP04 reviewer
    # note) and CoordSeedForkRefused subclasses ActionContextError, so the
    # NAMED subclasses are caught before their generic base.
    except CoordinationBranchDeleted as exc:
        raise _OwningSurfaceRefused(path=rel.as_posix(), reason=commit_outcome.COORDINATION_BRANCH_DELETED, diagnostic=str(exc)) from exc
    except CoordinationWorktreeUnmaterialized as exc:
        raise _OwningSurfaceRefused(path=rel.as_posix(), reason=commit_outcome.COORDINATION_WORKTREE_UNMATERIALIZED, diagnostic=str(exc)) from exc
    except StatusReadPathNotFound as exc:
        reason = getattr(exc, "error_code", None) or commit_outcome.PATH_UNROUTABLE
        raise _OwningSurfaceRefused(path=rel.as_posix(), reason=reason, diagnostic=str(exc)) from exc
    except FeatureStatusLockTimeoutError as exc:
        reason = getattr(exc, "error_code", None) or commit_outcome.STATUS_LOCK_HELD
        raise _OwningSurfaceRefused(path=rel.as_posix(), reason=reason, diagnostic=str(exc)) from exc
    except CoordSeedForkRefused as exc:
        raise _OwningSurfaceRefused(path=rel.as_posix(), reason=commit_outcome.COORD_SEED_FORK_REFUSED, diagnostic=str(exc)) from exc
    except ActionContextError as exc:
        raise _OwningSurfaceRefused(path=rel.as_posix(), reason=exc.code, diagnostic=str(exc)) from exc


def _translate_to_owning_surface(
    repo_root: Path,
    rel: Path,
    *,
    mission_slug: str,
    owned: OwnedCheckout | None,
    write_dirs: dict[MissionArtifactKind, WriteLocation],
) -> Path:
    """Resolve *rel*'s owning (coordination) absolute path (WP05 T027 / D7).

    ``write_dirs`` memoises one :func:`_resolve_owning_write_dir` call PER
    KIND across a whole staging batch — "resolve ONE WriteLocation per staging
    call, not one per path" (binding correction, seam map). A path whose
    ``kind_for_mission_file`` is ``None``, or whose Mission-relative tail
    cannot be located, is :data:`~specify_cli.coordination.commit_outcome.PATH_UNROUTABLE`
    (T029) — never silently coerced onto the caller's own ``kind``.
    """
    kind = kind_for_mission_file(rel)
    if kind is None:
        raise _OwningSurfaceRefused(
            path=rel.as_posix(),
            reason=commit_outcome.PATH_UNROUTABLE,
            diagnostic=f"{rel.as_posix()!r} does not classify to a known MissionArtifactKind; its owning (coordination) surface cannot be resolved.",
        )
    if kind not in write_dirs:
        write_dirs[kind] = _resolve_owning_write_dir(repo_root, kind, mission_slug=mission_slug, owned=owned, rel=rel)
    mission_rel = _mission_relative_subpath(rel)
    if mission_rel is None:
        raise _OwningSurfaceRefused(
            path=rel.as_posix(),
            reason=commit_outcome.PATH_UNROUTABLE,
            diagnostic=f"{rel.as_posix()!r} is not a Mission-relative path under 'kitty-specs/<mission>/'; its owning surface cannot be resolved.",
        )
    return write_dirs[kind].path / mission_rel


def _act_on_stage_plan(
    plan: _StagePlan,
    src: Path,
    rel: Path,
    coord_worktree: Path,
    repo_root: Path,
    *,
    mission_slug: str | None,
    owned: OwnedCheckout | None,
    write_dirs: dict[MissionArtifactKind, WriteLocation],
    named_files: frozenset[Path] = frozenset(),
) -> tuple[Path | None, tuple[Path, Path] | None]:
    """Act on *plan* for ONE path; returns ``(coord_file, staged_pair)`` (WP05 T027, WP04 reviewer note).

    ``coord_file`` is ``None`` for a dropped/skipped path. ``staged_pair`` is
    ``(src, dst)`` ONLY when a real ``shutil.copy2`` happened (the R6
    residue-cleanup input) — never for a translated (never-copied) path.

    This is the ONE place ``write_dir`` I/O happens for staging (kept OUT of
    :func:`_classify_stage_path`, which stays a pure per-path classifier, per
    the WP04 reviewer's binding note).
    """
    if plan is _StagePlan.IN_PLACE:
        return src, None
    if plan in _STAGE_PLAN_LOGS:
        if mission_slug is None:
            # Legacy 3-positional caller (no meta.json fixture): preserve the
            # historical "never copy a possibly-stale primary log" skip. #5513:
            # a primary-path STATUS_STATE file whose coordination twin carries
            # uncommitted content resolves to that twin, committed in place and
            # never copied over (skipping it outright reported
            # ``no_op_already_committed`` while the coord log stayed dirty). A
            # clean twin stays skipped, so a primary-only change still
            # classifies as wrong-surface. A twin the caller also named
            # directly (``named_files``) is committed through the in-place
            # branch, never probed or staged twice.
            twin = coord_worktree / rel
            if plan is _StagePlan.SKIP_STATUS_LOG and twin not in named_files and _is_uncommitted_in_worktree(coord_worktree, rel):
                return twin, None
            return None, None
        translated = _translate_to_owning_surface(repo_root, rel, mission_slug=mission_slug, owned=owned, write_dirs=write_dirs)
        # Never copied, regardless of existence — a root dirt log is judged
        # by the caller (T028), never silently mirrored.
        return translated, None
    if plan in _STAGE_PLAN_NO_COPY:
        return None, None
    # plan is COPY: a plain primary artifact, OR one of the four non-log COORD
    # kinds (TRACER_FILE / REVIEW_CYCLE / ISSUE_MATRIX / ACCEPTANCE_MATRIX) --
    # the UNCONDITIONAL legacy ``shutil.copy2`` overwrite, exactly pre-WP05
    # (reviewer ruling B1 / DECISION plan.design.translate-if-present-kinds:
    # see the _StagePlan.COPY docstring for why "owning copy wins" was
    # reverted for these four kinds -- none of their writers has migrated to
    # write_dir yet, so preferring an existing coordination copy silently
    # drops the writer's root-copy update).
    return _copy_into(src, coord_worktree / rel)


def _copy_into(src: Path, dst: Path) -> tuple[Path, tuple[Path, Path] | None]:
    """``shutil.copy2`` *src* to *dst* when present; ``dst`` is always returned (COPY-semantics, round 3)."""
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return dst, (src, dst)
    return dst, None


def _cleanup_staging_residue(
    staged_sources: list[tuple[Path, Path]],
    primary_paths_created_this_invocation: frozenset[Path] | None,
    repo_root: Path,
) -> None:
    """Delete a this-invocation-created primary source once its coord copy is
    confirmed byte-identical (R6 / #1814 residue cleanup).

    Extracted verbatim from :func:`_stage_artifacts_in_coord_worktree` (T005,
    campsite-clean WP01); the byte-compare guard and both log messages are
    unchanged.
    """
    if not primary_paths_created_this_invocation:
        return
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


def _stage_artifacts_in_coord_worktree(
    files: list[Path],
    coord_worktree: Path,
    repo_root: Path,
    *,
    primary_paths_created_this_invocation: frozenset[Path] | None = None,
    mission_slug: str | None = None,
    owned: OwnedCheckout | None = None,
) -> list[Path]:
    """Copy artifacts from the primary checkout to the coordination worktree.

    This IS the canonical staging helper (#2056 WP08 / T033 collapsed the former
    ``mission.py::_stage_finalize_artifacts_in_coord_worktree`` near-duplicate into
    this one function; the old name survives only as a backward-compat alias at the
    bottom of this module). Behaviour:
    - Translating a root-checkout ``STATUS_STATE`` / ``DECISION_LOG`` path to its
      owning (coordination) copy instead of skipping it (WP05 T027, D7) — ONLY
      when ``mission_slug`` is given; a 3-positional caller with no ``meta.json``
      fixture keeps the historical bare skip (#1589), except that a primary-path
      ``STATUS_STATE`` file whose coordination twin carries uncommitted content
      resolves to that twin, committed in place and never copied over (#5513).
    - ``TRACER_FILE`` / ``REVIEW_CYCLE`` / ``ISSUE_MATRIX`` / ``ACCEPTANCE_MATRIX``
      keep the UNCONDITIONAL legacy ``shutil.copy2`` overwrite (reviewer ruling
      B1 / DECISION plan.design.translate-if-present-kinds, WP05 cycle 1): none
      of their writers has migrated to ``write_dir`` yet, so "prefer the
      existing coordination copy" would silently drop every writer's root-copy
      update. The "owning copy wins" switch moves to the WP that migrates each
      kind's writer (WP08: review-cycle; WP10: tracer, issue-matrix; WP15:
      finalize, acceptance-matrix), one kind at a time.
    - Skipping the re-homed ``analysis-report.md`` (FR-003) — see
      :func:`_classify_stage_path`.
    - Skipping worktrees-nested paths (#FR-035).
    - Residue cleanup for ``primary_paths_created_this_invocation`` (R6 / #1814).

    ``mission_slug`` / ``owned`` are KEYWORD-ONLY and OPTIONAL (binding
    correction, seam map): several existing unit-test fixtures call this
    helper with exactly three positionals and no ``meta.json`` on disk, so an
    unconditional ``write_dir`` resolution would raise for them. Only a caller
    that supplies ``mission_slug`` gets the T027 translation; every other
    caller is byte-identical to the pre-WP05 behaviour.

    The per-path decision lives in :func:`_classify_stage_path` (T005,
    campsite-clean WP01); the per-path ACTION (including the ``write_dir``
    I/O for a translate plan) lives in :func:`_act_on_stage_plan` (WP05 T027,
    WP04 reviewer binding note: never put ``write_dir`` I/O in the
    classifier). ``coord_files`` is order-preserving DEDUPED (#5353 pin): a
    translated path and an already-IN_PLACE path can name the identical
    coordination file, and the pinned contract expects exactly one entry.
    """
    coord_files: list[Path] = []
    seen: set[Path] = set()
    staged_sources: list[tuple[Path, Path]] = []
    write_dirs: dict[MissionArtifactKind, WriteLocation] = {}
    named_files = frozenset(files)

    for src in files:
        rel = src.relative_to(repo_root)
        plan = _classify_stage_path(src, rel, coord_worktree)
        coord_file, staged_pair = _act_on_stage_plan(
            plan, src, rel, coord_worktree, repo_root, mission_slug=mission_slug, owned=owned, write_dirs=write_dirs, named_files=named_files
        )
        if coord_file is not None and coord_file not in seen:
            seen.add(coord_file)
            coord_files.append(coord_file)
        if staged_pair is not None:
            staged_sources.append(staged_pair)

    _cleanup_staging_residue(staged_sources, primary_paths_created_this_invocation, repo_root)
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


def _is_uncommitted_in_worktree(worktree: Path, rel: Path) -> bool:
    """True iff *rel* exists in *worktree* and carries uncommitted content there (#5513).

    An unreadable status raises ``GitCommandError`` rather than reading as clean,
    the same guard ``_paths_uncommitted_in_primary`` keeps (FR-013).
    """
    if not (worktree / rel).is_file():
        return False
    return bool(status_entries(worktree, pathspecs=(rel.as_posix(),), untracked=None))


def _relpath(repo_root: Path, path: Path) -> str:
    """Render *path* as the POSIX repo-relative string a :class:`PathFate` carries (WP05).

    Falls back to the raw ``str(path)`` when *path* is not actually under
    *repo_root* (e.g. a coordination-worktree path compared against the
    PRIMARY ``repo_root``) — this is cosmetic-only (the contract's ``path``
    field has no format guarantee beyond "as the caller passed it"), never a
    classification decision.
    """
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _dirty_paths_in_checkout(checkout_root: Path, files: tuple[Path, ...]) -> tuple[Path, ...]:
    """Return the subset of *files* that are present on disk AND carry uncommitted
    content (untracked or modified) in *checkout_root*.

    WP05 (T028): the single primitive both :func:`_paths_uncommitted_in_primary`
    (the #2739 B16 wrong-surface discriminator) and the root-checkout-dirt
    refinement (:func:`_refine_unchanged_for_root_checkout_dirt`) consult — one
    dirty check, not two independently-written loops.

    Each path is asked of git by itself through the typed, NUL-safe
    :func:`kernel.git.status_entries` (a path with a space, a quote, or a
    non-ASCII byte needs no un-quoting, and a rename needs no arrow parsing),
    so no porcelain text is parsed here. Guard (FR-013): an unreadable status
    must not read as "clean" and let a wrong-surface no-op pass as benign, so
    ``GitCommandError`` propagates. An ignored (``!!``) entry is never reported,
    matching the bare ``git status --porcelain`` this predicate always ran.
    """
    dirty: list[Path] = []
    for path in files:
        if not path.exists():
            continue
        try:
            rel = path.resolve().relative_to(checkout_root.resolve())
        except ValueError:
            continue
        if status_entries(checkout_root, pathspecs=(rel.as_posix(),), untracked=None):
            dirty.append(path)
    return tuple(dirty)


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
    return bool(_dirty_paths_in_checkout(repo_root, files))


def _is_empty_changeset_error(exc: RuntimeError) -> bool:
    # Match ONLY the genuine empty-changeset signal safe_commit now raises with a
    # distinct message. A generic "safe_commit: git commit failed …" (a rejecting
    # pre-commit hook, a lock error, etc.) must fall through to a real error,
    # never be silently reported as "unchanged".
    return "safe_commit: nothing to commit" in str(exc)


__all__ = [
    "CommitRouterResult",
    "commit_for_mission",
    "partition_for_mission_path",
]
