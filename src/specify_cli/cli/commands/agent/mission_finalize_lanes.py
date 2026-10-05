"""``finalize-tasks`` phase: lane computation and the acceptance-matrix scaffold.

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

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from mission_runtime import MissionArtifactKind, MissionTopology, TopologyManifestMismatch
from mission_runtime import OwnedCheckout
from specify_cli.lanes.models import LanesManifest
from specify_cli.ownership.models import OwnershipManifest
from specify_cli.status import WPMetadata
from specify_cli.cli.commands.agent.mission_finalize_seams import logger

if TYPE_CHECKING:
    from specify_cli.cli.commands.agent.mission_finalize_planning_pin import PlanningCommitResolution
    from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
    from specify_cli.lanes.compute import LaneMembershipFrozenError
    from specify_cli.lanes.frozen_membership import FrozenLaneMembership


def _cause_detail(cause: BaseException) -> str:
    """The cause's own message, plus its ``next_step`` when the message does not already carry it."""
    detail = str(cause) or type(cause).__name__
    next_step = getattr(cause, "next_step", None)
    if isinstance(next_step, str) and next_step and next_step not in detail:
        detail = f"{detail} {next_step}"
    return detail


def _status_unreadable_error(cause: BaseException) -> LaneMembershipFrozenError:
    """Build the ``status_unreadable`` refusal (#5573 FR-007) for *cause*; the caller chains it.

    The remedy keeps the cause's diagnostic. An unmaterialized coordination
    worktree (#4959) leads with materializing it, in the canonical
    :class:`~specify_cli.coordination.surface_resolver.CoordinationWorktreeUnmaterialized`
    wording, because repairing the status log is not the fix there.
    """
    from specify_cli.coordination.surface_resolver import CoordinationWorktreeUnmaterialized
    from specify_cli.lanes.compute import LaneMembershipFrozenError
    from specify_cli.lanes.frozen_membership import MembershipConflict, remedy_for

    if isinstance(cause, CoordinationWorktreeUnmaterialized):
        remedy = f"Materialize the coordination worktree, then re-run finalize-tasks. {cause.next_step}"
    else:
        remedy = f"{remedy_for('status_unreadable', ())} Cause: {_cause_detail(cause)}"
    conflict = MembershipConflict(reason="status_unreadable", wp_ids=(), recorded_lanes=(), remedy=remedy)
    error: LaneMembershipFrozenError = LaneMembershipFrozenError((conflict,))
    return error


def _missing_status_surface_cause(repo_root: Path, mission_slug: str, read_dir: Path, *, owned: OwnedCheckout | None) -> Exception:
    """Explain why the resolved status dir does not exist, through the canonical fail-closed read (#4959).

    The status-surface resolver composes a coordination path even when that
    worktree was never materialized; the placement seam's ``read_dir`` is the
    fail-closed reader that names the state (``CoordinationWorktreeUnmaterialized``,
    whose ``next_step`` distinguishes a local from a remote-only branch). A
    ``ValueError`` or ``FileNotFoundError`` from that read (meta resolution) is
    the cause itself. When the seam raises nothing, the missing directory
    itself is the cause.
    """
    from mission_runtime import placement_seam

    from specify_cli.missions._read_path_resolver import StatusReadPathNotFound

    try:
        placement_seam(owned.repository_root if owned else repo_root, mission_slug, owned=owned).read_dir(MissionArtifactKind.STATUS_STATE)
    except StatusReadPathNotFound as exc:
        # ``specify_cli.missions`` is outside mypy's scope, so name the type here.
        canonical: Exception = exc
        return canonical
    except (ValueError, FileNotFoundError) as exc:
        # The meta resolution itself failed: fail closed with that cause.
        return exc
    return FileNotFoundError(f"The status surface {read_dir} does not exist, so the status history cannot be read.")


def _committed_coordination_log(cause: CoordinationWorktreeUnmaterialized) -> bytes:
    """Bytes of the status log committed on the LOCAL coordination branch the unmaterialized worktree would check out.

    Read-only (``git ls-tree`` then ``git cat-file``, the same pair
    :mod:`specify_cli.coordination.status_surface_guard` reads a committed log
    with); never materializes the worktree. The in-branch path is the
    canonical coordination mission dir the error carries
    (``coord_candidate``), relative to the coordination worktree root.

    Raises:
        LaneMembershipFrozenError: ``status_unreadable`` -- the branch is not a
            local head (remote-only or gone) or the candidate lies outside the
            coordination worktree (the remedy keeps the canonical materialize
            guidance, including its fetch step), the branch carries no
            committed status log although a lane manifest exists, or git failed.
    """
    from kernel.git import GitCommandError, run_git, tree_entry
    from specify_cli.coordination.workspace import CoordinationWorkspace
    from specify_cli.status import EVENTS_FILENAME

    worktree_root: Path = CoordinationWorkspace.worktree_path(cause.repo_root, cause.mission_slug, cause.mid8)
    try:
        relative = (Path(cause.coord_candidate) / EVENTS_FILENAME).relative_to(worktree_root).as_posix()
        entry = tree_entry(cause.repo_root, f"refs/heads/{cause.coordination_branch}", relative)
    except (ValueError, GitCommandError):
        # The unmaterialized state is the cause: its remedy names the fix.
        raise _status_unreadable_error(cause) from cause
    if entry is None:
        missing = FileNotFoundError(f"The coordination branch {cause.coordination_branch!r} has no committed {relative}, so the status history cannot be read.")
        raise _status_unreadable_error(missing) from missing
    try:
        blob: bytes = run_git(cause.repo_root, "cat-file", "blob", entry.oid).stdout
    except GitCommandError as exc:
        raise _status_unreadable_error(exc) from exc
    return blob


def _started_on_coordination_branch(cause: CoordinationWorktreeUnmaterialized) -> frozenset[str]:
    """The history-started WPs read from the committed coordination status log (#5573, read-only, fail-closed).

    Parsed with the canonical status store parser; a malformed log or bad
    encoding raises the ``status_unreadable`` refusal.
    """
    from specify_cli.lanes.frozen_membership import started_wp_ids
    from specify_cli.status import StoreError, read_events_from_text

    blob = _committed_coordination_log(cause)
    try:
        started: frozenset[str] = started_wp_ids(read_events_from_text(Path(cause.primary_candidate), blob.decode("utf-8")))
    except (StoreError, UnicodeDecodeError) as exc:
        raise _status_unreadable_error(exc) from exc
    return started


def _read_started_wp_ids(repo_root: Path, mission_slug: str, *, owned: OwnedCheckout | None) -> frozenset[str]:
    """Read the history-started WPs from the status log, read-only and fail-closed (#5573 FR-007).

    An absent event log in an existing status dir means nothing started. A
    coordination worktree that is not materialized (#4959) is read from the
    log committed on its local coordination branch
    (:func:`_started_on_coordination_branch`), never by materializing it. An
    unresolvable status surface, any other status dir that does not exist,
    a coordination branch that cannot be read locally, or an unreadable log
    (malformed line, bad encoding, I/O error) raises the
    ``status_unreadable`` refusal: with a lane manifest on disk, "unknown"
    must never read as "nothing started". Never calls ``materialize()``.
    """
    from specify_cli.cli.commands.agent import mission_finalize as _mf

    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted, CoordinationWorktreeUnmaterialized, StatusReadPathNotFound
    from specify_cli.lanes.frozen_membership import started_wp_ids
    from specify_cli.status import StoreError, has_event_log, read_events

    try:
        read_dir = _mf._resolve_status_read_dir(repo_root, mission_slug, owned=owned)
    except (FileNotFoundError, ValueError, StatusReadPathNotFound, CoordinationBranchDeleted) as exc:
        raise _status_unreadable_error(exc) from exc
    if not read_dir.is_dir():
        # #4959: an absent surface is not an absent log ("nothing started").
        cause = _missing_status_surface_cause(repo_root, mission_slug, read_dir, owned=owned)
        if isinstance(cause, CoordinationWorktreeUnmaterialized):
            return _started_on_coordination_branch(cause)
        raise _status_unreadable_error(cause) from cause
    try:
        if not has_event_log(read_dir):
            return frozenset()
        started: frozenset[str] = started_wp_ids(read_events(read_dir))
    except (StoreError, UnicodeDecodeError, OSError) as exc:
        raise _status_unreadable_error(exc) from exc
    return started


def _gather_frozen_lane_membership(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    *,
    wp_frontmatters: dict[str, WPMetadata],
    eligible_wp_ids: frozenset[str],
    owned: OwnedCheckout | None = None,
) -> FrozenLaneMembership:
    """Gather the evidence for the frozen lane membership of started WPs (#5573).

    A first finalize (no ``lanes.json``) reads nothing and constrains nothing.
    Otherwise the started set comes from the status history
    (:func:`_read_started_wp_ids`, fail-closed), and the recorded lane work
    tips are listed (one git call): they are both the fallback evidence for a
    lane without a history-started member and the source of the lane ids kept
    reserved after a lane leaves the manifest. A listing git cannot produce
    refuses with ``status_unreadable``; it never reads as "no tips".
    """
    from specify_cli.lanes.frozen_membership import FrozenLaneMembership, build_frozen_membership
    from specify_cli.lanes.lane_tip import LaneTipListingError, recorded_tip_branches
    from specify_cli.lanes.persistence import read_lanes_json

    previous = read_lanes_json(planning_dir)
    if previous is None:
        return FrozenLaneMembership.empty()
    started = _read_started_wp_ids(repo_root, mission_slug, owned=owned)
    try:
        tipped = recorded_tip_branches(owned.repository_root if owned else repo_root)
    except LaneTipListingError as exc:
        # An unreadable listing is unknown, never "no tips": with a lane manifest on disk, refuse (#5573 FR-007).
        raise _status_unreadable_error(exc) from exc
    return build_frozen_membership(
        previous,
        started=started,
        tipped_branches=tipped,
        present_wp_ids=frozenset(wp_frontmatters),
        eligible_wp_ids=eligible_wp_ids,
    )


def _preflight_frozen_lane_membership(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    meta: dict[str, object] | None,
    target_branch: str,
    *,
    lane_wp_manifests: dict[str, OwnershipManifest],
    lane_wp_dependencies: dict[str, list[str]],
    lane_wp_bodies: dict[str, str],
    wp_frontmatters: dict[str, WPMetadata],
    eligible_wp_ids: frozenset[str],
    owned: OwnedCheckout | None = None,
) -> FrozenLaneMembership:
    """Refuse, before the first status write, a re-finalize that would move started work (#5573).

    Read-only: gathers the frozen membership and dry-runs ``compute_lanes``
    with it against the previous manifest, so a
    :class:`~specify_cli.lanes.compute.LaneMembershipFrozenError` surfaces
    before any status event or ``lanes.json`` write, ``--validate-only``
    included. A :class:`~specify_cli.lanes.compute.LaneDependencyCycleError`
    surfaces here too, with its existing ``LANE_DEPENDENCY_CYCLE`` text:
    keeping started lane-mates together can close a lane cycle that the
    unfrozen inputs would not have. Empty lane inputs still run the check, so a
    removed started WP refuses here rather than in the lane write.
    ``SINGLE_BRANCH`` has one repository-root lane and nothing to move. Other
    lane-computation failures are left to the real lane write, which reports
    them with their existing text (C-003).

    Returns:
        The membership to thread into the real lane write.
    """
    from specify_cli.lanes.branch_naming import InvalidMissionIdentity
    from specify_cli.lanes.compute import LaneComputationError, LaneDependencyCycleError, LaneMembershipFrozenError, compute_lanes
    from specify_cli.lanes.frozen_membership import FrozenLaneMembership
    from specify_cli.lanes.persistence import read_lanes_json
    from specify_cli.migration.backfill_topology import topology_from_meta

    topology = topology_from_meta(meta or {}, planning_dir)
    if topology is MissionTopology.SINGLE_BRANCH:
        return FrozenLaneMembership.empty()
    frozen = _gather_frozen_lane_membership(
        planning_dir,
        repo_root,
        mission_slug,
        wp_frontmatters=wp_frontmatters,
        eligible_wp_ids=eligible_wp_ids,
        owned=owned,
    )
    if frozen.is_empty:
        return frozen
    raw_mission_id = meta.get("mission_id") if meta else None
    raw_mission_branch = meta.get("mission_branch") if meta else None
    try:
        compute_lanes(
            dependency_graph=lane_wp_dependencies,
            ownership_manifests=lane_wp_manifests,
            mission_slug=mission_slug,
            target_branch=target_branch,
            wp_bodies=lane_wp_bodies,
            mission_id=raw_mission_id if isinstance(raw_mission_id, str) else None,
            previous_lanes=read_lanes_json(planning_dir),
            topology=topology,
            mission_branch=raw_mission_branch if isinstance(raw_mission_branch, str) else None,
            frozen=frozen,
        )
    except (LaneMembershipFrozenError, LaneDependencyCycleError):
        # A cycle can come from keeping started lane-mates together; the real
        # lane write would raise it after the status writes, so refuse here.
        raise
    except (LaneComputationError, InvalidMissionIdentity) as exc:
        # Deferred, not swallowed: the real lane write recomputes from the same
        # inputs, raises this again and renders it with its existing text (C-003).
        logger.debug("frozen-lane preflight deferred a lane-computation failure to the lane write: %s", exc)
    return frozen


def _compute_and_write_lanes(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    wp_manifests: dict[str, OwnershipManifest],
    wp_dependencies: dict[str, list[str]],
    wp_frontmatters: dict[str, WPMetadata],
    wp_bodies: dict[str, str],
    meta: dict[str, object] | None,
    target_branch: str,
    *,
    all_canceled: bool = False,
    json_output: bool,
    owned: OwnedCheckout | None = None,
    refresh_planning_commit: bool = False,
    allow_orphaned: bool = False,
    planning_sha: PlanningCommitResolution | None = None,
    frozen: FrozenLaneMembership | None = None,
) -> tuple[Path | None, LanesManifest | None, PlanningCommitResolution | None]:
    """Phase: compute execution lanes + write lanes.json + risk report.

    Thin CLI wrapper (WP01, #4758) around the pure
    :func:`specify_cli.lanes.compute_and_persist.compute_and_write_lanes`
    core: this function resolves the two CLI/status-partition inputs the
    core needs already-resolved (``planning_commit_sha`` via the
    still-local :func:`_preserve_or_capture_planning_commit_sha`, and
    ``mission_id`` from ``meta.json``), calls the core, then reports the
    outcome on the console / in ``--json`` and runs the (``policy``-backed)
    parallelization-risk report -- none of which the pure core may import.
    Behavior is unchanged for the healthy path (NFR-003-style
    behavior-preservation): only the glob-revalidation-failure /
    lane-computation bodies moved, verbatim, into the core.
    """

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    _mf._raise_lane_computation_empty_input_if_needed(
        wp_manifests,
        wp_dependencies,
        wp_frontmatters,
        all_canceled=all_canceled,
        json_output=json_output,
    )
    from specify_cli.lanes.compute_and_persist import LaneGlobValidationError, compute_and_write_lanes
    from specify_cli.migration.backfill_topology import topology_from_meta

    raw_mission_id = meta.get("mission_id") if meta else None
    mission_id = raw_mission_id if isinstance(raw_mission_id, str) else None
    # FR-009 / ADR 2026-07-29-1 (T002): freeze the recorded planning-artifact SHA
    # into the SAME write as the rest of lanes.json — no second commit, no
    # chicken-and-egg with this invocation's own finalize commit hash.
    # #3311 T015: once execution has begun, PRESERVE the previously-recorded
    # SHA instead of re-capturing the current branch tip — unless the operator
    # explicitly re-pointed it with --refresh-planning-commit (#4141). See
    # ``_preserve_or_capture_planning_commit_sha``.
    if planning_sha is None:
        planning_sha = _mf._preserve_or_capture_planning_commit_sha(
            planning_dir,
            repo_root,
            mission_slug,
            target_branch,
            json_output=json_output,
            owned=owned,
            refresh_planning_commit=refresh_planning_commit,
            allow_orphaned=allow_orphaned,
        )
    # Tolerate a ``None`` resolution: the historical test seam in
    # ``test_mission_finalize_phases.py`` monkeypatches this helper to return
    # ``None``, the pre-#4141 shape's value the manifest was assigned verbatim.
    resolved_sha = planning_sha.sha if planning_sha is not None else None
    # #5100 M3 (review cycle-1 nit 3): derived from the ALREADY-loaded,
    # tolerant `meta` parameter this wrapper already accepts (never a
    # second, stricter meta.json read) -- mirrors tasks_finalize.py's
    # identical fix. Read-only (C-003): the fail-closed writer check now
    # lives inside compute_and_write_lanes itself (WP05).
    topology = topology_from_meta(meta or {}, planning_dir)
    raw_mission_branch = meta.get("mission_branch") if meta else None
    resolved_mission_branch = raw_mission_branch if isinstance(raw_mission_branch, str) else None
    try:
        lanes_path, lanes_manifest = compute_and_write_lanes(
            planning_dir,
            repo_root,
            mission_slug,
            wp_manifests,
            wp_dependencies,
            wp_frontmatters,
            wp_bodies,
            target_branch,
            planning_commit_sha=resolved_sha,
            mission_id=mission_id,
            topology=topology,
            mission_branch=resolved_mission_branch,
            frozen=frozen,
        )
    except LaneGlobValidationError as exc:
        glob_result = exc.result
        if not json_output:
            lane_stderr = _mf.err_console
            for err in glob_result.errors:
                lane_stderr.print(f"[red]ERROR:[/red] Lane-compute re-validation: {err}")
        # Single-source the abort message through the exception the pure core
        # raises (lanes.compute_and_persist.LaneGlobValidationError) rather than
        # re-hardcoding the identical literal here (SSOT — squad MINOR).
        error_msg = str(exc)
        if json_output:
            _mf._emit_json({"error": error_msg, "ownership_literal_path_errors": glob_result.errors})
        else:
            _mf.console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1) from None
    except TopologyManifestMismatch as exc:
        # #5100 WP05: a single_branch mission whose on-disk lanes.json still
        # has a code lane (never re-stamped after #5100) -- the manifest
        # write is refused, so no lanes.json changed. Reported the same way
        # the sibling LaneGlobValidationError branch above is: JSON envelope
        # or console, never a raw traceback.
        error_msg = str(exc)
        if json_output:
            _mf._emit_json({"error": error_msg, "error_code": exc.error_code})
        else:
            _mf.console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1) from None
    _mf._report_planning_sha_decision(
        target_branch,
        planning_sha,
        json_output=json_output,
        repo_root=repo_root,
        mission_slug=mission_slug,
    )
    if not json_output:
        _mf.console.print(f"[green]✓[/green] Computed {len(lanes_manifest.lanes)} execution lane(s)")
        if lanes_manifest.collapse_report and lanes_manifest.collapse_report.independent_wps_collapsed > 0:
            _mf.console.print(
                f"[yellow]⚠[/yellow] {lanes_manifest.collapse_report.independent_wps_collapsed} "
                f"independent WP pair(s) collapsed into same lane. Run with --json to see details."
            )
    _mf._report_parallelization_risk(repo_root, lanes_manifest, wp_bodies, json_output=json_output)
    return lanes_path, lanes_manifest, planning_sha


def _report_parallelization_risk(repo_root: Path, lanes_manifest: LanesManifest, wp_bodies: dict[str, str], *, json_output: bool) -> None:
    """Phase: compute + (optionally block on) the parallelization risk report."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    from specify_cli.policy.config import load_policy_config
    from specify_cli.policy.risk_scorer import compute_risk_report

    policy = load_policy_config(repo_root)
    risk_report = compute_risk_report(lanes_manifest, wp_bodies=wp_bodies, policy=policy.risk)
    if risk_report.overall_score > 0 and not json_output:
        _mf.console.print(f"[yellow]⚠[/yellow] Parallelization risk: {risk_report.overall_score:.2f} (threshold: {risk_report.threshold:.2f})")
        for pr in risk_report.lane_pair_risks:
            if pr.score > 0:
                _mf.console.print(f"  {pr.lane_a} ↔ {pr.lane_b}: {pr.score:.2f}")
                for d in pr.shared_parent_dirs[:3]:
                    _mf.console.print(f"    shared dir: {d}")
                for c in pr.import_coupling[:3]:
                    _mf.console.print(f"    coupling: {c}")
    if risk_report.exceeds_threshold and policy.risk.mode == "block":
        error_msg = f"Parallelization risk {risk_report.overall_score:.2f} exceeds threshold {risk_report.threshold:.2f}. Adjust the risk policy to proceed."
        if json_output:
            _mf._emit_json(
                {
                    "error": error_msg,
                    "risk_report": {"overall_score": risk_report.overall_score, "threshold": risk_report.threshold},
                }
            )
        else:
            _mf.console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)


def _resolve_acceptance_matrix_home(repo_root: Path, planning_dir: Path, mission_slug: str, *, owned: OwnedCheckout | None = None) -> Path:
    """Resolve the acceptance matrix's declared home dir AND establish it (FR-010 / C8 / B6 cycle 2).

    WP15 (Decision ``plan.design.translate-if-present-kinds``): resolves
    through ``write_dir(ACCEPTANCE_MATRIX)`` -- the single write-location
    authority -- never the gate's READ-side resolver
    (``_acceptance_matrix_read_dir`` / ``read_dir``). The DoD line "no
    finalize write leg uses a read resolver for a COORD kind" applies here
    too: a READ resolver's EMPTY/UNMATERIALIZED -> PRIMARY degrade (C-002)
    would misclassify a never-seeded coordination Mission's home as
    ``planning_dir``, routing the scaffold's bare write there instead of
    establishing the real coordination surface first. A ``DELETED``
    coordination branch has no writable home at all, so we fall back to the
    primary ``planning_dir`` -- the scaffold is a convenience artifact and
    must never fail finalize (the caller's own ``except Exception`` is the
    broader safety net for every OTHER write_dir refusal, e.g. a remote-only
    branch).
    """
    from mission_runtime import placement_seam
    from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted

    if owned:
        return placement_seam(owned.repository_root, owned.mission_slug, owned=owned).write_dir(MissionArtifactKind.ACCEPTANCE_MATRIX).path
    try:
        return placement_seam(repo_root, mission_slug).write_dir(MissionArtifactKind.ACCEPTANCE_MATRIX).path
    except CoordinationBranchDeleted:
        return planning_dir


def _scaffold_acceptance_matrix_if_lane_based(
    planning_dir: Path,
    repo_root: Path,
    mission_slug: str,
    lanes_manifest: LanesManifest | None,
    functional_spec_requirement_ids: set[str],
    *,
    validate_only: bool,
    json_output: bool,
    owned: OwnedCheckout | None = None,
) -> None:
    """Phase: Finding 6 — scaffold acceptance-matrix.json for lane-based missions."""

    from specify_cli.cli.commands.agent import mission_finalize as _mf

    if lanes_manifest is None or validate_only:
        return
    try:
        from specify_cli.acceptance.matrix import scaffold_acceptance_matrix

        # FR-010 / C8: resolve the matrix's DECLARED HOME through the same surface
        # resolver the accept gate reads from, so the scaffolder's idempotency check
        # sees an existing coord-homed matrix and never authors a divergent second
        # primary copy (#2882). A deleted coord branch (fail-loud) falls back to the
        # primary planning dir — the scaffold is a convenience artifact, never a gate.
        home_dir = _resolve_acceptance_matrix_home(repo_root, planning_dir, mission_slug, **({"owned": owned} if owned else {}))
        # write-surface-coherence WP08 (#2804 / #2404 T040/T041): thread
        # ``repo_root`` so the WRITE (not just the idempotency check) routes
        # through the coord-aware write-seam — never a stray PRIMARY husk
        # under coord topology, mirroring the sibling issue-matrix scaffold.
        #
        # FR-015/NFR-001 (WP13 T072/T073): when the declared home IS
        # ``planning_dir`` -- every topology this mission's atomic-finalize
        # mandate covers (``LIFECYCLE_OWNED_TOPOLOGIES`` is single_branch-only,
        # and a flat/non-coord repository-root mission resolves here too) --
        # there is no separate coordination surface for a write-seam commit to
        # route to. Omitting ``repo_root`` takes ``scaffold_acceptance_
        # matrix``'s bare-write branch (``write_acceptance_matrix``, no
        # commit): `_collect_finalize_artifacts` already lists
        # ``acceptance-matrix.json`` as a TASKS_INDEX candidate, so the write
        # rides the SAME single combined commit ``_commit_finalize_
        # artifacts`` makes for frontmatter/tasks.md/lanes.json below --
        # closing the separate-commit atomicity gap T070 pinned (a failure
        # inside that later, single commit now leaves NO acceptance-matrix
        # commit stranded, because none was ever made separately). A
        # genuinely coord-routed home (a LANES/coord-topology repository-root
        # mission, outside this WP's single_branch-owned mandate) keeps
        # today's write-seam-routed, separately-committed scaffold unchanged.
        writes_to_planning_dir = home_dir.resolve() == planning_dir.resolve()
        acceptance_matrix_path = scaffold_acceptance_matrix(
            planning_dir,
            mission_slug,
            requirement_ids=sorted(functional_spec_requirement_ids),
            home_dir=home_dir,
            repo_root=None if writes_to_planning_dir else (owned.repository_root if owned else repo_root),
            policy=_mf._mission_protection_policy(repo_root, mission_slug, owned),
            owned=owned,
        )
    except Exception as acc_matrix_exc:  # noqa: BLE001 — convenience artifact never blocks finalize
        if owned:
            raise
        if not json_output:
            _mf.console.print(f"[yellow]Warning:[/yellow] could not scaffold acceptance-matrix.json: {acc_matrix_exc}")
            _mf.console.print(f"[yellow]Hint:[/yellow] create it manually before acceptance:\n  spec-kitty agent mission finalize-tasks --mission {mission_slug}")
        return
    if acceptance_matrix_path is not None and not json_output:
        try:
            rel: Path = acceptance_matrix_path.relative_to(repo_root)
        except ValueError:
            rel = acceptance_matrix_path
        _mf.console.print(f"[info] Scaffolded {rel}")
