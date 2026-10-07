"""Accept command implementation."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NoReturn

import click
import typer
from rich.table import Table
from kernel.git import StatusEntry
from kernel.paths import to_posix
from mission_runtime import ActionContextError, MissionArtifactKind, OwnedCheckout, OwnedRefusalCode, TopologySurface

if TYPE_CHECKING:
    # WP16: annotation-only import (``from __future__ import annotations``
    # keeps this cold at runtime) -- every real use of ``commit_router``
    # stays function-local below, mirroring this module's established
    # pattern for the ``coordination`` package.
    from specify_cli.coordination.commit_router import CommitRouterResult

from specify_cli.acceptance import (
    AcceptanceError,
    AcceptanceResult,
    AcceptanceSummary,
    ArtifactEncodingError,
    acceptance_lane_derivations,
    choose_mode,
    collect_feature_summary,
    normalize_feature_encoding,
    perform_acceptance,
    resolve_acceptance_actor,
)
from specify_cli.acceptance.ledger_dirt import mission_decision_ledger_files
from specify_cli.acceptance.matrix import AcceptanceMatrixParseError
from specify_cli.config.path_conventions import PathConventionsConfigError
from specify_cli.core.paths import assert_safe_path_segment
from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES, require_unstaged_index
from specify_cli.migration.runtime_state_cutover import MissingMissionIdError
from specify_cli.migration.verdict_provenance_backfill import stranded_verdict_findings
from specify_cli.consolidation.baseline import (
    PrMergeEvidence,
    PrMergeEvidenceError,
    verify_pr_merge_evidence,
)
from specify_cli.git.origin_freshness import (
    READ_ONLY_ORIGIN_CHECK,
    OriginFreshnessRefused,
    resolve_origin_check_mode,
)
from specify_cli.git.origin_gate import run_origin_gate, verdict_payloads
from specify_cli.upgrade.pre30_guard import Pre30LayoutError
from specify_cli.cli import StepTracker
from specify_cli.cli.commands._owned_checkout import OwnedCheckoutOption, emit_owned_refusal, resolve_owned_or_adopt
from specify_cli.cli.selector_resolution import resolve_mission_dir_with_bare_modern_fold
from specify_cli.cli.console import console
from specify_cli.cli.helpers import show_banner
from specify_cli.task_utils import (
    LANES,
    TaskCliError,
    find_repo_root,
    git_status_entries,
    run_git,
)

logger = logging.getLogger(__name__)


def _stranded_verdict_provenance_note(feature_dir: Path) -> str | None:
    """Non-blocking SC-008 diagnostic: a WP with a terminal review-cycle ``.md``
    verdict but no event-log ``review_result`` slot.

    ``verdict-seam-write-unification-01KZ9Q35`` collapsed every verdict reader
    onto the event authority and deleted the frontmatter readers. The
    protective backfill runs on ``spec-kitty upgrade``; this diagnostic surfaces
    any mission still carrying a stranded verdict so an operator who has not yet
    upgraded (or whose consumers read the retired authority mid-upgrade) is told
    to run it. It is advisory only -- it never blocks acceptance and never
    raises: a diagnostic that could abort ``accept`` would be worse than the gap
    it reports.

    Returns ``None`` when there is nothing stranded (the converged, post-backfill
    steady state) or when the scan cannot run.
    """
    try:
        findings = stranded_verdict_findings(feature_dir)
    except Exception as exc:  # noqa: BLE001 — advisory diagnostic, never fatal
        logger.debug("stranded-verdict provenance scan skipped for %s: %s", feature_dir, exc)
        return None
    if not findings:
        return None
    wp_list = ", ".join(finding.wp_id for finding in findings)
    return (
        f"Stranded verdict provenance: {len(findings)} WP(s) ({wp_list}) carry a "
        "terminal review-cycle .md verdict with no event-log review_result slot. "
        "Run `spec-kitty upgrade` to backfill the event authority (FR-012/SC-008) "
        "before any consumer reads the retired frontmatter verdict mid-upgrade."
    )


def _dirty_paths_with_prefix(status: Iterable[StatusEntry], prefix: str) -> list[str]:
    """Filter ``git status`` entries to tracked-modified paths under ``prefix``.

    Shared by the primary and coordination-worktree scans (T008) so both
    surfaces apply the identical filtering rule: rename entries resolve to
    their destination path, and untracked files (``??``) are deliberately
    excluded so the cleanup commit never sweeps in unrelated, unmanaged files
    the operator may have created.
    """
    return [str(entry.path) for entry in status if not entry.is_untracked and str(entry.path).startswith(prefix)]


def _primary_dirty_paths(repo_root: Path, mission_slug: str) -> list[str]:
    """Return tracked-but-uncommitted spec/meta artifacts in the PRIMARY checkout.

    Also returns the current mission's dirty decision-ledger files -- including
    an UNTRACKED new ``DM-*.md`` the tracked-only scan skips -- because accept is
    a ledger committer (FR-009b / G1) and the dirty gate no longer blocks them.
    """
    prefix = f"kitty-specs/{mission_slug}/"
    dirty_entries = git_status_entries(repo_root)
    dirty = _dirty_paths_with_prefix(dirty_entries, prefix)
    for path in mission_decision_ledger_files(dirty_entries, repo_root=repo_root, mission_slug=mission_slug):
        if path not in dirty:
            dirty.append(path)
    return dirty


def _coord_scan_target(repo_root: Path, mission_slug: str, *, owned: OwnedCheckout | None = None) -> tuple[Path, Path] | None:
    """Resolve ``(worktree_root, coordination_mission_dir)`` for the dirt scan, if any.

    Returns ``None`` when the mission's stored topology does not route
    through coordination, or the coordination worktree has not been
    materialised on disk yet — there is nothing to reconcile before that
    (mirrors the leniency ``_status_read_feature_dir`` already applies).
    Never creates the worktree (a dirty-tree scan must not have side effects).

    Consumes the ONE affirmative surface→filesystem seam
    (:func:`mission_runtime.resolve_artifact_surface`,
    lifecycle-gate-execution-context WP02 — the schema root). The seam's
    :class:`~mission_runtime.TopologySurface` stamp IS the "coord or not" signal: a
    ``COORD`` stamp yields the materialised coordination mission dir (its worktree
    root is then found via ``git rev-parse``); every other stamp (the affirmative
    PRIMARY home for coord-less / ``EMPTY`` / ``UNMATERIALIZED``) means "nothing to
    reconcile" → ``None``. A ``DELETED`` coordination branch raises
    :class:`CoordinationBranchDeleted` (C3 "fail loud"): a deleted coord branch at
    accept-time carries unmerged status — accept must refuse, not silently scan a
    stale primary.

    The returned mission dir is the seam's own ``resolved.path`` — the
    coordination ``<slug>-<mid8>`` directory — NOT ``kitty-specs/<mission_slug>``:
    for a backfilled mission the primary directory name carries no ``-<mid8>``, so
    a prefix derived from ``mission_slug`` would match nothing in the worktree.
    """
    from mission_runtime import resolve_artifact_surface

    resolved = resolve_artifact_surface(repo_root, mission_slug, MissionArtifactKind.ACCEPTANCE_MATRIX, owned=owned)
    if resolved.surface_kind is not TopologySurface.COORD:
        return None

    try:
        worktree_root = Path(run_git(["rev-parse", "--show-toplevel"], cwd=resolved.path, check=True).stdout.strip())
    except TaskCliError:
        return None

    if worktree_root.resolve() == repo_root.resolve():
        return None
    return worktree_root, resolved.path


def _coord_worktree_root(repo_root: Path, mission_slug: str, *, owned: OwnedCheckout | None = None) -> Path | None:
    """Resolve the mission's materialised coordination worktree root, if any.

    Thin projection of :func:`_coord_scan_target`; see it for the resolution
    contract (no side effects, ``None`` for any non-COORD stamp).
    """
    target = _coord_scan_target(repo_root, mission_slug, owned=owned)
    return None if target is None else target[0]


def _coord_status_feature_dir(repo_root: Path, mission_slug: str, *, owned: OwnedCheckout | None = None) -> Path | None:
    """Resolve the COORD-partition mission dir the birth-cutover seeds into.

    ``cutover_mission``'s ``status_feature_dir`` argument IS the ``STATUS_STATE``
    port target — the directory where ``status.events.jsonl`` canonically lives
    under coordination topology (``runtime_state_cutover.cutover_mission``
    docstring, WP09/IC-08). So the kind is
    :attr:`~mission_runtime.MissionArtifactKind.STATUS_STATE`, not the
    ``ACCEPTANCE_MATRIX`` kind :func:`_coord_worktree_root` probes with: both are
    COORD-partition kinds resolving to the same mission dir, but naming the kind
    the caller actually writes keeps the site honest if the partition table ever
    splits them.

    WP16 (FR-003, coord-artifact-single-home-01M3V4BE): the birth cutover is a
    WRITE, so this now asks :meth:`~mission_runtime.PlacementSeam.write_dir`
    rather than :meth:`~mission_runtime.PlacementSeam.read_dir`. The read
    projection's declared EMPTY/UNMATERIALIZED-surface fallback to the PRIMARY
    checkout (a sanctioned READ-side degrade, never meant for a write) used to
    leak into this write call transitively, so a pre-fix or not-yet-materialised
    coordination surface silently wrote the birth-cutover seed into the
    repository-root checkout instead of its one true coordination home — the
    exact single-home violation this mission exists to close. ``write_dir``
    instead materialises an ``UNMATERIALIZED`` local-head worktree, seeds a
    pre-fix ``EMPTY`` surface or restores a post-fix one, or refuses by raising
    a named exception (never a silent primary substitution) — see the module
    docstring of :meth:`~mission_runtime.PlacementSeam.write_dir` for the full
    resolution order.

    Returns ``None`` only when the mission's ``STATUS_STATE`` surface is
    declared PRIMARY (a coord-less topology), preserving the pre-existing
    contract that ``cutover_mission`` then collapses both legs onto the
    PRIMARY ``feature_dir`` — there is no more EMPTY/UNMATERIALIZED ``None``
    fallback for a coordination-routed Mission. For a coordination-routed
    Mission, a ``DELETED`` coordination branch
    (:class:`~specify_cli.coordination.surface_resolver.CoordinationBranchDeleted`),
    a remote-only coordination branch
    (:class:`~specify_cli.coordination.surface_resolver.CoordinationWorktreeUnmaterialized`),
    a forked coordination log
    (:class:`~specify_cli.coordination.coord_seed.CoordSeedForkRefused`), or a
    held status lock
    (:class:`~specify_cli.status.locking.FeatureStatusLockTimeoutError`) all
    propagate UNCHANGED out of this function (C3 "fail loud") — the caller,
    :func:`_stamp_birth_cutover_for_accept`, converts each into an actionable
    :class:`~specify_cli.acceptance.AcceptanceError` rather than crashing
    unstructured or silently stamping a stale primary.
    """
    from mission_runtime import placement_seam

    # Guard the handle before it reaches the seam so both legs of the stamp carry
    # the same traversal check (the PRIMARY leg gets it from
    # ``primary_feature_dir_for_mission``).
    assert_safe_path_segment(mission_slug)

    location = placement_seam(repo_root, mission_slug, owned=owned).write_dir(MissionArtifactKind.STATUS_STATE)
    if location.surface is not TopologySurface.COORD:
        return None
    return location.path


def _coord_dirty_paths(repo_root: Path, mission_slug: str, *, owned: OwnedCheckout | None = None) -> list[str]:
    """Return tracked-but-uncommitted acceptance artifacts in the COORD worktree.

    M2 (#read-surface-ssot-closeout FR-008): ``write_acceptance_matrix`` writes
    ``acceptance-matrix.json`` (and the sibling issue-matrix/status views) to
    the coordination worktree's ``feature_dir`` under coordination topology
    (:func:`~specify_cli.acceptance.resolve_feature_dir_for_mission` /
    :func:`~mission_runtime.placement_seam`). A primary-only
    ``git_status_entries(repo_root)`` scan can never see that dirt — it lives in
    a completely separate git worktree. This mirrors :func:`_primary_dirty_paths`
    against that surface instead.
    """
    target = _coord_scan_target(repo_root, mission_slug, owned=owned)
    if target is None:
        return []
    worktree_root, mission_dir = target
    # The COORDINATION mission dir (``<slug>-<mid8>``), relative to the worktree
    # root -- never ``kitty-specs/<mission_slug>`` (the primary dir name).
    prefix = to_posix(mission_dir.resolve().relative_to(worktree_root.resolve())) + "/"
    return _dirty_paths_with_prefix(git_status_entries(worktree_root), prefix)


def _spec_artifact_dirty_paths(repo_root: Path, mission_slug: str) -> list[str]:
    """Return tracked-but-uncommitted spec/meta artifacts under the mission dir.

    The acceptance pipeline materializes derived artifacts (e.g.
    ``acceptance-matrix.json`` and status views) while running readiness checks
    *before* the acceptance commit is created. Those writes happen after the
    git-cleanliness snapshot is taken, so the acceptance commit only captures
    ``meta.json`` and leaves the materialized artifacts modified-unstaged. This
    helper finds exactly those leftover tracked modifications so the command can
    fold them into the acceptance state and leave a clean working tree.

    M2 (T008): under coordination topology the acceptance-matrix write lands in
    the coordination worktree, not the primary checkout, so the scan also
    consults that surface (:func:`_coord_dirty_paths`) and unions the result —
    a flattened/non-coord mission is unaffected (that scan returns ``[]``).
    """
    dirty = _primary_dirty_paths(repo_root, mission_slug)
    for path in _coord_dirty_paths(repo_root, mission_slug):
        if path not in dirty:
            dirty.append(path)
    return dirty


def _stamp_birth_cutover_for_accept(
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> None:
    """Auto-stamp the birth-cutover into the mission branch at the terminal
    ``accept`` seam (WP02 / FR-001 / FR-004 / FR-005 / FR-006 / NFR-003).

    Mirrors ``consolidation/phase_bookkeeping.py::_run_birth_cutover``'s shape (resolve PRIMARY
    + COORD legs -> the single-authority
    :func:`~specify_cli.migration.runtime_state_cutover.cutover_mission`, via
    :func:`~specify_cli.migration.runtime_state_cutover.stamp_accept_cutover`
    — no forked writer) so the committed corpus is already cut over before
    the branch can land by ANY path (closing the GitHub-squash/rebase leak,
    #2917 reopened). Runs only when runtime state is final: the caller only
    reaches this on the real-commit path, AFTER ``summary.ok`` already gated
    every WP approved/done (FR-004 — avoids the dual-write vacuity trap).

    Deliberately called BEFORE
    :func:`_commit_residual_acceptance_artifacts` so this stamp's own writes
    (PRIMARY ``meta.json`` ``status_phase``, COORD seed events) are swept into
    that SAME partition-aware residual commit (R4 — the stamp must be a
    committed artifact, not a working-tree-only write the background status
    daemon might commit later under an unrelated message). No second
    committer is introduced here.

    Best-effort / non-fatal for an ordinary cutover failure (mirrors
    ``_run_birth_cutover``: a stamp failure must not abort an otherwise
    successful accept — the gap remains repairable via ``migrate
    backfill-runtime-state`` / ``doctor cutover``). A
    :class:`~specify_cli.migration.runtime_state_cutover.MissingMissionIdError`
    (NFR-003/R6 fail-closed) is the one exception that propagates, so the
    caller aborts the whole ``accept`` command rather than silently landing a
    slug-namespaced seed.
    """
    # PRIMARY leg via the blessed topology-blind constructor rather than a raw
    # join: it is the sanctioned owner of ``KITTY_SPECS_DIR`` assembly AND it
    # applies ``assert_safe_path_segment`` to the slug. It deliberately does NOT
    # route through the topology-aware resolver -- that one selects the coord
    # worktree once it exists, which is exactly the surface that lacks
    # ``meta.json``, so using it here would send the phase stamp to the wrong leg.
    #
    # read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): routed off
    # the retiring ``primary_feature_dir_for_mission`` wrapper onto the seam
    # directly — PRIMARY_METADATA, since the read/write target is meta.json's
    # ``status_phase`` (per ``stamp_accept_cutover``'s own contract docstring).
    # WP08 (T036): the caller-side canonicalizer fold DROPPED — redundant with
    # the seam's own internal fold for a PRIMARY-partition kind (the SAME
    # ``_canonicalize_primary_read_handle`` primitive
    # ``resolve_planning_read_dir``'s PRIMARY leg applies before composing).
    from mission_runtime import placement_seam

    feature_dir = placement_seam(repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.PRIMARY_METADATA)
    if not feature_dir.is_dir():
        return  # nothing to stamp

    from specify_cli.migration.runtime_state_cutover import stamp_accept_cutover

    # COORD leg comes from the kind-aware placement seam (see
    # :func:`_coord_status_feature_dir`) rather than a hand-built join under the
    # coordination worktree root: a PRIMARY-kind seam read would redirect this
    # back to the primary checkout (it normalises through
    # ``get_main_repo_root``) and collapse the very partition split this
    # function exists to preserve, while a raw mission-spec-dir join re-derives
    # placement the seam already owns.
    #
    # FR-003: ``owned`` is the fact the CLI edge validated, exactly once. This
    # function never re-validates from a bare root; a run with no fact is a
    # non-owned run and keeps the best-effort semantics below.
    #
    # WP16: ``_coord_status_feature_dir`` now asks ``write_dir`` (a WRITE
    # resolution), which can refuse with two refusals a pre-WP16 ``read_dir``
    # call never raised: a remote-only coordination branch
    # (``CoordinationWorktreeUnmaterialized``, #4970 parity) and a forked
    # coordination log (``CoordSeedForkRefused``) -- plus a held status lock
    # (``FeatureStatusLockTimeoutError``). All three are converted into an
    # actionable ``AcceptanceError`` here (T089) instead of crashing
    # unstructured. ``CoordinationBranchDeleted`` is UNCHANGED -- the
    # pre-existing fail-loud contract
    # (``test_stamp_birth_cutover_resolves_primary_dir_regardless_of_coord_state``'s
    # own docstring: "fail-loud is the intended contract for a real accept-time
    # cutover, not a diagnostic") -- and still propagates raw.
    from specify_cli.coordination.coord_seed import CoordSeedForkRefused
    from specify_cli.coordination.surface_resolver import (
        CoordinationBranchDeleted,
        CoordinationWorktreeUnmaterialized,
    )
    from specify_cli.status import FeatureStatusLockTimeoutError

    try:
        status_feature_dir = _coord_status_feature_dir(repo_root, mission_slug, owned=owned)
    except CoordinationBranchDeleted:
        raise
    except (CoordinationWorktreeUnmaterialized, CoordSeedForkRefused, FeatureStatusLockTimeoutError) as exc:
        raise AcceptanceError(f"Coordination status surface refused for {mission_slug} while stamping the birth cutover: {exc}") from exc

    try:
        result = stamp_accept_cutover(feature_dir, status_feature_dir=status_feature_dir, owned=owned)
    except MissingMissionIdError:
        raise
    except Exception as exc:  # noqa: BLE001 — best-effort, mirrors _run_birth_cutover
        if owned is not None:
            raise AcceptanceError(f"Owned birth-cutover failed: {exc}") from exc
        logger.warning("birth-cutover stamp failed for %s: %s", mission_slug, exc)
        return

    if owned is not None and not result.flipped:
        detail = result.error or ("; ".join(result.verify.mismatches) if result.verify else "no verified stamp")
        raise AcceptanceError(f"Owned birth-cutover failed: {detail}")
    if result.error:
        logger.warning("birth-cutover for %s did not reconcile: %s", mission_slug, result.error)


def _record_pr_merge_for_accept(
    repo_root: Path,
    mission_slug: str,
    merge_commit: str,
    *,
    owned: OwnedCheckout | None = None,
    target_ref: str | None = None,
    attest_first_landing: bool = False,
) -> PrMergeEvidence:
    """Record the PR's real merge commit as the post-merge review baseline (#4231).

    A mission accepted through ``--mode pr`` never passes through
    ``spec-kitty consolidate``, so without this recording its ``meta.json`` never
    carries ``baseline_merge_commit`` and both ``spec-kitty review --mode
    post-merge`` (``MISSION_REVIEW_MODE_MISMATCH``) and the lightweight
    dead-code gate (``dead_code_baseline_missing``) misreport a cleanly
    merged mission. This records the merge the mission ACTUALLY had, through
    the shared single seam
    (:func:`specify_cli.consolidation.baseline.record_pr_merge_baseline_for_mission`
    — the same one ``migrate backfill-merge-commit`` uses), which verifies the
    commit against git before writing anything — no fabricated evidence.

    Mirrors :func:`_stamp_birth_cutover_for_accept`'s placement (PRIMARY
    ``meta.json`` via the kind-aware seam) and ordering (called before
    :func:`_commit_residual_acceptance_artifacts` so this write is swept into
    that same partition-aware residual commit). Unlike the birth-cutover
    stamp it is NOT best-effort: the operator explicitly asked for the merge
    to be recorded, so a failure propagates and the command exits non-zero
    rather than silently landing a mission whose baseline was never recorded
    — the exact silent-gap defect #4231 reports.
    """
    from specify_cli.consolidation.baseline import record_pr_merge_baseline_for_mission

    return record_pr_merge_baseline_for_mission(
        repo_root,
        mission_slug,
        merge_commit,
        owned=owned,
        target_ref=target_ref,
        attest_first_landing=attest_first_landing,
    )


def _residual_commit_files(
    repo_root: Path,
    mission_slug: str,
    *,
    primary_dirty: list[str],
    coord_dirty: list[str],
    owned: OwnedCheckout | None,
) -> tuple[Path, ...]:
    """Build the ONE absolute-path batch both residual legs feed to the router.

    WP16 (FR-005, research D9): primary-checkout dirt resolves against
    ``repo_root`` (where it physically lives); coordination-worktree dirt
    resolves against the COORDINATION worktree root (``_coord_worktree_root``),
    never joined onto ``repo_root`` -- that join (the retired L427 bug) handed
    the router non-existent root-relative paths for files that only exist in
    the coordination worktree, which is why the coordination leg silently
    no-opped before this WP. Passing each leg's paths already resolved against
    the checkout they actually live in makes the coordination paths land
    ``IN_PLACE`` in :func:`~specify_cli.coordination.commit_router
    ._materialise_coord_worktree`'s staging classification -- no ``copy2``
    overwrite risk, by construction (binding correction
    ``plan.design.owning-copy-flip-allocation``).
    """
    files: tuple[Path, ...] = tuple(repo_root / path for path in primary_dirty)
    if not coord_dirty:
        return files
    coord_worktree_root = _coord_worktree_root(repo_root, mission_slug, owned=owned)
    if coord_worktree_root is None:
        # Defensive only: ``_coord_dirty_paths`` itself resolves
        # ``_coord_worktree_root`` and returns ``[]`` whenever it is ``None``,
        # so ``coord_dirty`` is non-empty here precisely when this is not
        # ``None`` either. Kept so a future caller that hands this helper a
        # pre-computed ``coord_dirty`` list fails closed instead of silently
        # dropping coordination residuals.
        return files
    return files + tuple(coord_worktree_root / path for path in coord_dirty)


class ResidualCommitError(TaskCliError):
    """Raised by :func:`_run_residual_acceptance_commit` when any surface is refused/error.

    Carries the :class:`~specify_cli.coordination.commit_router.CommitRouterResult`
    so the CLI boundary can render ``residual_commit.surfaces`` on the FAILURE
    arm too (B3, cycle 2 review) -- not just the success arm T087 already covered.
    """

    def __init__(self, message: str, *, result: CommitRouterResult) -> None:
        super().__init__(message)
        self.result = result


def _format_residual_failure_detail(result: CommitRouterResult) -> str:
    """Render *result* for a :class:`ResidualCommitError` message (B2, cycle 2 review).

    ``render_commit_outcome`` alone prints only ``path: reason`` for a named
    refused/error path -- a bare machine code like ``error``, never the
    ACTIONABLE diagnostic text a lower-level primitive (e.g. ``safe_commit``'s
    ``SafeCommitHeadMismatch``: "HEAD is 'other', expected 'topic'. Run git
    checkout topic first.") attaches to ``SurfaceOutcome.diagnostic``. This
    appends every non-empty refused/error surface diagnostic so the operator
    sees the actionable instruction, not just the bare reason code.
    """
    from specify_cli.coordination.commit_outcome import render_commit_outcome

    parts = list(render_commit_outcome(result))
    for surface in result.surfaces:
        if surface.status in ("refused", "error") and surface.diagnostic:
            detail_line = f"{surface.surface} ({surface.branch}): {surface.diagnostic}"
            if detail_line not in parts:
                parts.append(detail_line)
    return "; ".join(parts) if parts else (result.diagnostic or "unknown error")


def _run_residual_acceptance_commit(
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None = None,
) -> CommitRouterResult | None:
    """Commit BOTH residual legs through the ONE router call (FR-005, C-001).

    Replaces the retired two-mechanism split (a raw ``git commit`` for
    PRIMARY-checkout residuals, a separate ``write_artifact`` call for
    coordination-worktree residuals): this WP removes the raw commit
    entirely and routes every dirty mission path -- from either checkout --
    through :func:`~specify_cli.coordination.commit_router.commit_for_mission`
    in one call. The router's own ``_group_files_by_partition`` groups the
    batch by partition and commits each group to its own resolved surface
    (R9 -- the SAME per-path verdict the dirty gate consults via
    :func:`~specify_cli.coordination.commit_router.partition_for_mission_path`),
    so neither leg is hand-classified here.

    Decision ``plan.design.accept-primary-leg-ref``: when HEAD is unprotected,
    the PRIMARY residual leg commits on that same branch (the branch
    ``_commit_acceptance_meta`` uses for its raw commit). The branch is passed
    as ``commit_for_mission``'s ``primary_ref``, which retargets only the
    PRIMARY group. ``target_branch`` is left unset so this accept-only
    override does not change ``spec-commit`` or write-seam callers. A
    protected HEAD does not override: the router's
    protected-branch guard still applies to the stored target. Coordination
    groups are unaffected.

    Returns ``None`` when neither checkout has any residual dirt (the
    bool wrapper, :func:`_commit_residual_acceptance_artifacts`, reports that
    as ``False``). Raises :class:`ResidualCommitError` (carrying the result,
    B3) naming every refused/error surface's diagnostic (B2) when any
    surface comes back ``refused`` or ``error``.
    """
    from specify_cli.coordination.commit_router import commit_for_mission
    from specify_cli.core.git_ops import get_current_branch
    from specify_cli.git.protection_policy import ProtectionPolicy

    primary_dirty = _primary_dirty_paths(repo_root, mission_slug)
    coord_dirty = _coord_dirty_paths(repo_root, mission_slug, owned=owned)
    if not primary_dirty and not coord_dirty:
        return None

    files = _residual_commit_files(repo_root, mission_slug, primary_dirty=primary_dirty, coord_dirty=coord_dirty, owned=owned)
    policy = ProtectionPolicy.resolve(repo_root)
    current_branch = get_current_branch(repo_root)
    primary_ref = current_branch if current_branch and not policy.is_protected(current_branch) else None
    result = commit_for_mission(
        repo_root,
        mission_slug,
        files,
        f"Finalize acceptance artifacts for {mission_slug}",
        policy,
        kind=MissionArtifactKind.ACCEPTANCE_MATRIX,
        primary_ref=primary_ref,
        owned=owned,
    )

    if any(surface.status in ("refused", "error") for surface in result.surfaces):
        detail = _format_residual_failure_detail(result)
        raise ResidualCommitError(f"Residual acceptance artifact commit failed for {mission_slug}: {detail}", result=result)
    return result


def _commit_residual_acceptance_artifacts(repo_root: Path, mission_slug: str, *, owned: OwnedCheckout | None = None) -> bool:
    """Stage and commit any leftover acceptance artifacts so the tree is clean.

    Returns True when a follow-up commit was created on at least one surface.
    This preserves the recorded ``accept_commit`` SHA (it still points at the
    real acceptance commit) while guaranteeing a successful ``accept`` leaves
    no staged-but-uncommitted or modified-unstaged spec/meta artifacts behind
    (modulo a root-checkout COORD-record copy, reported skipped -- never
    committed to the target, see :func:`_run_residual_acceptance_commit`'s
    ``COORD_RECORD_IN_ROOT_CHECKOUT`` fate).

    Kept as a ``bool`` return (operator decision, brownfield scout round 3),
    but it is no longer on the ``accept`` command path:
    :func:`_run_post_acceptance_steps` calls
    :func:`_run_residual_acceptance_commit` directly, and
    ``test_accept_decomposition.py`` monkeypatches that name (while still
    asserting this wrapper's ``bool`` contract by calling it). The CI-owned
    ``test_accept_matrix_coord_partition.py`` also calls this wrapper and
    asserts ``created is True`` against the real function, which is why it is
    not deleted. The detailed
    :class:`~specify_cli.coordination.commit_router.CommitRouterResult` (for
    JSON/text rendering) lives on the private
    :func:`_run_residual_acceptance_commit` helper this wrapper calls.
    """
    result = _run_residual_acceptance_commit(repo_root, mission_slug, owned=owned)
    if result is None:
        return False
    return any(surface.status == "committed" for surface in result.surfaces)


def _print_acceptance_warnings(summary: AcceptanceSummary) -> None:
    """Render non-blocking ``summary.warnings`` in the human console.

    The ``--json`` output already carries ``warnings``, but the human-readable
    paths did not surface them, so a ``--lenient`` operator (issue #1892) got no
    signal about what was downgraded from blocking to advisory. Shown only when
    non-empty so a clean summary prints no spurious section.
    """
    if not summary.warnings:
        return
    console.print("\n[bold yellow]Warnings[/bold yellow]")
    for warning in summary.warnings:
        console.print(f"[yellow]- {warning}[/yellow]")


def _print_acceptance_summary(summary: AcceptanceSummary) -> None:
    table = Table(title="Work Packages by Lane", header_style="cyan")
    table.add_column("Lane")
    table.add_column("Count", justify="right")
    table.add_column("Work Packages", justify="left")
    for lane in LANES:
        items = summary.lanes.get(lane, [])
        display = ", ".join(items) if items else "-"
        table.add_row(lane, str(len(items)), display)
    console.print(table)

    outstanding = summary.outstanding()
    if outstanding:
        console.print("\n[bold red]Outstanding items[/bold red]")
        for key, values in outstanding.items():
            console.print(f"[red]- {key}[/red]")
            for value in values:
                console.print(f"    • {value}")
    else:
        console.print("\n[green]No outstanding acceptance issues detected.[/green]")

    _print_acceptance_warnings(summary)


def _print_acceptance_result(result: AcceptanceResult) -> None:
    console.print(
        f"\n[bold]Acceptance metadata[/bold]\n• Mission: {result.summary.feature}\n• Accepted at: {result.accepted_at}\n• Accepted by: {result.accepted_by}"
    )
    if result.accept_commit:
        console.print(f"• Acceptance commit: {result.accept_commit}")
    if result.parent_commit:
        console.print(f"• Parent commit: {result.parent_commit}")
    if not result.commit_created:
        console.print("• Commit status: no changes were committed (dry-run)")
    if result.accepted_wps:
        console.print(f"• Accepted WPs: {', '.join(result.accepted_wps)}")
    if result.merge_pending_wps:
        console.print(f"• Merge-pending WPs: {', '.join(result.merge_pending_wps)}")
    if result.done_wps:
        console.print(f"• Already merged WPs: {', '.join(result.done_wps)}")

    if result.instructions:
        console.print("\n[bold]Next steps[/bold]")
        for idx, instruction in enumerate(result.instructions, start=1):
            console.print(f"  {idx}. {instruction}")

    if result.cleanup_instructions:
        console.print("\n[bold]Cleanup[/bold]")
        for idx, instruction in enumerate(result.cleanup_instructions, start=1):
            console.print(f"  {idx}. {instruction}")

    if result.notes:
        console.print("\n[bold]Notes[/bold]")
        for note in result.notes:
            console.print(f"  - {note}")


def _print_acceptance_diagnosis(summary: AcceptanceSummary) -> None:
    failed_checks = summary.failed_checks()
    if failed_checks:
        console.print("\n[bold red]Failed checks[/bold red]")
        for item in failed_checks:
            console.print(f"[red]- {item.check}[/red]: {item.detail}")
    else:
        console.print("\n[green]No failed acceptance checks detected.[/green]")

    if summary.skipped_checks:
        console.print("\n[bold yellow]Skipped checks[/bold yellow]")
        for item in summary.skipped_checks:
            console.print(f"[yellow]- {item.check}[/yellow]: {item.detail}")

    if summary.blocked_checks:
        console.print("\n[bold yellow]Blocked checks[/bold yellow]")
        for item in summary.blocked_checks:
            console.print(f"[yellow]- {item.check}[/yellow]: {item.detail}")

    _print_acceptance_warnings(summary)

    if summary.recommended_fix_order:
        console.print("\n[bold]Recommended fix order[/bold]")
        for idx, fix in enumerate(summary.recommended_fix_order, start=1):
            console.print(f"  {idx}. {fix}")


def _summary_payload(summary: AcceptanceSummary) -> dict[str, object]:
    payload: dict[str, object] = summary.to_dict()
    payload.update(acceptance_lane_derivations(summary))
    return payload


def _with_advisories(payload: dict[str, object], notes: list[str | None]) -> dict[str, object]:
    """Inject a top-level ``advisories`` array into a non-error JSON payload.

    #3255: ``accept --json`` dropped the SC-008 stranded-verdict backfill
    advisory (``_stranded_verdict_provenance_note``) because it was only
    ever rendered inside the ``if not json_output`` console branch, so JSON
    automation never saw the "run ``spec-kitty upgrade``" hint. This is a
    CLI-layer-only concern (C-005): it must never be threaded into
    ``AcceptanceSummary``/``AcceptanceResult`` — the domain model stays
    unaware of migration-provenance advisories. ``notes`` is filtered for
    ``None`` entries so callers can pass the raw (possibly-``None``) result
    of an advisory lookup without a conditional at every call site; the
    array is present (``[]``) even when nothing is stranded, so JSON
    consumers can rely on the key always existing.
    """
    payload["advisories"] = [note for note in notes if note is not None]
    return payload


def _report_encoding_repair(repo_root: Path, repaired: list[Path]) -> None:
    """Surface which acceptance artifacts the encoding repair rewrote.

    Mirrors the command's existing ``console`` reporting idiom. Paths are shown
    relative to ``repo_root`` when possible so the operator sees mission-relative
    artifact names rather than absolute temp paths.
    """
    if not repaired:
        console.print("[yellow]--normalize-encoding enabled but no artifacts required updates.[/yellow]")
        return
    console.print("[yellow]Normalized acceptance-artifact encoding for:[/yellow]")
    for path in repaired:
        try:
            display = path.relative_to(repo_root)
        except ValueError:
            display = path
        console.print(f"  - {display}")


def _collect_summary_with_optional_repair(
    repo_root: Path,
    mission_slug: str,
    *,
    strict_metadata: bool,
    mutate_matrix: bool,
    normalize_encoding: bool,
    owned: OwnedCheckout | None = None,
) -> AcceptanceSummary:
    """Collect the acceptance summary, optionally repairing artifact encoding.

    FR-005 / C-003: when ``normalize_encoding`` is True and the strict UTF-8 read
    raises ``ArtifactEncodingError``, delegate to the **canonical**
    ``acceptance.normalize_feature_encoding`` (no standalone logic is copied),
    report the repaired paths, and re-collect exactly once. Any second failure
    propagates to the caller's ``except AcceptanceError`` handler (exit 1). When
    the flag is off, the error propagates unchanged so the pre-existing default
    error path is preserved untouched.
    """
    try:
        return collect_feature_summary(
            repo_root,
            mission_slug,
            strict_metadata=strict_metadata,
            mutate_matrix=mutate_matrix,
            owned=owned,
        )
    except PathConventionsConfigError as exc:
        # A malformed ``project.path_conventions`` section is a fail-closed operator
        # config error (SC-007). Surface it as a clean accept blocking verdict through
        # the command's ``except AcceptanceError`` handler (exit 1) rather than letting
        # the typed exception reach typer as a raw traceback.
        raise AcceptanceError(str(exc)) from exc
    except ArtifactEncodingError:
        if not normalize_encoding:
            raise
        repaired = normalize_feature_encoding(
            repo_root,
            mission_slug,
            owned=owned,
        )
        _report_encoding_repair(repo_root, repaired)
        # Re-collect exactly once; a second encoding failure means the canonical
        # detector refused the file (its code page is genuinely ambiguous — e.g. a
        # lone stray byte in otherwise-ASCII text that no single code page can
        # disambiguate). Re-suggesting --normalize-encoding would loop; point the
        # operator at the byte-offset repair surface instead (#4962/#4968).
        try:
            return collect_feature_summary(
                repo_root,
                mission_slug,
                strict_metadata=strict_metadata,
                mutate_matrix=mutate_matrix,
                owned=owned,
            )
        except ArtifactEncodingError as exc:
            raise AcceptanceError(
                f"Could not safely recover the encoding of {exc.path}: byte "
                f"0x{exc.error.object[exc.error.start]:02x} at offset {exc.error.start} "
                "is ambiguous (no single code page fits), so --normalize-encoding "
                "refused rather than risk silent corruption. Repair the stray "
                f"byte(s) with `spec-kitty validate-encoding --fix {exc.path}` "
                "(byte-offset repair), or re-save the file as UTF-8, then re-run accept."
            ) from exc


def _owned_accept_context(
    repo_root: Path,
    checkout: Path | None,
    mission: str | None,
    *,
    diagnose: bool,
    normalize_encoding: bool,
) -> OwnedCheckout | None:
    """Validate ownership once (explicit ``--owned-checkout`` or flagless adoption) before any acceptance read or write.

    Returns the validated fact, or ``None`` when the run stays on the
    repository root checkout. Every later phase consumes this one fact.
    """
    owned = resolve_owned_or_adopt(
        repo_root,
        checkout,
        mission,
        cwd=Path.cwd(),
        allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
    )
    if owned is None:
        return None
    if diagnose and normalize_encoding:
        raise ActionContextError(OwnedRefusalCode.OWNED_OPTION_UNSUPPORTED, "--diagnose cannot repair encoding in an owned checkout.")
    if not diagnose:
        require_unstaged_index(owned)
    return owned


# ---------------------------------------------------------------------------
# accept() phases (FR-026 / IC-14a): one small helper per phase so the command
# body is a linear sequence and stays under the complexity ceiling. Behaviour is
# pinned by tests/specify_cli/cli/commands/test_accept_decomposition.py.
# ---------------------------------------------------------------------------

_REQUIRED_MISSION_MESSAGE = "--mission <slug> is required"


@dataclass(frozen=True)
class _AcceptRun:
    """The resolved, read-only facts every phase of one ``accept`` run shares."""

    json_output: bool
    tracker: StepTracker
    repo_root: Path
    mission_slug: str
    mission_dir: Path
    owned: OwnedCheckout | None
    actual_mode: str
    commit_required: bool
    provenance_note: str | None
    origin_warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class _PrMergeRequest:
    """A ``--merge-commit`` whose evidence was verified before any acceptance write."""

    evidence: PrMergeEvidence
    merge_commit: str
    target_ref: str | None
    attest_first_landing: bool


@dataclass
class _FinalizeOutcome:
    """What the perform / stamp / PR-merge / residual-commit sequence produced."""

    result: AcceptanceResult | None = None
    accept_exc: AcceptanceError | None = None
    stamp_exc: Exception | None = None
    pr_merge_exc: Exception | None = None
    residue_exc: Exception | None = None
    pr_merge_recorded: bool = False
    #: T087: the router result behind the residual-artifacts commit, when one
    #: ran (``None`` when neither checkout had any residual dirt). Threaded
    #: through to ``_render_accept_result`` so ``--json`` can add
    #: ``residual_commit.surfaces`` and text output can render the same
    #: per-surface lines through the shared renderer (contract rule 6).
    residual_commit_result: CommitRouterResult | None = None


def _report_error(
    json_output: bool,
    message: str,
    *,
    tracker: StepTracker | None = None,
    step: str | None = None,
    extra_json: dict[str, object] | None = None,
) -> None:
    """Emit one error on the active output lane (JSON envelope or console).

    When ``tracker`` and ``step`` are given, the human lane also marks that
    step failed and renders the tracker first. ``extra_json`` merges additive
    keys into the ``--json`` failure envelope (B3, cycle 2 review) --
    ``residual_commit.surfaces`` on a residual-commit failure, so the
    per-surface outcome is not lost behind the flattened error string.

    B3 (cycle 2 review): ``message`` can embed ``render_commit_outcome``
    lines and raw diagnostic text from an arbitrary lower-level git error
    (e.g. a stray ``[/red]``), which would otherwise corrupt or crash Rich's
    markup parser (``MarkupError``) when interpolated into ``[red]Error:
    [/red] {message}`` or a tracker detail. ``rich.markup.escape`` makes the
    text literal on BOTH the console line and the tracker, mirroring the
    pattern WP10 cycle 2 established for ``render_commit_outcome`` consumers.
    """
    if json_output:
        payload: dict[str, object] = {"error": message}
        if extra_json:
            payload.update(extra_json)
        print(json.dumps(payload))
        return
    from rich.markup import escape

    safe_message = escape(message)
    if tracker is not None and step is not None:
        tracker.error(step, safe_message)
        console.print(tracker.render())
    console.print(f"[red]Error:[/red] {safe_message}")


def _fail(
    json_output: bool,
    message: str,
    *,
    code: int = 1,
    tracker: StepTracker | None = None,
    step: str | None = None,
    extra_json: dict[str, object] | None = None,
) -> NoReturn:
    """Emit one error and exit with ``code``."""
    _report_error(json_output, message, tracker=tracker, step=step, extra_json=extra_json)
    raise typer.Exit(code)


def _refusal_envelope(code: str, message: str) -> dict[str, object]:
    """Accept's owned-refusal JSON envelope: ``{"error_code", "error"}``."""
    return {"error_code": code, "error": message}


def _resolve_accept_entry(
    json_output: bool,
    checkout: Path | None,
    mission: str | None,
    *,
    diagnose: bool,
    normalize_encoding: bool,
) -> tuple[Path, OwnedCheckout | None]:
    """Find the repository root and validate opt-in ownership before any read or write."""
    try:
        repo_root = find_repo_root()
        owned = _owned_accept_context(
            repo_root,
            checkout,
            mission,
            diagnose=diagnose,
            normalize_encoding=normalize_encoding,
        )
    except ActionContextError as exc:
        emit_owned_refusal(exc, json_output=json_output, envelope=_refusal_envelope)
    except TaskCliError as exc:
        _fail(json_output, str(exc))
    return (owned.owned_root if owned is not None else repo_root), owned


def _start_tracker(json_output: bool) -> StepTracker:
    tracker = StepTracker("Mission Acceptance")
    if not json_output:
        tracker.add("detect", "Identify mission slug")
        tracker.add("verify", "Run readiness checks")
        console.print()
        tracker.start("detect")
    return tracker


def _resolve_mission_identity(
    raw_handle: str | None,
    repo_root: Path,
    owned: OwnedCheckout | None,
    json_output: bool,
    tracker: StepTracker,
) -> tuple[str, Path]:
    """Resolve the mission slug and directory, or exit 2 when no handle was given.

    Supports slug, numeric prefix, mid8, full ULID, or a bare human slug naming
    a composed ``<slug>-<mid8>`` primary dir (#4723).
    ``resolve_mission_dir_with_bare_modern_fold()`` tries the shared
    bare-modern-slug primitive first (so an ambiguous bare slug raises the
    structured ambiguity error instead of a misleading MISSION_NOT_FOUND), then
    falls back to ``resolve_mission_handle()`` for every other form; both legs
    call ``sys.exit()`` on failure, so no try/except is needed here.
    """
    if raw_handle is None:
        _fail(json_output, _REQUIRED_MISSION_MESSAGE, code=2, tracker=tracker, step="detect")
    if owned is not None:
        return owned.mission_slug, owned.mission_dir
    mission_dir = resolve_mission_dir_with_bare_modern_fold(raw_handle, repo_root, json_mode=json_output)
    return mission_dir.name, mission_dir


def _plan_run(
    *,
    json_output: bool,
    tracker: StepTracker,
    repo_root: Path,
    mission_slug: str,
    mission_dir: Path,
    owned: OwnedCheckout | None,
    requested_mode: str,
    no_commit: bool,
    diagnose: bool,
) -> _AcceptRun:
    """Announce the mission, pick the acceptance mode and register the remaining steps."""
    # T020 (#3255): computed unconditionally so the SC-008 advisory reaches
    # BOTH the human console (non-JSON branch below) and every non-error
    # `--json` payload via `_with_advisories` — it was previously gated
    # behind `if not json_output`, so JSON automation never saw it.
    provenance_note = _stranded_verdict_provenance_note(mission_dir)
    if not json_output:
        tracker.complete("detect", mission_slug)
        if provenance_note is not None:
            console.print(f"[yellow]⚠ {provenance_note}[/yellow]")

    actual_mode = choose_mode((requested_mode or "auto").lower(), repo_root)
    commit_required = actual_mode != "checklist" and not no_commit and not diagnose
    if not json_output:
        if commit_required:
            tracker.add("commit", "Record acceptance metadata")
        tracker.add("guide", "Report diagnostics" if diagnose else "Share next steps")
    return _AcceptRun(
        json_output=json_output,
        tracker=tracker,
        repo_root=repo_root,
        mission_slug=mission_slug,
        mission_dir=mission_dir,
        owned=owned,
        actual_mode=actual_mode,
        commit_required=commit_required,
        provenance_note=provenance_note,
    )


def _verify_merge_commit(
    run: _AcceptRun,
    merge_commit: str | None,
    target_branch: str | None,
    attest_first_landing: bool,
) -> _PrMergeRequest | None:
    """Validate ``--merge-commit`` BEFORE any acceptance write (#4231).

    A bad or unverifiable SHA fails with nothing mutated. Verification is
    read-only git, so ``--diagnose`` / ``--no-commit`` may carry it too.
    """
    if merge_commit is None:
        return None
    if run.actual_mode != "pr":
        _fail(
            run.json_output,
            f"--merge-commit is only valid with --mode pr (resolved mode: "
            f"{run.actual_mode}). A {run.actual_mode} acceptance records its "
            "baseline_merge_commit through `spec-kitty consolidate`, not here.",
            code=2,
        )
    try:
        evidence = verify_pr_merge_evidence(
            run.repo_root,
            run.mission_slug,
            merge_commit,
            target_ref=target_branch,
            attest_first_landing=attest_first_landing,
            owned=run.owned,
        )
    except PrMergeEvidenceError as exc:
        _fail(run.json_output, f"Cannot record PR merge for {run.mission_slug}: {exc}")
    return _PrMergeRequest(evidence, merge_commit, target_branch, attest_first_landing)


def _check_origin_freshness(run: _AcceptRun, origin_check: str | None, *, read_only: bool) -> _AcceptRun:
    """Refuse on stale or unreachable origin status evidence BEFORE any acceptance read or write (FR-003).

    ``--no-commit`` / ``--diagnose`` are read-only: the verdict is reported, never
    refused. Warnings (warn mode, read-only, a bad opt-out value) go to stderr so a
    ``--json`` stdout stays one payload, and ride the payload's ``advisories``.
    """
    setting = READ_ONLY_ORIGIN_CHECK if read_only else resolve_origin_check_mode(origin_check)
    try:
        warnings = run_origin_gate(run.repo_root, run.mission_slug, setting=setting, owned=run.owned)
    except OriginFreshnessRefused as exc:
        _fail(
            run.json_output,
            str(exc),
            extra_json={"error_code": exc.error_code, "error_codes": exc.error_codes, "origin_freshness": verdict_payloads(exc.verdicts)},
        )
    for warning in warnings:
        typer.echo(f"Warning: {warning}", err=True)
    return replace(run, origin_warnings=tuple(warnings))


def _collect_summary_or_exit(
    run: _AcceptRun,
    *,
    lenient: bool,
    diagnose: bool,
    normalize_encoding: bool,
) -> AcceptanceSummary:
    """Collect the acceptance summary; a blocking collection error exits 1 with nothing written."""
    if not run.json_output:
        run.tracker.start("verify")
    try:
        summary = _collect_summary_with_optional_repair(
            run.repo_root,
            run.mission_slug,
            strict_metadata=not lenient,
            # --no-commit must still resolve the acceptance matrix (run negative
            # invariants, refresh verdict); otherwise the verdict stays 'pending'
            # and the gate can never pass in --no-commit mode. The matrix write
            # is accept-owned and excluded from the dirty-tree gate (#1883), so
            # mutating without committing is safe and converges. Only diagnose
            # (read-only) leaves the matrix untouched.
            mutate_matrix=not diagnose,
            # FR-005: opt-in repair of mojibake acceptance artifacts via the
            # canonical normalize_feature_encoding before validating (default off).
            normalize_encoding=normalize_encoding,
            owned=run.owned,
        )
    except (Pre30LayoutError, AcceptanceError, AcceptanceMatrixParseError) as exc:
        # #1057 / squad Blocker 1: a pre-3.0 lane-directory mission must hard-reject
        # with the `spec-kitty upgrade` instruction and write NOTHING — never fall
        # through to a vacuous all-done summary that auto-commits an unmigrated
        # mission.
        # T021 (mgifford, #2318): a malformed acceptance-matrix.json item
        # (a bad negative_invariants/criteria entry) is REPORTED here —
        # which item, why — instead of crashing with an unhandled TypeError
        # at load. Catching it here (rather than inside
        # AcceptanceMatrix.from_dict) also fixes every OTHER accept mode that
        # hits the same load path, without weakening gates_core.py's /
        # post_consolidation.py's own loud-crash contract on malformed input.
        _fail(run.json_output, str(exc), tracker=run.tracker, step="verify")
    if not run.json_output:
        run.tracker.complete("verify", "ready" if summary.ok else "issues found")
    return summary


def _exit_early_for_report_modes(run: _AcceptRun, summary: AcceptanceSummary, *, diagnose: bool, allow_fail: bool) -> None:
    """Exit for ``--diagnose``, checklist mode and a not-ready summary; return when acceptance may proceed."""
    if diagnose:
        _report_diagnosis(run, summary)
        raise typer.Exit(0)
    if run.actual_mode == "checklist":
        _report_summary(run, summary)
        raise typer.Exit(0 if summary.ok else 1)
    if not summary.ok:
        _report_summary(run, summary, raw=True)
        if not allow_fail and not run.json_output:
            console.print(
                "\n[red]Outstanding acceptance issues detected. Resolve them before merging or rerun with --allow-fail for a checklist-only report.[/red]"
            )
        raise typer.Exit(1)


def _report_diagnosis(run: _AcceptRun, summary: AcceptanceSummary) -> None:
    if run.json_output:
        payload = _summary_payload(summary)
        payload["diagnose"] = True
        print(json.dumps(_with_advisories(payload, [run.provenance_note, *run.origin_warnings]), indent=2))
        return
    run.tracker.start("guide")
    run.tracker.complete("guide", "diagnostics ready")
    console.print(run.tracker.render())
    _print_acceptance_diagnosis(summary)


def _report_summary(run: _AcceptRun, summary: AcceptanceSummary, *, raw: bool = False) -> None:
    """Print the readiness summary; ``raw`` selects the bare ``summary.to_dict()`` JSON shape."""
    if run.json_output:
        payload = summary.to_dict() if raw else _summary_payload(summary)
        print(json.dumps(_with_advisories(payload, [run.provenance_note, *run.origin_warnings]), indent=2))
    else:
        _print_acceptance_summary(summary)


def _perform_and_finalize(
    run: _AcceptRun,
    summary: AcceptanceSummary,
    *,
    actor: str | None,
    tests: list[str],
    pr_merge: _PrMergeRequest | None,
) -> _FinalizeOutcome:
    """Perform acceptance, then always run the post-acceptance steps in their fixed order.

    The residual-artifacts commit runs after an ``AcceptanceError`` too, and an
    unexpected exception from ``perform_acceptance`` still propagates once the
    ``finally`` block has run.
    """
    acceptance_tests = list(tests)
    actor_name = resolve_acceptance_actor(actor)

    # T015 / WP04 / FR-001: the protected-primary guard is no longer a hard
    # reject here.  ``_commit_acceptance_meta`` routes every commit through
    # ``commit_for_mission``, which materialises the coordination worktree on
    # demand when the primary is protected (C-001 / FR-003).  A pre-flight
    # raise-and-exit deadlock is therefore unnecessary and has been removed.
    outcome = _FinalizeOutcome()
    try:
        _perform_acceptance_step(run, summary, actor_name, acceptance_tests, outcome)
    finally:
        _run_post_acceptance_steps(run, outcome, pr_merge)
    return outcome


def _perform_acceptance_step(
    run: _AcceptRun,
    summary: AcceptanceSummary,
    actor_name: str,
    acceptance_tests: list[str],
    outcome: _FinalizeOutcome,
) -> None:
    try:
        if run.commit_required and not run.json_output:
            run.tracker.start("commit")
        result = perform_acceptance(
            summary,
            mode=run.actual_mode,
            actor=actor_name,
            tests=acceptance_tests,
            auto_commit=run.commit_required,
        )
        outcome.result = result
        if run.commit_required and not run.json_output:
            run.tracker.complete("commit", "commit created" if result.commit_created else "no changes")
    except AcceptanceError as exc:
        outcome.accept_exc = exc
        _report_error(run.json_output, str(exc), tracker=run.tracker if run.commit_required else None, step="commit")


def _run_post_acceptance_steps(run: _AcceptRun, outcome: _FinalizeOutcome, pr_merge: _PrMergeRequest | None) -> None:
    if not run.commit_required:
        return
    if outcome.accept_exc is None:
        _stamp_step(run, outcome)
        if pr_merge is not None:
            _record_pr_merge_step(run, outcome, pr_merge)
    # The acceptance commit (inside perform_acceptance) only captures
    # meta.json. Derived artifacts materialized during readiness checks
    # (e.g. acceptance-matrix.json, status views) are written after the
    # git-cleanliness snapshot and would otherwise be left dirty. Fold
    # them into a follow-up commit so all writing exit paths (including
    # error paths and accept_commit == None) leave a clean working tree.
    try:
        outcome.residual_commit_result = _run_residual_acceptance_commit(run.repo_root, run.mission_slug, owned=run.owned)
    except ResidualCommitError as residue_exc:
        # B3 (cycle 2 review): keep the merged result even on failure so the
        # CLI boundary can still render ``residual_commit.surfaces`` -- not
        # just flatten everything into the error string.
        outcome.residue_exc = residue_exc
        outcome.residual_commit_result = residue_exc.result
    except Exception as residue_exc:
        outcome.residue_exc = residue_exc


def _stamp_step(run: _AcceptRun, outcome: _FinalizeOutcome) -> None:
    # WP02 (FR-001/FR-004/FR-005): stamp the birth-cutover ONLY on the
    # real-commit, acceptance-succeeded path -- runtime state is
    # already final (summary.ok gated all WPs approved/done above).
    # Deliberately BEFORE the residual-artifacts commit so its
    # writes (meta.json status_phase, COORD seed events) are swept
    # into that SAME partition-aware commit rather than needing a
    # second committer.
    try:
        # #3866 / FR-003: hand the stamp the fact the CLI edge validated; it
        # never re-validates ownership.
        _stamp_birth_cutover_for_accept(run.repo_root, run.mission_slug, owned=run.owned)
    except (MissingMissionIdError, AcceptanceError, ActionContextError) as stamp_exc:
        outcome.stamp_exc = stamp_exc


def _record_pr_merge_step(run: _AcceptRun, outcome: _FinalizeOutcome, pr_merge: _PrMergeRequest) -> None:
    # #4231: record the verified PR merge as the review baseline on the
    # same real-commit, acceptance-succeeded path as the birth-cutover
    # stamp, BEFORE the residual-artifacts commit so this meta.json
    # write is swept into that same partition-aware commit. Unlike the
    # stamp this is explicit operator intent, so a failure propagates
    # to the command's exit path instead of degrading to a warning.
    try:
        _record_pr_merge_for_accept(
            run.repo_root,
            run.mission_slug,
            pr_merge.merge_commit,
            target_ref=pr_merge.target_ref,
            attest_first_landing=pr_merge.attest_first_landing,
            owned=run.owned,
        )
        outcome.pr_merge_recorded = True
    except Exception as pr_merge_error:  # noqa: BLE001 — reported on the command's own error lane below
        outcome.pr_merge_exc = pr_merge_error


def _raise_on_finalize_errors(run: _AcceptRun, outcome: _FinalizeOutcome) -> AcceptanceResult:
    """Exit 1 on the first finalize failure (acceptance, stamp, PR merge, residual, in that order)."""
    result = outcome.result
    if outcome.accept_exc is not None or result is None:
        raise typer.Exit(1)
    if outcome.stamp_exc is not None:
        _fail(run.json_output, f"Birth-cutover stamp refused: {outcome.stamp_exc}")
    if outcome.pr_merge_exc is not None:
        _fail(run.json_output, f"PR merge recording failed: {outcome.pr_merge_exc}")
    if outcome.residue_exc is not None:
        extra_json: dict[str, object] | None = None
        if outcome.residual_commit_result is not None:
            from specify_cli.coordination.commit_outcome import commit_outcome_payload

            extra_json = {"residual_commit": commit_outcome_payload(outcome.residual_commit_result)}
        _fail(
            run.json_output,
            f"Residual artifact commit failed: {outcome.residue_exc}",
            tracker=run.tracker if run.commit_required else None,
            step="commit",
            extra_json=extra_json,
        )
    return result


def _note_pr_merge_outcome(result: AcceptanceResult, pr_merge: _PrMergeRequest | None, *, recorded: bool) -> None:
    """Surface the PR-merge recording outcome on both output lanes (#4231)."""
    if pr_merge is None:
        return
    if recorded:
        evidence = pr_merge.evidence
        result.notes.append(
            "PR merge recorded: baseline_merge_commit "
            f"{evidence.baseline_merge_commit} "
            f"(PR merge commit {evidence.pr_merge_commit}; "
            f"anchor evidence {evidence.anchor_evidence})"
        )
    else:
        result.notes.append("--merge-commit verified against this repository; re-run without --no-commit to record it as the review baseline")


def _render_accept_result(
    run: _AcceptRun,
    result: AcceptanceResult,
    *,
    residual_commit_result: CommitRouterResult | None = None,
) -> None:
    """Render the acceptance result, plus the residual commit's per-surface outcome (T087).

    ``residual_commit_result`` is additive on both lanes: ``None`` (no
    residual dirt was found) changes nothing from before this WP. When
    present, ``--json`` gains a ``residual_commit.surfaces`` key
    (contracts/commit-outcome.md) and text output gains one line per
    surface, then one per named path, through the shared
    :func:`~specify_cli.coordination.commit_outcome.render_commit_outcome` —
    never formatted by hand here (contract rule 6).
    """
    if run.json_output:
        payload = _with_advisories(result.to_dict(), [run.provenance_note, *run.origin_warnings])
        if residual_commit_result is not None:
            from specify_cli.coordination.commit_outcome import commit_outcome_payload

            payload["residual_commit"] = commit_outcome_payload(residual_commit_result)
        print(json.dumps(payload, indent=2))
        return
    run.tracker.start("guide")
    run.tracker.complete("guide", "instructions ready")
    console.print(run.tracker.render())

    _print_acceptance_summary(result.summary)
    _print_acceptance_result(result)

    if residual_commit_result is not None:
        from specify_cli.coordination.commit_outcome import render_commit_outcome

        for line in render_commit_outcome(residual_commit_result):
            console.print(line, markup=False)


def accept(
    mission: str | None = typer.Option(
        None,
        "--mission",
        help="Mission slug to accept",
    ),
    mode: str = typer.Option("auto", "--mode", case_sensitive=False, help="Acceptance mode: auto, pr, local, or checklist"),
    actor: str | None = typer.Option(None, "--actor", help="Name to record as the acceptance actor"),
    test: list[str] = typer.Option([], "--test", help="Validation command executed (repeatable)", show_default=False),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON instead of formatted text"),
    lenient: bool = typer.Option(
        False,
        "--lenient",
        help="Skip strict metadata validation and downgrade missing path-convention checks to warnings",
    ),
    no_commit: bool = typer.Option(False, "--no-commit", help="Report acceptance readiness without writing metadata or status changes"),
    diagnose: bool = typer.Option(False, "--diagnose", help="Diagnose acceptance blockers without writing metadata or matrix artifacts"),
    allow_fail: bool = typer.Option(False, "--allow-fail", help="Return checklist even when issues remain"),
    normalize_encoding: bool = typer.Option(
        False,
        "--normalize-encoding/--no-normalize-encoding",
        help="Repair acceptance-artifact encoding (Windows-1252/Latin-1 -> UTF-8) before validating.",
    ),
    owned_checkout: OwnedCheckoutOption = None,
    origin_check: Annotated[
        str | None,
        typer.Option(
            "--origin-check",
            click_type=click.Choice(["enforce", "warn"]),
            help=(
                "Refuse (enforce, the default) or only warn (warn) when the mission's status evidence is behind "
                "or unreachable on its remote. Overrides SPEC_KITTY_ORIGIN_CHECK. --no-commit and --diagnose always warn."
            ),
        ),
    ] = None,
    merge_commit: Annotated[
        str | None,
        typer.Option(
            "--merge-commit",
            metavar="SHA",
            help=(
                "With --mode pr: record this PR merge commit as the mission's "
                "post-merge review baseline. The commit is verified against git "
                "before anything is written — it must carry "
                "kitty-specs/<slug>/meta.json, its first parent must not, and it "
                "must have landed on the target branch. Every landing shape "
                "additionally needs --attest-first-landing-commit."
            ),
        ),
    ] = None,
    target_branch: Annotated[
        str | None,
        typer.Option(
            "--target-branch",
            help=(
                "With --merge-commit: the branch the PR merged into (the PR's "
                "base branch). Defaults to the mission's declared target_branch, "
                "else the repository's primary branch."
            ),
        ),
    ] = None,
    attest_first_landing: Annotated[
        bool,
        typer.Option(
            "--attest-first-landing-commit",
            help=(
                "With --merge-commit: attest that the supplied commit's first "
                "parent is the pre-landing target tip — for a two-parent "
                "merge commit, that the merge was performed ON the target "
                "branch (an internal merge fast-forwarded onto the target "
                "is graph-identical, and its first parent is an "
                "implementation commit); for a single-parent landing (squash "
                "or corpus-first stack), that it was the first commit of the "
                "landing. Required for every landing shape: git cannot prove "
                "either, and a wrong anchor silently under-scans the "
                "dead-code gate. The attestation is recorded in "
                "pr_merge_evidence, never presented as a git proof."
            ),
        ),
    ] = False,
) -> None:
    """Validate mission readiness before merging to main."""

    if not json_output:
        show_banner()

    repo_root, owned = _resolve_accept_entry(
        json_output,
        owned_checkout,
        mission,
        diagnose=diagnose,
        normalize_encoding=normalize_encoding,
    )
    tracker = _start_tracker(json_output)
    mission_slug, mission_dir = _resolve_mission_identity(mission, repo_root, owned, json_output, tracker)
    run = _plan_run(
        json_output=json_output,
        tracker=tracker,
        repo_root=repo_root,
        mission_slug=mission_slug,
        mission_dir=mission_dir,
        owned=owned,
        requested_mode=mode,
        no_commit=no_commit,
        diagnose=diagnose,
    )
    pr_merge = _verify_merge_commit(run, merge_commit, target_branch, attest_first_landing)
    run = _check_origin_freshness(run, origin_check, read_only=no_commit or diagnose)
    summary = _collect_summary_or_exit(run, lenient=lenient, diagnose=diagnose, normalize_encoding=normalize_encoding)
    _exit_early_for_report_modes(run, summary, diagnose=diagnose, allow_fail=allow_fail)
    outcome = _perform_and_finalize(run, summary, actor=actor, tests=test, pr_merge=pr_merge)
    result = _raise_on_finalize_errors(run, outcome)
    _note_pr_merge_outcome(result, pr_merge, recorded=outcome.pr_merge_recorded)
    _render_accept_result(run, result, residual_commit_result=outcome.residual_commit_result)


__all__ = ["accept"]
