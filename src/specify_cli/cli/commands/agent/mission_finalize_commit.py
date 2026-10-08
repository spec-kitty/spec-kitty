"""``finalize-tasks`` phase: the finalize commit pipeline.

Candidate resolution, the commit-router result, the success report and the
refusal-time rollback guards.

Part of the ``mission_finalize`` decomposition (#5627); bodies moved verbatim.
``mission_finalize`` re-exports every name defined here, so historical
``mission_finalize.<name>`` imports and patch targets keep resolving. To keep
those patches *intercepting*, calls to a patched name or to a function owned by
another finalize module go through a lazy in-function
``from specify_cli.cli.commands.agent import mission_finalize as _mf`` import
(cycle-safe: never at module scope) -- the same seam-bridge idiom
``tasks_shared`` uses.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

import typer

from kernel.atomic import observe_writes, stop_observing_writes


if TYPE_CHECKING:
    from specify_cli.coordination.commit_router import CommitRouterResult
from mission_runtime import ActionContextError, MissionArtifactKind, mission_file_basenames_for_kind
from specify_cli.core.commit_guard import GuardCapability
from mission_runtime import OwnedCheckout
from specify_cli.lanes.models import LanesManifest
from specify_cli.ownership.models import OwnershipManifest
from specify_cli.status import BootstrapResult, WPMetadata
from specify_cli.status import mission_write_lock

if TYPE_CHECKING:
    from specify_cli.cli.commands.agent.mission_finalize_bootstrap import _BootstrapState
    from specify_cli.cli.commands.agent.mission_finalize_planning_pin import PlanningCommitResolution
    from specify_cli.cli.commands.agent.mission_finalize_validation import _DependencyResolution
    from specify_cli.lanes.compute import LaneMembershipFrozenError
    from specify_cli.lanes.frozen_membership import FrozenLaneMembership
from specify_cli.cli.commands.agent.finalize_status_surface import StatusSurfaceGuard, StatusSurfaceLeftover
from specify_cli.cli.commands.agent.mission_finalize_branch_contract import TargetBranchPersistOutcome
from specify_cli.cli.commands.agent.mission_finalize_seams import FINALIZE_TASKS_COMMAND_NAME, META_JSON_FILENAME, logger


@dataclass
class _CommitOutcome:
    """Outcome of the finalize commit phase.

    ``commit_hash`` remains the historical single-value projection (the
    feature-branch commit for the common case) for backward compatibility.
    ``commit_hashes`` (#2549 facet B) additionally carries the FULL per-branch
    commit set the router actually issued — under coord topology this includes
    BOTH the feature-branch commit (primary-partition artifacts: tasks.md,
    lanes.json, tasks/WP*) AND the coordination-branch commit (placement-
    partition artifacts: status.events.jsonl, status.json, acceptance-
    matrix.json, issue-matrix.md), which ``commit_hash`` alone cannot express.
    """

    commit_created: bool = False
    commit_hash: str | None = None
    commit_hashes: list[dict[str, str]] = field(default_factory=list)
    files_committed: list[str] = field(default_factory=list)
    diagnostic: str | None = None
    #: WP15/FR-007 (contracts/commit-outcome.md): the serialized per-surface
    #: outcome -- ``commit_outcome_payload(router_result)["surfaces"]``, never
    #: hand-formatted (rule 6). Empty for the pre-``surfaces`` legacy case
    #: (no commit attempted) or any caller that never reached the router.
    commit_surfaces: list[dict[str, object]] = field(default_factory=list)
    #: True iff any surface in ``commit_surfaces`` is ``refused``/``error``
    #: (:func:`~specify_cli.coordination.commit_outcome.commit_outcome_exit_code`
    #: contract rule 5) -- the caller raises after rendering, never before.
    surface_refusal: bool = False
    #: WP13-review binding correction: ``render_commit_outcome(router_result)``'s
    #: plain text lines, computed once alongside ``commit_surfaces`` from the
    #: SAME real router result -- never re-derived from the serialized
    #: ``commit_surfaces`` payload. Printed with ``markup=False`` by every
    #: text-mode consumer (untrusted path/diagnostic content, never Rich markup).
    rendered_lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _FinalizeCommitCandidates:
    """T071 campsite: the resolved commit-candidate file list plus whether any are dirty."""

    files_to_commit: list[Path]
    files_to_commit_rel: list[str]
    has_relevant_changes: bool


def _finalize_candidates_dirty(repo_root: Path, files_to_commit_rel: list[str]) -> bool:
    """True when any finalize candidate path has a pending change.

    A failed probe propagates (``GitCommandError``) rather than reading as "no
    changes", which would silently skip the finalize commit.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    return bool(_mf.status_entries(repo_root, pathspecs=files_to_commit_rel, untracked=None))


#: WP15/T081 (FR-007b): the COORD-partition kinds whose files finalize may itself
#: write, each resolved through its own ``write_dir``. ``STATUS_STATE`` covers the
#: event-log/snapshot files; ``ISSUE_MATRIX``/``ACCEPTANCE_MATRIX`` each resolve
#: their own kind-specific directory (identical to the STATUS_STATE one for a
#: coordination-routed Mission's single Mission dir, but resolved independently
#: so a kind-specific routing exception -- e.g. the PUBLISHED/E2 short-circuit --
#: is honored per kind rather than assumed). The FILENAMES are never listed here:
#: :func:`_coord_candidate_filenames` derives them from the artifact classifier,
#: so a classifier entry (e.g. the failover-read ``issue-matrix.md``) can never be
#: invisible to this probe.
_COORD_CANDIDATE_KINDS: Final[tuple[MissionArtifactKind, ...]] = (
    MissionArtifactKind.STATUS_STATE,
    MissionArtifactKind.ISSUE_MATRIX,
    MissionArtifactKind.ACCEPTANCE_MATRIX,
)


def _coord_candidate_filenames(kind: MissionArtifactKind) -> tuple[str, ...]:
    """The basenames the artifact classifier maps to *kind*, in a stable order."""
    return tuple(sorted(mission_file_basenames_for_kind(kind)))


@dataclass(frozen=True)
class _CoordCandidateDirt:
    """WP15/T081: resolved COORD-kind commit candidates plus whether any are dirty."""

    files: list[Path]
    is_dirty: bool


def _coord_candidate_dirt(
    repo_root: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None,
) -> _CoordCandidateDirt:
    """Resolve finalize's COORD-kind commit candidates and probe them for dirt (FR-007b).

    ``_resolve_finalize_commit_candidates``'s own porcelain check runs only in
    the repository-root checkout, so a coordination-routed Mission's
    lifecycle records -- which land in the coordination worktree after
    WP15/T080 -- read as "no changes" even while genuinely dirty there. This
    helper resolves each COORD kind's write location FIRST (write-before-check,
    research D2): a pending seed is committed by ``write_dir`` before the
    porcelain probe ever runs, so a never-seeded pre-fix Mission reports real
    dirt instead of silently reading clean. Deduplicates resolved
    directories: under ``lanes``/``single_branch`` topology (C-008) every
    kind's ``write_dir`` returns the SAME ``planning_dir`` the PRIMARY
    candidates already cover, so this never double-reports or double-commits
    those paths.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    from mission_runtime import placement_seam

    seam = placement_seam(repo_root, mission_slug, owned=owned)
    checkout_roots_by_dir: dict[Path, Path] = {}
    candidates: list[Path] = []
    for kind in _COORD_CANDIDATE_KINDS:
        location = seam.write_dir(kind)
        checkout_roots_by_dir.setdefault(location.path, location.surface_root)
        for filename in _coord_candidate_filenames(kind):
            candidate = location.path / filename
            if candidate.exists():
                candidates.append(candidate)

    seen: set[Path] = set()
    files: list[Path] = []
    for candidate in candidates:
        if candidate not in seen:
            files.append(candidate)
            seen.add(candidate)

    is_dirty = False
    for directory, checkout_root in checkout_roots_by_dir.items():
        rel_files = [str(path.relative_to(checkout_root)) for path in files if path.is_relative_to(directory)]
        if not rel_files:
            continue
        # A failed probe propagates (``GitCommandError``) -- see ``_finalize_candidates_dirty``.
        if _mf._finalize_candidates_dirty(checkout_root, rel_files):
            is_dirty = True

    return _CoordCandidateDirt(files=files, is_dirty=is_dirty)


def _resolve_finalize_commit_candidates(
    planning_dir: Path,
    tasks_dir: Path,
    repo_root: Path,
    lanes_path: Path | None,
    *,
    mission_slug: str,
    owned: OwnedCheckout | None = None,
) -> _FinalizeCommitCandidates:
    """Phase: collect and porcelain-check the finalize commit-candidate file list (T071/WP15-T081).

    meta.json (#3466 / SK3466-RR-001) needs no special-cased ``extra_paths``
    threading here: :func:`_collect_finalize_artifacts` already includes it as
    a candidate, so a ``--target-branch`` correction rides the same ``git
    status --porcelain`` gate as every other tracked artifact. But unlike
    those other artifacts, meta.json can ALSO carry a pending edit
    finalize-tasks did not make (SK3466-REV-001, e.g. ``implement
    --no-auto-commit``'s ``vcs``/``vcs_locked_at`` write) — so it is
    additionally checked with :func:`_meta_json_delta_is_finalize_attributable`
    and dropped entirely when the pending delta is not confined to the
    fields finalize-tasks itself owns.

    WP15/T081 (FR-007b): ``has_relevant_changes`` additionally honors
    :func:`_coord_candidate_dirt` -- the COORD-kind commit candidates
    (resolved via ``write_dir``, never the PRIMARY-anchored porcelain check
    below) -- so coordination-only dirt is never reported as "no changes".
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    files_to_commit = _mf._collect_finalize_artifacts(planning_dir, tasks_dir, lanes_path=lanes_path)
    meta_json_path = planning_dir / META_JSON_FILENAME
    if meta_json_path in files_to_commit and not _mf._meta_json_delta_is_finalize_attributable(meta_json_path, repo_root):
        files_to_commit = [path for path in files_to_commit if path != meta_json_path]

    primary_files_rel = [str(path.relative_to(repo_root)) for path in files_to_commit]
    primary_dirty = bool(primary_files_rel) and _mf._finalize_candidates_dirty(repo_root, primary_files_rel)

    coord_dirt = _mf._coord_candidate_dirt(repo_root, mission_slug, owned=owned)
    seen_files = set(files_to_commit)
    for candidate in coord_dirt.files:
        if candidate not in seen_files:
            files_to_commit.append(candidate)
            seen_files.add(candidate)

    files_to_commit_rel = [_finalize_candidate_display_path(path, repo_root) for path in files_to_commit]
    return _FinalizeCommitCandidates(
        files_to_commit=files_to_commit,
        files_to_commit_rel=files_to_commit_rel,
        has_relevant_changes=primary_dirty or coord_dirt.is_dirty,
    )


def _finalize_candidate_display_path(path: Path, repo_root: Path) -> str:
    """Repo-root-relative display form of a candidate, or an absolute fallback.

    A COORD-kind candidate resolved via ``write_dir`` may live inside a
    SEPARATE coordination worktree checkout, never under ``repo_root`` — this
    is display-only (JSON ``files_committed`` / the console summary), never
    fed back into a git invocation, so an absolute fallback is honest rather
    than a crash or a misleading synthetic relative path.
    """
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _apply_finalize_commit_router_result(
    router_result: CommitRouterResult,
    outcome: _CommitOutcome,
    files_to_commit_rel: list[str],
    *,
    json_output: bool,
    updated_count: int,
) -> None:
    """Phase: fold ``commit_for_mission``'s result into ``outcome``, or refuse (T071/WP15-T082).

    Every status leg populates ``outcome.commit_surfaces``/``surface_refusal``
    (contract rule 6: the shared trio is the ONLY renderer) so a refused
    coordination surface is visible even when the top-level legacy
    ``status`` still reads ``committed`` (the PRIMARY group landed fine) --
    the caller (:func:`_run_commit_pipeline`) raises on ``surface_refusal``
    AFTER the JSON/text report has already rendered it (FR-007 exit-code
    rule: a refused/error surface must still be REPORTED, not swallowed by
    an early raise).

    WP13-review binding corrections (applied here too, first consumer):
    when ``surfaces`` is populated, :func:`render_commit_outcome`'s lines are
    printed on EVERY outcome arm -- including the legacy-error arm below --
    THEN any existing actionable error line, never the legacy diagnostic
    alone. Every rendered line is printed with ``markup=False``:
    :func:`render_commit_outcome` returns plain, untrusted-content-bearing
    strings (file paths, diagnostics), never Rich markup, so a literal ``[``
    in a path/reason must not be interpreted as a markup tag.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    from specify_cli.coordination.commit_outcome import (
        commit_outcome_exit_code,
        commit_outcome_payload,
        render_commit_outcome,
    )

    outcome.commit_surfaces = cast("list[dict[str, object]]", commit_outcome_payload(router_result)["surfaces"])
    outcome.surface_refusal = commit_outcome_exit_code(router_result) != 0
    outcome.rendered_lines = render_commit_outcome(router_result)

    def _print_surfaces() -> None:
        for line in outcome.rendered_lines:
            _mf.console.print(line, markup=False)

    if router_result.status == "committed":
        outcome.commit_hash = router_result.commit_hash
        outcome.commit_created = True
        # WP06 (#2937 / FR-009): only now is the committed set real.
        outcome.files_committed = list(files_to_commit_rel)
        outcome.commit_hashes = [{"branch": ref, "hash": commit_hash} for ref, commit_hash in router_result.commit_hashes]
        if not json_output:
            _print_surfaces()
            _mf.console.print(f"[dim]Updated {updated_count} WP files with dependencies[/dim]")
    elif router_result.status == "unchanged":
        outcome.commit_created = False
        if not json_output:
            if outcome.rendered_lines:
                _print_surfaces()
            else:
                _mf.console.print("[dim]Tasks unchanged, no commit needed[/dim]")
    else:
        error_output = router_result.diagnostic or "Failed to commit tasks updates"
        if json_output:
            print(json.dumps({"error": f"Git commit failed: {error_output}"}))
        else:
            _print_surfaces()
            _mf.console.print(f"[red]Error:[/red] Git commit failed: {error_output}")
        raise typer.Exit(1)


class OwnedCheckoutCandidateOutsidePlanningError(RuntimeError):
    """WP15 cycle 3 (fold): an owned-checkout commit candidate resolved outside
    ``planning_dir`` -- the invariant ``_commit_finalize_artifacts`` relies on
    to rewrite candidates onto the owned checkout root safely. Today this can
    only happen if ``LIFECYCLE_OWNED_TOPOLOGIES`` widens beyond
    single_branch to include a coordination-routing topology without this
    call site being updated to match.
    """


def _commit_finalize_artifacts(
    planning_dir: Path,
    tasks_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    lanes_path: Path | None,
    preexisting_primary_files: set[Path],
    *,
    json_output: bool,
    updated_count: int,
    owned: OwnedCheckout | None = None,
) -> _CommitOutcome:
    """Phase: commit finalize artifacts through commit_for_mission.

    Routes ``run_command`` through the ``mission`` module to preserve the
    ``mission.run_command`` patch seam. T027 / WP02: collapsed to the
    ``commit_for_mission`` entry point (TASKS_INDEX → primary target branch for
    every topology).
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    outcome = _CommitOutcome()
    try:
        candidates = _mf._resolve_finalize_commit_candidates(planning_dir, tasks_dir, repo_root, lanes_path, mission_slug=mission_slug, owned=owned)
        # partition-authority-residuals-01M021K9 WP06 (#2937 / FR-009): report the
        # TRUE committed set — ``files_committed`` is populated ONLY once the router
        # actually lands a commit (below), never up front. Reporting the full
        # candidate set here regardless of outcome misled automated callers on the
        # no-change / "unchanged" paths (nothing was committed, yet every candidate
        # was named as committed).
        if not candidates.has_relevant_changes:
            if not json_output:
                _mf.console.print("[dim]Tasks unchanged, no commit needed[/dim]")
            return outcome

        from specify_cli.coordination.commit_router import commit_for_mission

        files_to_commit = candidates.files_to_commit
        tasks_policy = _mf._mission_protection_policy(repo_root, mission_slug, owned)
        if owned:
            # WP15 cycle 3 (fold, non-blocking from cycle 2): ``owned.files()``
            # rewrites candidates onto the OWNED checkout root, which is sound
            # only because ``LIFECYCLE_OWNED_TOPOLOGIES`` is single_branch-only
            # today (``routes_through_coordination`` is False for it, so
            # ``_resolve_finalize_commit_candidates`` never resolves a
            # COORD-kind candidate via ``write_dir`` for an owned mission). If
            # that set ever widens to include a coordination-routing topology,
            # this guard fails loudly here instead of silently rewriting a
            # coordination path onto the wrong checkout. A bare ``assert`` is
            # stripped under ``python -O``, so this is a real, unconditional
            # raise instead.
            non_planning = [path for path in files_to_commit if not path.is_relative_to(planning_dir)]
            if non_planning:
                raise OwnedCheckoutCandidateOutsidePlanningError(
                    "owned checkout commit candidates must all resolve under planning_dir; "
                    f"LIFECYCLE_OWNED_TOPOLOGIES widened to a coordination-routing topology "
                    f"without updating this guard (offending paths: {non_planning!r})"
                )
            files_to_commit = owned.files(files_to_commit)
        # WP15/T081: ``primary_paths_created_this_invocation`` is, by name, a
        # PRIMARY-partition residue-cleanup signal -- a COORD-kind candidate
        # (resolved via ``write_dir``, never under ``planning_dir``) is never
        # "preexisting" by the ``preexisting_primary_files`` snapshot (which
        # only ever scanned ``planning_dir``), so it would otherwise be
        # misclassified as newly-created PRIMARY residue on every run.
        primary_created = frozenset(path for path in files_to_commit if path not in preexisting_primary_files and path.is_relative_to(planning_dir))
        router_result = commit_for_mission(
            repo_root=owned.repository_root if owned else repo_root,
            mission_slug=mission_slug,
            files=tuple(files_to_commit),
            message=_mf._finalize_bookkeeping_commit_message(mission_slug),
            policy=tasks_policy,
            kind=MissionArtifactKind.TASKS_INDEX,
            primary_paths_created_this_invocation=primary_created,
            target_branch=target_branch,
            owned=owned,
        )
        _apply_finalize_commit_router_result(
            router_result,
            outcome,
            candidates.files_to_commit_rel,
            json_output=json_output,
            updated_count=updated_count,
        )
    except typer.Exit:
        raise
    except Exception as e:
        if json_output:
            _mf._emit_json({"error": str(e)})
        else:
            _mf.console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1) from None
    return outcome


def _emit_success_report(
    tasks_dir: Path,
    state: _BootstrapState,
    commit_outcome: _CommitOutcome,
    dep_resolution: _DependencyResolution,
    bootstrap_result: BootstrapResult,
    lanes_manifest: LanesManifest | None,
    *,
    target_branch_override: str | None = None,
    target_branch_persist: TargetBranchPersistOutcome | None = None,
    meta_committed_this_run: bool = False,
    planning_sha: PlanningCommitResolution | None = None,
    planning_commit_refresh: dict[str, object] | None = None,
) -> None:
    """Phase: emit the terminal JSON success report.

    ``target_branch_override`` / ``target_branch_persist`` (SK3466-R-003):
    a ``--target-branch`` override durably rewrites meta.json's canonical
    merge destination, but the payload previously carried no signal that a
    mutation occurred or what the previous value was — the only observable
    trace for a ``--json`` caller was "meta.json" appearing in
    ``files_committed``, indistinguishable from any other artifact commit.
    ``target_branch_override`` is only non-``None`` when the flag was
    actually supplied this run.

    ``planning_sha`` (#4141): the ``planning_commit_sha`` decision this run
    made (captured / preserved / refreshed, the previous SHA, and the branch
    tip it was compared against), so a ``--json`` caller can see that the
    recorded SHA was preserved against a moved branch tip — and re-run with
    ``--refresh-planning-commit`` — without diffing ``lanes.json`` by hand.

    ``meta_committed_this_run`` (SK3466-REV2-002): ``persist.persisted=True``
    only means meta.json was rewritten to disk this call — it says nothing
    about whether that write survived ``_commit_finalize_artifacts``'s
    attribution check (``_meta_json_delta_is_finalize_attributable`` excludes
    meta.json entirely when a foreign field is pending alongside our
    ``target_branch`` write). A ``--json`` caller checking ``persisted``
    alone — its documented use — could not tell "durably committed" from
    "written but left dangling because it was excluded from this commit".
    Computed once by ``_run_commit_pipeline`` from ``commit_outcome.
    files_committed`` (the same value that already gates the revert-safety
    marker for SK3466-REV2-001) and passed through here rather than
    re-derived, so both corrections share one source of truth.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    persist = target_branch_persist or TargetBranchPersistOutcome(persisted=False)
    # #4141: the planning_commit_sha decision. Falls back to the manifest's
    # own SHA when no resolution was threaded through (defensive only — the
    # commit pipeline always passes one).
    _mf._emit_json(
        {
            "result": "success",
            "wp_count": len(state.work_packages),
            "updated_wp_count": state.updated_count,
            "modified_wps": state.modified_wps,
            "unchanged_wps": state.unchanged_wps,
            "preserved_wps": state.preserved_wps,
            "tasks_dir": str(tasks_dir),
            "commit_created": commit_outcome.commit_created,
            "commit_hash": commit_outcome.commit_hash,
            "commit_hashes": commit_outcome.commit_hashes,
            # WP15/FR-007 (contracts/commit-outcome.md): per-surface outcome,
            # beside the legacy caller-surface-only fields above.
            "commit_surfaces": commit_outcome.commit_surfaces,
            "files_committed": commit_outcome.files_committed,
            "dependencies_parsed": dep_resolution.wp_dependencies,
            "requirement_refs_parsed": dep_resolution.wp_requirement_refs,
            "bootstrap": {
                "total_wps": bootstrap_result.total_wps,
                "newly_seeded": bootstrap_result.newly_seeded,
                "already_initialized": bootstrap_result.already_initialized,
            },
            "lanes": {
                "computed": lanes_manifest is not None,
                "count": len(lanes_manifest.lanes) if lanes_manifest else 0,
                "lane_ids": [lane.lane_id for lane in lanes_manifest.lanes] if lanes_manifest else [],
                "planning_artifact_wps": lanes_manifest.planning_artifact_wps if lanes_manifest else [],
                "collapse_report": (lanes_manifest.collapse_report.to_dict() if lanes_manifest and lanes_manifest.collapse_report else None),
            },
            "ownership_warnings": state.ownership_warnings,
            "requirement_extraction_warnings": state.requirement_extraction_warnings,
            "post_integration_acceptance_warnings": state.post_integration_acceptance_warnings,
            "target_branch_override": {
                "requested": target_branch_override,
                "persisted": persist.persisted,
                # SK3466-REV2-002: distinct from ``persisted`` -- ``True``
                # only when meta.json's delta actually rode this commit.
                # ``persisted and not committed`` means the override is
                # written to disk but excluded from this run's commit and
                # left dangling in the working tree (mixed with a foreign
                # meta.json field also pending).
                "committed": persist.persisted and meta_committed_this_run,
                "previous_value": persist.previous_value,
                "persist_error": persist.persist_error,
            },
            "planning_commit": _mf._planning_commit_payload(planning_sha, lanes_manifest),
            # WP15/FR-012 (contracts/commit-outcome.md): the AUTOMATIC
            # refresh decision, additive and distinct from the legacy
            # ``planning_commit`` projection above.
            "planning_commit_refresh": planning_commit_refresh,
            **({"commit_diagnostic": commit_outcome.diagnostic} if commit_outcome.diagnostic is not None else {}),
            **state.requirement_diagnostics,
        }
    )


def _warn_missing_meta(planning_dir: Path, meta: dict[str, object] | None, *, json_output: bool) -> None:
    """Phase: warn (non-blocking) when meta.json is missing/malformed."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if meta is not None or json_output:
        return
    if (planning_dir / META_JSON_FILENAME).exists():
        _mf.console.print("[yellow]Warning:[/yellow] Failed to read meta.json for event emission (missing or malformed); skipping MissionCreated emission")
    else:
        _mf.console.print("[yellow]Warning:[/yellow] meta.json missing; skipping MissionCreated emission")


def _emit_tasks_started(
    mission_slug: str,
    state: _BootstrapState,
    *,
    validate_only: bool,
    repo_root: Path,
    owned: OwnedCheckout | None = None,
    status_surface: StatusSurfaceGuard | None = None,
    planning_dir: Path | None = None,
) -> None:
    """Phase: local canonical TasksStarted (idempotent; skipped in validate-only).

    ``owned`` (item 6): passes ``owned.repository_root`` so the event is written
    against the fact's repository root, never re-derived via ``get_main_repo_root``.

    WP15/T080 (FR-003, finalize bootstrap writer family): writes through
    ``PlacementSeam.write_dir(STATUS_STATE)`` — the SAME single write-location
    authority :func:`_emit_local_canonical_events` uses — rather than
    ``planning_dir`` directly. Without this, ``TasksStarted`` forked into a
    SECOND copy of the lifecycle log on the repository-root checkout even
    after the ``WPCreated``/``TasksCompleted`` leg was fixed.

    WP15 cycle 2 (B3, HIGH, FR-003a): ``write_dir`` is resolved OUTSIDE the
    best-effort ``try`` below (see :func:`_emit_local_canonical_events`'s
    identical cycle-2 fix for the full rationale) -- a named write-location
    refusal must fail finalize closed, never degrade to a silent
    ``logger.debug`` line while the event is written nowhere.

    ``status_surface`` (#5641): this is the run's first status write, so the
    guard is captured here, against the directory just resolved.
    """
    if validate_only:
        return
    from mission_runtime import placement_seam

    status_write_dir = placement_seam(repo_root, mission_slug, owned=owned).write_dir(MissionArtifactKind.STATUS_STATE).path
    if status_surface is not None and planning_dir is not None:
        _capture_status_surface(status_surface, status_write_dir, planning_dir)
    try:
        from specify_cli.status import TASKS_STARTED, emit_artifact_phase

        emit_artifact_phase(
            status_write_dir,
            event_type=TASKS_STARTED,
            mission_slug=mission_slug,
            actor=FINALIZE_TASKS_COMMAND_NAME,
            wp_count=len(state.work_packages),
            repo_root=owned.repository_root if owned else None,
        )
    except Exception as tasks_started_exc:  # noqa: BLE001 — non-blocking emission call (not the write-location resolution above)
        logger.debug("TasksStarted emission skipped: %s", tasks_started_exc)
    finally:
        if planning_dir is not None:
            from specify_cli.cli.commands.agent import mission_finalize as _mf

            _mf.note_status_files_written(planning_dir, owned.repository_root if owned else None)


def _run_commit_pipeline(
    planning_dir: Path,
    tasks_dir: Path,
    repo_root: Path,
    mission_slug: str,
    target_branch: str,
    state: _BootstrapState,
    dep_resolution: _DependencyResolution,
    wp_manifests: dict[str, OwnershipManifest],
    wp_frontmatters: dict[str, WPMetadata],
    wp_bodies: dict[str, str],
    meta: dict[str, object] | None,
    functional_spec_requirement_ids: set[str],
    preexisting_primary_files: set[Path],
    *,
    validate_only: bool,
    json_output: bool,
    target_branch_override: str | None = None,
    target_branch_persist: TargetBranchPersistOutcome | None = None,
    meta_commit_progress: _MetaBranchOverrideProgress | None = None,
    commit_landed: _FinalizeCommitLanded | None = None,
    lane_wp_dependencies: dict[str, list[str]] | None = None,
    all_canceled: bool = False,
    owned: OwnedCheckout | None = None,
    refresh_planning_commit: bool = False,
    allow_orphaned: bool = False,
    planning_sha: PlanningCommitResolution | None = None,
    status_surface: StatusSurfaceGuard | None = None,
    frozen: FrozenLaneMembership | None = None,
) -> None:
    """Phase: the post-validate-only commit pipeline.

    Seeds canonical state, computes lanes, scaffolds acceptance-matrix, syncs the
    dossier, commits artifacts, emits SaaS WPCreated, and reports success. Only
    ever reached when ``not validate_only`` (INV-6).

    A ``--target-branch`` override that just rewrote meta.json
    (:func:`_persist_target_branch_override`) — or one dangling from a prior
    crashed run (SK3466-RR-001) — is folded into the SAME finalize commit as
    tasks.md / WP files below, because :func:`_collect_finalize_artifacts`
    treats meta.json as a commit candidate and :func:`_commit_finalize_
    artifacts` attributes any pending delta by field
    (SK3466-REV-001: a delta confined to ``target_branch`` rides this commit
    regardless of which run produced it; a delta ALSO touching a foreign
    field, e.g. a concurrent ``implement --no-auto-commit`` write, is
    excluded from this commit entirely). Nothing in this phase needs to know
    whether THIS invocation's own persist call fired.

    ``target_branch_override`` / ``target_branch_persist`` are threaded
    through only to ``_emit_success_report`` (SK3466-R-003 JSON traceability)
    and do not affect this phase's own behavior.

    ``meta_commit_progress`` (SK3466-R-001, corrected SK3466-REV2-001): once
    ``_commit_finalize_artifacts`` below returns, flipped to
    ``committed=True`` only when meta.json's own relative path actually
    appears in ``commit_outcome.files_committed`` -- NOT unconditionally.
    ``_meta_json_delta_is_finalize_attributable`` can exclude meta.json from
    this commit entirely (a foreign field, e.g. ``implement
    --no-auto-commit``'s ``vcs``/``vcs_locked_at`` write, is pending
    alongside our ``target_branch`` write); an unconditional flip in that
    case fooled ``_revert_unpersisted_target_branch_override``'s ``not
    meta_commit_progress.committed`` guard into skipping a real revert when a
    LATER step in this function (SaaS emission, the JSON report) goes on to
    raise, leaving a permanently dangling meta.json write. Reading
    ``commit_outcome.files_committed`` -- a value ``_commit_finalize_
    artifacts`` already computes -- needs no new state to close this.

    ``commit_landed`` (review cycle 1, HIGH-1): flipped the moment
    ``_commit_finalize_artifacts`` returns with a real commit, regardless of
    whether meta.json rode it. The FR-015/NFR-001 atomicity guards in
    ``finalize_tasks`` key off this marker, NOT ``meta_commit_progress``.

    ``status_surface`` (#5641): captured by ``_emit_tasks_started`` before the
    run's first status write; its tip is recorded when the status-write window below
    closes (also on an error, so a bootstrap that raises part-way is covered);
    ``finalize_tasks`` restores it when the finalize commit never lands.
    """
    from specify_cli.cli.commands.agent import mission_finalize as _mf

    # #5641: every status-surface commit before the final commit -- the per-WP
    # seeds, and on a coordination surface the acceptance-matrix scaffold -- lands
    # inside this window, so the guard records the tip once it closes.
    with status_surface.recording() if status_surface is not None else contextlib.nullcontext():
        _mf._emit_local_canonical_events(planning_dir, mission_slug, repo_root, state.work_packages, json_output=json_output, owned=owned)

        bootstrap_result = _mf._bootstrap_canonical_state_via_mission(
            planning_dir,
            mission_slug,
            dry_run=False,
            capability=GuardCapability.STANDARD,
            **({"owned": owned} if owned else {}),
        )
        if not json_output and bootstrap_result.newly_seeded:
            _mf.console.print(f"[green]✓[/green] Bootstrapped canonical status: {bootstrap_result.newly_seeded} WPs seeded")

        lanes_path, lanes_manifest, planning_sha = _mf._compute_and_write_lanes(
            planning_dir,
            repo_root,
            mission_slug,
            wp_manifests,
            lane_wp_dependencies if lane_wp_dependencies is not None else dep_resolution.wp_dependencies,
            wp_frontmatters,
            wp_bodies,
            meta,
            target_branch,
            all_canceled=all_canceled,
            json_output=json_output,
            owned=owned,
            refresh_planning_commit=refresh_planning_commit,
            allow_orphaned=allow_orphaned,
            planning_sha=planning_sha,
            frozen=frozen,
        )

        _mf._scaffold_acceptance_matrix_if_lane_based(
            planning_dir,
            repo_root,
            mission_slug,
            lanes_manifest,
            functional_spec_requirement_ids,
            validate_only=validate_only,
            json_output=json_output,
            **({"owned": owned} if owned else {}),
        )

    commit_outcome = _commit_finalize_artifacts(
        planning_dir,
        tasks_dir,
        repo_root,
        mission_slug,
        target_branch,
        lanes_path,
        preexisting_primary_files,
        json_output=json_output,
        updated_count=state.updated_count,
        **({"owned": owned} if owned else {}),
    )
    # SK3466-REV2-001/002: whether meta.json's own delta actually rode this
    # commit -- NOT "the phase returned without raising". Computed once here
    # (the exact same relative-path form _commit_finalize_artifacts used to
    # build ``commit_outcome.files_committed``) and reused below for both the
    # revert-safety marker and the terminal report, so the two call sites
    # this Op's round 3 left behind learn about the same third outcome state
    # from a single source rather than two independent guesses.
    if commit_landed is not None:
        # Independent of meta.json attribution: the atomicity guards must see
        # a landed commit even when meta.json was excluded from it.
        commit_landed.landed = commit_outcome.commit_created
    meta_json_rel = str((planning_dir / META_JSON_FILENAME).relative_to(repo_root))
    meta_committed_this_run = meta_json_rel in commit_outcome.files_committed
    if meta_commit_progress is not None:
        # SK3466-R-001, corrected SK3466-REV2-001: only durable once
        # meta.json's delta actually folded into this commit -- an
        # unconditional flip here fooled the revert guard below
        # (``not meta_commit_progress.committed``) into skipping a real
        # revert when ``_meta_json_delta_is_finalize_attributable`` excluded
        # meta.json for being mixed with a foreign field.
        meta_commit_progress.committed = meta_committed_this_run
    if not json_output and target_branch_persist is not None and target_branch_persist.persisted and not meta_committed_this_run:
        # SK3466-REV2-002: the "persisted to meta.json" note already printed
        # by ``_persist_target_branch_override`` ran before this commit's
        # attribution decision was known, so a mixed-delta exclusion left no
        # console trace distinguishing "committed" from "written but still
        # dangling". This corrective note fires only in that gap.
        _mf.console.print(
            "[yellow]Note:[/yellow] the --target-branch override written to meta.json "
            "was excluded from this commit (a foreign meta.json edit is pending "
            "alongside it) and remains an uncommitted working-tree change."
        )

    if json_output:
        _mf._emit_success_report(
            tasks_dir,
            state,
            commit_outcome,
            dep_resolution,
            bootstrap_result,
            lanes_manifest,
            target_branch_override=target_branch_override,
            target_branch_persist=target_branch_persist,
            meta_committed_this_run=meta_committed_this_run,
            planning_sha=planning_sha,
            planning_commit_refresh=_mf._planning_commit_refresh_payload(planning_sha),
        )
    # Non-JSON mode: the refresh decision (including a ``kept_with_warning``
    # console WARN) was already reported inside ``_compute_and_write_lanes``
    # via ``_report_planning_sha_decision`` -- nothing further to print here.

    # WP15/T082 (FR-007 exit-code rule): a refused/error coordination surface
    # exits non-zero even though the top-level legacy status above may have
    # reported "committed" (the PRIMARY group landed). Raised AFTER the
    # success report so a refused surface is reported, never swallowed.
    if commit_outcome.surface_refusal:
        raise typer.Exit(1)


@dataclass
class _FinalizeCommitLanded:
    """Mutable marker: the single final finalize commit has landed (FR-015/NFR-001).

    Deliberately SEPARATE from :attr:`_MetaBranchOverrideProgress.committed`,
    which only says "meta.json's delta rode the commit" (SK3466 attribution).
    When a foreign field (e.g. ``implement --no-auto-commit``'s ``vcs``) is
    pending in meta.json, that file is excluded from the commit, so that flag
    stays ``False`` although the commit DID land. The mission-directory /
    derived-cache / HEAD atomicity guards must key off THIS marker: a later
    failure after a durable commit must never unwind it. Mutated in place from
    ``_run_commit_pipeline`` for the same reason the sibling marker is.
    """

    landed: bool = False


#: The ``warning`` key of the note naming files the restore kept.
WRITE_SCOPE_KEPT_WARNING = "write_scope_files_kept_changed_by_another_writer"

#: The note for a ``meta.json`` the revert left alone because another writer changed it after this run wrote it.
_META_CHANGED_BY_ANOTHER_WRITER = "{path} was changed by another writer after finalize-tasks wrote it; kept as is, not reverted"


@dataclass
class _MetaBranchOverrideProgress:
    """Mutable revert-safety marker for a persisted ``--target-branch`` write (SK3466-R-001).

    Mutated in place from inside ``_run_commit_pipeline`` (not communicated
    via a return value) so its state survives even when a LATER, unrelated
    phase raises AFTER the meta.json write has already been folded into the
    finalize commit. A return value alone cannot do this: if
    ``_emit_success_report`` raised after
    ``_commit_finalize_artifacts`` had already committed successfully, but
    before ``_run_commit_pipeline`` returned, the caller would never observe
    an "already committed" return and would incorrectly revert meta.json —
    reintroducing a fresh, uncommitted diff on top of an already-green
    commit. Mutating this shared object instead means the caller's
    ``except`` handler still sees ``committed=True`` no matter where past
    that point the exception originated.
    """

    committed: bool = False


def _revert_unpersisted_target_branch_override(
    meta_path: Path | None,
    original_text: str | None,
    *,
    meta_json_persisted: bool,
    meta_commit_progress: _MetaBranchOverrideProgress,
    written_text: str | None = None,
) -> str | None:
    """Undo an applied-but-uncommitted ``--target-branch`` meta.json write (SK3466-R-001).

    ``_persist_target_branch_override`` writes meta.json to disk as soon as
    the override differs from the on-disk value — well before roughly eight
    downstream validation gates (missing ``tasks_dir``, dependency-cycle,
    requirement-mapping, ownership, ...) that can still raise
    ``typer.Exit(1)``. Without this guard, a run that failed one of those
    gates left meta.json mutated and uncommitted in the working tree,
    contradicting the invariant :func:`_collect_finalize_artifacts` exists to
    uphold: a persisted override lands in the SAME commit as tasks.md / the
    WP files, or not at all — never as a dangling, uncommitted edit.

    A no-op unless the write actually happened this run (``meta_json_
    persisted``) AND it was never folded into the finalize commit
    (``not meta_commit_progress.committed``) AND the pre-write content was
    captured.

    With *written_text* (the text this run wrote, mission-writer-followups plan A8) the
    revert is a compare-and-swap inside the Mission write lock: it acts only while
    ``meta.json`` still holds exactly that text, so another writer's later change is never
    clobbered. When it changed, nothing is written and the returned string says so.

    Returns:
        ``None`` on success or on a no-op. A non-``None`` string
        (SK3466-RR-003) describes the revert WRITE's OWN failure — e.g. a
        permission change, a full disk, or the same TOCTOU class this
        function's caller already reasons about (meta.json deleted/replaced
        between the persist and this revert attempt). Without this, a
        SECOND, unrelated exception raised from inside ``mission_metadata.
        restore_meta_text``'s own write would propagate out of one of
        ``finalize_tasks``'s ``except`` handlers uncaught — replacing the
        graceful ``{"error": str(e)}``
        JSON-output contract the rest of this fix guarantees with an
        unhandled Python traceback for a ``--json`` caller. Callers report
        the ORIGINAL exception regardless; this is a best-effort ADDITIONAL
        note.
    """
    if not (meta_json_persisted and not meta_commit_progress.committed and original_text is not None and meta_path is not None):
        return None
    from specify_cli.mission_metadata import restore_meta_text

    try:
        # Routed through mission_metadata.py's byte-exact rollback primitive
        # (T025 single-writer gate) rather than a direct ``meta_path.
        # write_text`` here -- this module must not become a second writer of
        # meta.json, the very defect class this fix's history (SK3466-R-001)
        # exists to close. ``restore_meta_text`` guarantees the SAME
        # byte-exact restore this call site always relied on; see its
        # docstring for why ``write_meta`` (re-serialize from a parsed dict)
        # cannot make that guarantee.
        restored = restore_meta_text(meta_path.parent, original_text, expected_current=written_text)
    except OSError as revert_exc:
        logger.warning(
            "SK3466-RR-003: failed to revert unpersisted target_branch override in %s: %s",
            meta_path,
            revert_exc,
        )
        return str(revert_exc)
    if not restored:
        return _META_CHANGED_BY_ANOTHER_WRITER.format(path=meta_path)
    return None


def _report_target_branch_revert_failure(revert_error: str | None, *, json_output: bool) -> None:
    """Phase: best-effort surfacing of a failed meta.json revert (SK3466-RR-003).

    A no-op unless the revert write itself failed. Used from ``finalize_
    tasks``'s ``except typer.Exit`` handler, where the ORIGINAL error already
    emitted its own diagnostic before raising — this is purely an additional
    note, never a substitute for it.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if not revert_error:
        return
    if json_output:
        _mf._emit_json({"warning": "target_branch_override_revert_failed", "detail": revert_error})
    else:
        _mf.console.print(f"[yellow]Warning:[/yellow] failed to revert unpersisted --target-branch override in meta.json: {revert_error}")


def _emit_finalize_error_with_revert_note(
    error: Exception,
    revert_error: str | None,
    *,
    json_output: bool,
    status_leftover: StatusSurfaceLeftover | None = None,
    kept_files: list[Path] | None = None,
) -> None:
    """Phase: emit finalize_tasks's terminal error, folding in a revert-failure note (SK3466-RR-003).

    Preserves the existing ``{"error": str(e)}`` / ``[red]Error:[/red]``
    diagnostic contract for the ORIGINAL exception unconditionally; the
    meta.json-revert failure (if any) is added as a SECOND, clearly-labelled
    field/line rather than replacing it.
    """
    from specify_cli.cli.commands.agent import mission_finalize as _mf

    from specify_cli.lanes.compute import LaneDependencyCycleError, LaneMembershipFrozenError

    if json_output:
        error_payload: dict[str, object] = {"error": str(error)}
        if isinstance(error, ActionContextError):
            error_payload["error_code"] = error.code
        if isinstance(error, LaneMembershipFrozenError):
            error_payload.update(
                {
                    "error_code": error.error_code,
                    "reason": error.reason,
                    "conflicts": [conflict.to_dict() for conflict in error.conflicts],
                    "next_step": error.next_step,
                }
            )
        if isinstance(error, LaneDependencyCycleError):
            error_payload.update(
                {
                    "error_code": error.error_code,
                    "cycle_path": list(error.cycle_path),
                    "cycle_lanes": [
                        {
                            "lane_id": lane.lane_id,
                            "wp_ids": list(lane.wp_ids),
                        }
                        for lane in error.cycle_lanes
                    ],
                }
            )
        if revert_error:
            error_payload["target_branch_override_revert_error"] = revert_error
        if status_leftover is not None:
            # #5641: one envelope on this path, like the meta.json revert note.
            error_payload["status_commits_not_undone"] = status_leftover.as_payload()
        if kept_files:
            # Plan A8: files another writer changed after the run wrote them were kept, not reverted.
            error_payload["write_scope_kept_changed_by_another_writer"] = [str(path) for path in kept_files]
        _mf._emit_json(error_payload)
        return
    _mf.console.print(f"[red]Error:[/red] {error}")
    if isinstance(error, LaneDependencyCycleError):
        _mf.console.print(f"  Cycle path: {' -> '.join(error.cycle_path)}")
        for lane in error.cycle_lanes:
            _mf.console.print(f"  {lane.lane_id}: {', '.join(lane.wp_ids)}")
    if isinstance(error, LaneMembershipFrozenError):
        _print_membership_conflicts(error)
    if revert_error:
        _mf.console.print(f"[yellow]Warning:[/yellow] failed to revert unpersisted --target-branch override in meta.json: {revert_error}")
    _report_status_surface_leftover(status_leftover, json_output=False)
    _report_write_scope_kept(kept_files or [], json_output=False)


def _print_membership_conflicts(error: LaneMembershipFrozenError) -> None:
    """Console form of a ``LANE_MEMBERSHIP_FROZEN`` refusal: one line per conflict plus its remedy (#5573)."""
    from specify_cli.cli.commands.agent import mission_finalize as _mf

    for conflict in error.conflicts:
        named = ", ".join(f"{wp_id} ({lane_id})" for wp_id, lane_id in conflict.pairs) or ", ".join(conflict.wp_ids)
        _mf.console.print(f"  {conflict.reason}: {named}" if named else f"  {conflict.reason}")
        _mf.console.print(f"  Remedy: {conflict.remedy}")


def _mission_write_scope_files(mission_dir: Path) -> set[Path]:
    """Every file under ``mission_dir`` this guard tracks, excluding ``meta.json``.

    ``meta.json`` is excluded deliberately: it already has its own
    byte-exact, single-writer-gated revert path
    (:func:`_revert_unpersisted_target_branch_override`, routed through
    ``mission_metadata.restore_meta_text``), and a second writer here would
    contradict that primitive's single-writer guarantee (T025).
    """
    if not mission_dir.exists():
        return set()
    return {path for path in mission_dir.rglob("*") if path.is_file() and path.name != META_JSON_FILENAME}


def _snapshot_mission_write_scope(mission_dir: Path) -> dict[Path, bytes]:
    """Byte-snapshot every tracked file under ``mission_dir`` (FR-015/NFR-001).

    Read by :func:`_restore_mission_write_scope` so a failed
    ``finalize_tasks`` run leaves the mission directory exactly as it found
    it, even though several writes (WP frontmatter, ``tasks.md``, the issue
    matrix, canonical status events) land on disk before every ordered
    fail-closed gate has run (R-07). A not-yet-existing ``mission_dir``
    snapshots as empty rather than raising.
    """
    return {path: path.read_bytes() for path in _mission_write_scope_files(mission_dir)}


class FinalizeWriteLedger:
    """The exact bytes one finalize run wrote, per file (mission-writer-followups plan A8, FR-003).

    Every write finalize makes through :func:`kernel.atomic.atomic_write` is recorded at the moment it
    happens (the writers hold the Mission write lock then), and the status files finalize's emissions
    touched are noted by :func:`note_status_files_written`. The write-scope restore acts on a path only
    when it is in the ledger and the file still holds the recorded bytes: a file finalize never wrote,
    or one another writer changed since, is never put back.
    """

    def __init__(self) -> None:
        self.written: dict[Path, bytes] = {}

    def record(self, path: Path, content: bytes) -> None:
        """Remember that *path* now holds *content* (the latest write of the run wins)."""
        self.written[path.resolve()] = content

    def text_for(self, path: Path) -> str | None:
        """The text the run last wrote to *path*, or ``None`` when it wrote nothing there."""
        content = self.written.get(path.resolve())
        return content.decode("utf-8") if content is not None else None


_ACTIVE_LEDGER: ContextVar[FinalizeWriteLedger | None] = ContextVar("finalize_write_ledger", default=None)


def begin_write_ledger() -> tuple[FinalizeWriteLedger, Token[FinalizeWriteLedger | None], Token[Callable[[Path, bytes], None] | None]]:
    """Start recording this run's writes; hand the tokens to :func:`end_write_ledger`."""
    ledger = FinalizeWriteLedger()
    return ledger, _ACTIVE_LEDGER.set(ledger), observe_writes(ledger.record)


def end_write_ledger(ledger_token: Token[FinalizeWriteLedger | None], observer_token: Token[Callable[[Path, bytes], None] | None]) -> None:
    """Stop recording the run's writes."""
    stop_observing_writes(observer_token)
    _ACTIVE_LEDGER.reset(ledger_token)


def active_write_ledger() -> FinalizeWriteLedger | None:
    """The ledger of the finalize run in progress in this context, if any."""
    return _ACTIVE_LEDGER.get()


def note_status_files_written(planning_dir: Path, repo_root: Path | None = None) -> None:
    """Record the Mission's in-directory status files as finalize's emissions left them.

    Status rows are appended, not atomically replaced, so the ledger reads the files back right after the
    emission, inside the Mission write lock. A no-op outside a finalize run.
    """
    ledger = _ACTIVE_LEDGER.get()
    if ledger is None:
        return
    with mission_write_lock(planning_dir, repo_root=repo_root):
        for name in _STATUS_FILE_NAMES:
            content = _bytes_or_none(planning_dir / name)
            if content is not None:
                ledger.record(planning_dir / name, content)


#: The in-directory status files a finalize emission writes by appending.
_STATUS_FILE_NAMES: Final = ("status.events.jsonl", "status.json")


def _bytes_or_none(path: Path) -> bytes | None:
    """The bytes at *path*, or ``None`` when it is not a readable file."""
    try:
        return path.read_bytes()
    except OSError:
        return None


def _restore_mission_write_scope(
    before: dict[Path, bytes],
    mission_dir: Path,
    *,
    written: dict[Path, bytes] | None = None,
    keep: frozenset[Path] = frozenset(),
    keep_under: Path | None = None,
    lock_dir: Path | None = None,
    repo_root: Path | None = None,
) -> list[Path]:
    """Undo every tracked write under ``mission_dir`` since the matching snapshot (FR-015/NFR-001).

    A file present in ``before`` is rewritten to its original bytes; a file
    that now exists under ``mission_dir`` but was absent from ``before``
    (created by the failed attempt) is deleted. A file in ``keep`` (resolved
    paths a commit left on the status branch changed), or anywhere under
    ``keep_under`` (the status directory, when those paths could not be listed),
    is neither rewritten nor deleted: it is that commit's, not this attempt's.
    Each path is restored independently and a failure is logged, never raised --
    this is best-effort cleanup alongside the ORIGINAL exception that triggered
    it, never a replacement diagnostic for it.

    Compare-and-swap (mission-writer-followups plan A8): the whole restore runs inside the
    Mission write lock. With ``written`` (the ledger of the bytes this attempt wrote, keyed
    by resolved path) a file is rewritten or deleted only while its bytes still equal
    what the attempt wrote there; a file the attempt never wrote, or one another writer
    changed since, is neither rewritten nor deleted: it is kept and returned (sorted), so
    the caller can report it. A file that is already gone is put back whatever the ledger
    says. Without ``written`` every changed file is undone (a status directory the status
    guard restores by its own compare-and-swap).

    The lock is the Mission write lock of ``lock_dir`` (``mission_dir`` by default): a directory
    that is not a Mission directory (the owned checkout's derived view) takes its Mission's lock
    rather than minting a lock beside itself.
    """
    keep_root = keep_under.resolve() if keep_under is not None else None

    def _is_kept(path: Path) -> bool:
        resolved = path.resolve()
        return resolved in keep or (keep_root is not None and resolved.is_relative_to(keep_root))

    kept_changed: list[Path] = []
    with mission_write_lock(lock_dir or mission_dir, repo_root=repo_root):
        current = _mission_write_scope_files(mission_dir)
        for path in sorted(set(before) | current):
            if _is_kept(path):
                continue
            original = before.get(path)
            now = _bytes_or_none(path)
            if now == original:
                continue  # already as it was before the attempt (for example restored with the status branch)
            if written is not None and now is not None and now != written.get(path.resolve(), None):
                kept_changed.append(path)  # not what finalize wrote: another writer's change, left alone
                continue
            _undo_one_path(path, original)
    return sorted(kept_changed)


def _undo_one_path(path: Path, original: bytes | None) -> None:
    """Put *path* back to *original*, or remove it when the attempt created it; a failure is logged, never raised."""
    try:
        if original is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original)
    except OSError as exc:
        logger.warning("finalize atomicity: failed to restore %s: %s", path, exc)


def _restore_mission_write_scope_beside_status(
    guard: StatusSurfaceGuard,
    before: dict[Path, bytes],
    mission_dir: Path,
    *,
    written: dict[Path, bytes] | None = None,
) -> list[Path]:
    """:func:`_restore_mission_write_scope`, leaving what the status branch kept as it is (#5641).

    The files a kept commit changed stay; when git cannot list them, so does
    everything under the status directory -- fail closed, never the rewrite.
    Returns the files another writer changed since the attempt (kept, plan A8).
    """
    kept = guard.kept_paths()
    return _restore_mission_write_scope(before, mission_dir, written=written, keep=kept or frozenset(), keep_under=guard.status_dir if kept is None else None)


def _undo_finalize_write_scope(
    guard: StatusSurfaceGuard,
    snapshot: dict[Path, bytes],
    mission_dir: Path,
    *,
    owned_derived_snapshot: dict[Path, bytes],
    owned_derived_dir: Path | None,
    ledger: FinalizeWriteLedger | None = None,
) -> tuple[StatusSurfaceLeftover | None, list[Path]]:
    """Undo a refused run's writes: the status commits first, then the Mission directory (and the owned derived view).

    The restore acts only on what the run's write ledger (the active one unless *ledger* is given) says
    finalize wrote, as a compare-and-swap inside the Mission write lock (plan A8, FR-003): a file finalize
    never wrote, or one another writer changed since, is kept. Returns what the status surface could not
    undo and the files kept.
    """
    ledger = ledger or active_write_ledger() or FinalizeWriteLedger()
    leftover = _restore_status_surface(guard)
    kept = _restore_mission_write_scope_beside_status(guard, snapshot, mission_dir, written=ledger.written)
    if owned_derived_dir is not None:
        kept.extend(_restore_mission_write_scope(owned_derived_snapshot, owned_derived_dir, written=ledger.written, lock_dir=mission_dir))
    return leftover, kept


def _report_write_scope_kept(kept: list[Path], *, json_output: bool) -> None:
    """Name the files the write-scope restore left alone because another writer changed them (plan A8)."""
    if not kept:
        return
    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if json_output:
        _mf._emit_json({"warning": WRITE_SCOPE_KEPT_WARNING, "files": [str(path) for path in kept]})
        return
    _mf.console.print(f"[yellow]Warning:[/yellow] {len(kept)} file(s) were changed by another writer after finalize-tasks wrote them and were kept, not reverted:")
    for path in kept:
        _mf.console.print(f"  {path}")


def _capture_status_surface(guard: StatusSurfaceGuard, status_dir: Path, planning_dir: Path) -> None:
    """Capture the status surface just before the run's first status write (#5641).

    ``status_dir`` is the directory the writer itself just resolved through
    ``PlacementSeam.write_dir(STATUS_STATE)``, so capturing costs no second
    resolution. Its bytes are snapshotted here only when it lies outside
    ``planning_dir`` (the coordination worktree); otherwise the Mission
    directory snapshot already holds them.
    """
    inside_mission_dir = status_dir.resolve().is_relative_to(planning_dir.resolve())
    guard.capture(status_dir, None if inside_mission_dir else _snapshot_mission_write_scope(status_dir))


def _restore_status_surface(guard: StatusSurfaceGuard) -> StatusSurfaceLeftover | None:
    """Undo the status commits of a run whose finalize commit never landed (FR-015/NFR-001, #5641).

    Runs BEFORE :func:`_restore_mission_write_scope_beside_status`, which then skips the files
    of any commit the guard kept (``guard.kept_paths()``): on a repository-root
    status surface (``lanes`` / ``single_branch``, an owned checkout) the status
    files either go back with the branch or stay exactly as the kept commits
    left them, never modified against their own HEAD. A status directory outside
    the Mission directory (the coordination worktree) gets its bytes back only
    once its branch did, so a refused restore never leaves that worktree
    diverged from its own HEAD. Best-effort like the other restore helpers:
    returns what it could not undo, never raises.
    """
    leftover = guard.restore()
    if guard.status_bytes is not None and guard.status_dir is not None and guard.is_at_tip_before():
        _restore_mission_write_scope(guard.status_bytes, guard.status_dir)
    return leftover


def _report_status_surface_leftover(leftover: StatusSurfaceLeftover | None, *, json_output: bool) -> None:
    """Name the status commits a failed run could not undo (#5641); an additional note, never the error itself."""
    if leftover is None:
        return
    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if json_output:
        _mf._emit_json(leftover.as_payload())
        return
    for line in leftover.lines():
        _mf.console.print(f"[yellow]Warning:[/yellow] {line}" if not line.startswith(" ") else line)
