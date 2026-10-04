"""Dry-run forecast (preview + payload build) for the merge seam.

Mission #2057 (decompose ``cli/commands/merge.py``) — IC-06 / WP06.

The ``merge --dry-run`` preview was extracted byte-for-byte out of the ``merge``
command body: lanes-manifest load, the review-artifact consistency gate preview
(emits ``REJECTED_REVIEW_ARTIFACT_CONFLICT`` in both human and JSON output), the
``would_assign_mission_number`` scan, and the JSON/human payload build. The
dry-run JSON key set is frozen by contracts/cli-surface-contract.md (FR-001,
FR-004) and re-asserted by the golden CLI test. One-way import: this module
never imports the command shim.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer

from specify_cli import __version__ as SPEC_KITTY_VERSION
from specify_cli.cli.console import console
from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    CoordinationWorktreeUnmaterialized,
)
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.core.paths import get_main_repo_root, resolve_merge_retention
from specify_cli.lanes.persistence import (
    CorruptLanesError,
    MissingLanesError,
    require_lanes_json,
)
from specify_cli.lanes.consolidation import preview_mission_target_integration
from specify_cli.lanes.models import LanesManifest
from specify_cli.consolidation._constants import (
    TARGET_BRANCH_CONTENT_CONFLICT,
    TARGET_BRANCH_CONTENT_CONFLICT_HEADER,
    TARGET_BRANCH_CONTENT_CONFLICT_REMEDIATION_UPDATE,
    logger,
)
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.mission_number.bake import assign_next_mission_number
from specify_cli.consolidation.preflight import refuse_protected_status_target
from specify_cli.consolidation.state import needs_number_assignment
from mission_runtime import MissionArtifactKind, placement_seam, resolve_artifact_surface
from specify_cli.post_merge.review_artifact_consistency import (
    REJECTED_REVIEW_ARTIFACT_CONFLICT,
    ReviewArtifactPreflightResult,
    format_review_artifact_finding,
    review_artifact_finding_diagnostic,
    run_review_artifact_consistency_preflight,
)


def _effective_delete_branch(delete_branch: bool, lanes_manifest: LanesManifest) -> bool:
    """Whether the merge would really delete a branch (#5100 B6).

    An unprotected single_branch mission's ``mission_branch`` is its own
    ``target_branch`` and it has no code lanes, so the executor deletes nothing;
    report that instead of the raw retention flag.
    """
    from specify_cli.lanes.compute import is_planning_lane

    if not delete_branch:
        return False
    only_planning = all(is_planning_lane(lane) for lane in lanes_manifest.lanes)
    return not (only_planning and lanes_manifest.mission_branch == lanes_manifest.target_branch)


def _emit_dry_run_error(*, error_msg: str, json_output: bool, error_code: str | None = None) -> None:
    """Emit a dry-run error in the right channel (``error_code`` added to JSON when given)."""
    if json_output:
        payload: dict[str, str] = {"spec_kitty_version": SPEC_KITTY_VERSION, "error": error_msg}
        if error_code is not None:
            payload["error_code"] = error_code
        print(json.dumps(payload))
    else:
        console.print(f"[red]Error:[/red] {error_msg}")


def _preview_review_artifacts(
    repo_root: Path,
    resolved_feature: str,
    wp_ids: list[str],
    *,
    json_output: bool,
) -> tuple[Path, ReviewArtifactPreflightResult]:
    """Resolve the preview dir and run the review-artifact preflight, failing closed.

    The preflight reads WP lane state from the STATUS_STATE (coord) partition. On
    a coord-topology mission whose coordination branch was deleted, or whose
    coordination worktree is not materialized (#4959), that read raises
    :class:`CoordinationBranchDeleted` / :class:`CoordinationWorktreeUnmaterialized`
    -- ``StatusReadPathNotFound(Exception)`` subclasses, not ``RuntimeError`` /
    ``OSError``. #5110: render the exception's own remediation (its ``next_step``
    is folded into ``str(exc)``) and exit 1, mirroring the real consolidation
    path's STATUS_STATE read in ``executor.py``, with a valid ``--json`` error
    object carrying the stable ``error_code`` -- never a raw traceback.
    """
    main_repo = get_main_repo_root(repo_root)
    try:
        # FR-006 (#2885): the review-artifact consistency preflight needs facts from
        # TWO partitions — WP lane state (STATUS_STATE, the coord husk for a coord
        # mission) and review-cycle artifacts (WORK_PACKAGE_TASK, PRIMARY) — and it
        # resolves each from its OWN declared home internally (see
        # ``find_rejected_review_artifact_conflicts``). The dir below stays PRIMARY
        # because it ALSO drives the ``would_assign_mission_number`` scan
        # (``meta.json`` is a PRIMARY-partition fact for every topology); passing it
        # into the preflight only supplies the mission slug (``.name``). Routed
        # through the ONE affirmative surface→filesystem seam
        # (lifecycle-gate-execution-context WP02).
        feature_dir_for_preview = resolve_artifact_surface(
            main_repo,
            resolved_feature,
            MissionArtifactKind.WORK_PACKAGE_TASK,
        ).path
        preflight = run_review_artifact_consistency_preflight(feature_dir_for_preview, wp_ids=wp_ids)
    except (CoordinationBranchDeleted, CoordinationWorktreeUnmaterialized) as exc:
        _emit_dry_run_error(error_msg=str(exc), json_output=json_output, error_code=exc.error_code)
        if not json_output:
            console.print(
                "[yellow]Dry run aborted before any state change.[/yellow] "
                "Restore the mission's coordination worktree/branch as described above, "
                "then re-run [bold]spec-kitty consolidate --dry-run[/bold]."
            )
        raise typer.Exit(1) from exc
    return feature_dir_for_preview, preflight


def _emit_review_artifact_block(
    review_artifact_preflight: ReviewArtifactPreflightResult,
    *,
    main_repo_for_diag: Path,
    resolved_feature: str,
    resolved_target_branch: str,
    json_output: bool,
) -> None:
    """Emit the review-artifact gate failure (REJECTED_REVIEW_ARTIFACT_CONFLICT).

    FR-001 (WP07/T030, traced not assumed): renders ``review_artifact_preflight``
    opaquely (``.diagnostics()`` / ``.findings``) — no independent frontmatter
    re-parse of its own. The event-sourced ``review_result`` reducer slot T029
    wired into ``run_review_artifact_consistency_preflight`` therefore reaches
    the dry-run preview automatically; no additional code change is needed here.
    """
    diagnostics = review_artifact_preflight.diagnostics(
        repo_root=main_repo_for_diag,
    )
    if json_output:
        diagnostic_code = (
            diagnostics[0]["diagnostic_code"]
            if diagnostics
            else REJECTED_REVIEW_ARTIFACT_CONFLICT
        )
        print(
            json.dumps(
                {
                    "spec_kitty_version": SPEC_KITTY_VERSION,
                    "mission_slug": resolved_feature,
                    "target_branch": resolved_target_branch,
                    "blocked": True,
                    "blockers": diagnostics,
                    "diagnostic_code": diagnostic_code,
                }
            )
        )
        return

    console.print("[red]Error:[/red] Review artifact consistency gate failed.")
    for finding in review_artifact_preflight.findings:
        diagnostic = review_artifact_finding_diagnostic(
            finding,
            repo_root=main_repo_for_diag,
        )
        console.print(
            f"  - {format_review_artifact_finding(finding, repo_root=main_repo_for_diag)}"
        )
        console.print(f"    diagnostic_code: {diagnostic['diagnostic_code']}")
        console.print(f"    branch_or_work_package: {diagnostic['branch_or_work_package']}")
        console.print(f"    violated_invariant: {diagnostic['violated_invariant']}")
        console.print(f"    latest_review_cycle_path: {diagnostic['latest_review_cycle_path']}")
        if "latest_review_cycle_verdict" in diagnostic:
            console.print(
                f"    latest_review_cycle_verdict: {diagnostic['latest_review_cycle_verdict']}"
            )
        remediation = diagnostic.get("remediation", [])
        if not isinstance(remediation, list):
            remediation = [str(remediation)]
        for line in remediation:
            console.print(f"    remediation: {line}")
    console.print(f"  Mission: {resolved_feature}")


def _emit_target_content_conflict(
    *,
    resolved_feature: str,
    mission_branch: str,
    target_branch: str,
    conflicting_paths: tuple[str, ...],
    json_output: bool,
) -> None:
    """Render the stable #4892 dry-run blocker."""
    remediation = [
        TARGET_BRANCH_CONTENT_CONFLICT_REMEDIATION_UPDATE,
        "Resolve the listed conflicts, then rerun `spec-kitty consolidate --dry-run`.",
    ]
    if json_output:
        print(
            json.dumps(
                {
                    "spec_kitty_version": SPEC_KITTY_VERSION,
                    "mission_slug": resolved_feature,
                    "mission_branch": mission_branch,
                    "target_branch": target_branch,
                    "blocked": True,
                    "diagnostic_code": TARGET_BRANCH_CONTENT_CONFLICT,
                    "conflicting_paths": list(conflicting_paths),
                    "remediation": remediation,
                }
            )
        )
        return

    console.print(f"[red]Error:[/red] {TARGET_BRANCH_CONTENT_CONFLICT_HEADER}")
    console.print(f"  diagnostic_code: {TARGET_BRANCH_CONTENT_CONFLICT}")
    console.print(f"  mission_branch: {mission_branch}")
    console.print(f"  target_branch: {target_branch}")
    for path in conflicting_paths:
        console.print(f"  conflicting_path: {path}")
    for line in remediation:
        console.print(f"  remediation: {line}")


def _scan_would_assign_mission_number(repo_root: Path, feature_dir_for_preview: Path) -> int | None:
    """Best-effort dry-run preview of merge-time mission_number assignment (WP10/T053)."""
    if not needs_number_assignment(feature_dir_for_preview):
        return None
    try:
        result: int = assign_next_mission_number(
            get_main_repo_root(repo_root),
            get_main_repo_root(repo_root) / KITTY_SPECS_DIR,
        )
        return result
    except Exception as exc:  # noqa: BLE001 — dry-run mission_number scan is best-effort; an unavailable kitty-specs dir must not crash the preview
        logger.warning("dry-run mission_number scan failed: %s", exc)
        return None


def _refuse_protected_status_target_in_forecast(main_repo: Path, mission_slug: str, lanes_manifest: LanesManifest, *, json_output: bool) -> None:
    """``--dry-run`` parity for the #5385 preflight: report the policy's refusal with its own ``error_code``."""
    verdict = refuse_protected_status_target(main_repo, mission_slug, lanes_manifest)
    if verdict is None:
        return
    _emit_dry_run_error(
        error_msg=f"{verdict.error_code}: {verdict.message} Next step: {verdict.next_step}",
        json_output=json_output,
        error_code=verdict.error_code,
    )
    raise typer.Exit(1)


def run_dry_run_forecast(
    *,
    repo_root: Path,
    resolved_feature: str | None,
    resolved_target_branch: str,
    resolved_strategy: MergeStrategy,
    delete_branch: bool | None,
    remove_worktree: bool | None,
    push: bool,
    json_output: bool,
) -> None:
    """Render the ``merge --dry-run`` forecast and exit.

    Behavior-preserving extraction of the dry-run block from the ``merge``
    command body. Always terminates the dry-run path (returns on success after
    printing the payload; raises ``typer.Exit(1)`` on unresolved slug / missing
    lanes / review-artifact conflict).

    ``delete_branch`` / ``remove_worktree`` are tri-state (``None`` = flag
    unset): they are resolved against the mission's ``meta.json`` retention
    policy via :func:`resolve_merge_retention` (contracts/retention-resolver-
    contract.md, consumption contract item 2) -- the SAME resolver the merge
    executor uses -- so the forecast reports the RESOLVED cleanup decision
    instead of echoing raw flags.
    """
    if not resolved_feature:
        _emit_dry_run_error(
            error_msg="Mission slug could not be resolved. Use --mission <slug>.",
            json_output=json_output,
        )
        raise typer.Exit(1)

    # The ONE placement seam for this mission — every partition-routed read
    # below (LANE_STATE, PRIMARY_METADATA) goes through it, mirroring the
    # executor's seam construction in ``_run_lane_based_consolidation``.
    seam = placement_seam(get_main_repo_root(repo_root), resolved_feature)
    try:
        # FR-001 (#2185): ``lanes.json`` is a LANE_STATE (PRIMARY-partition)
        # artifact — it lives ONLY on the PRIMARY checkout post-#2106. The
        # kind-blind ``candidate_feature_dir_for_mission`` lands on the STATUS-only
        # ``-coord`` husk for a coord-topology mission, where ``lanes.json`` is
        # absent → the forecast spuriously reports missing lanes. Route by kind so
        # the dry-run reads the real PRIMARY lane manifest.
        lanes_manifest = require_lanes_json(
            seam.read_dir(MissionArtifactKind.LANE_STATE)
        )
    except (MissingLanesError, CorruptLanesError) as exc:
        _emit_dry_run_error(error_msg=str(exc), json_output=json_output)
        raise typer.Exit(1) from exc
    _refuse_protected_status_target_in_forecast(get_main_repo_root(repo_root), resolved_feature, lanes_manifest, json_output=json_output)

    # FR-007/FR-008/FR-009: Run the same review-artifact consistency gate
    # that real merge runs (issue #991). When a rejected review-cycle
    # artifact still sits on an approved/done WP, real merge exits with
    # REJECTED_REVIEW_ARTIFACT_CONFLICT — dry-run must surface the same
    # blocker in both human and JSON output, so operators can trust the
    # preview as a readiness signal.
    dry_run_all_wp_ids: list[str] = [
        wp for lane in lanes_manifest.lanes for wp in lane.wp_ids
    ]
    feature_dir_for_preview, review_artifact_preflight = _preview_review_artifacts(
        repo_root,
        resolved_feature,
        dry_run_all_wp_ids,
        json_output=json_output,
    )
    if not review_artifact_preflight.passed:
        _emit_review_artifact_block(
            review_artifact_preflight,
            main_repo_for_diag=get_main_repo_root(repo_root),
            resolved_feature=resolved_feature,
            resolved_target_branch=resolved_target_branch,
            json_output=json_output,
        )
        raise typer.Exit(1)

    try:
        integration_preview = preview_mission_target_integration(
            get_main_repo_root(repo_root),
            lanes_manifest.mission_branch,
            resolved_target_branch,
            strategy=resolved_strategy,
        )
    except (RuntimeError, OSError) as exc:
        # A *non-conflict* preview failure — unrelated histories, a failed
        # ``git worktree add`` (RuntimeError), or an OS-level failure from the
        # scratch worktree (mkdtemp / write_bytes / fsdecode → OSError). Route it
        # through the same channel as every other dry-run error so ``--json``
        # output stays valid JSON (a raw traceback would corrupt it) and
        # terminate the path.
        _emit_dry_run_error(error_msg=str(exc), json_output=json_output)
        raise typer.Exit(1) from exc
    if integration_preview.conflicting_paths:
        _emit_target_content_conflict(
            resolved_feature=resolved_feature,
            mission_branch=lanes_manifest.mission_branch,
            target_branch=resolved_target_branch,
            conflicting_paths=integration_preview.conflicting_paths,
            json_output=json_output,
        )
        raise typer.Exit(1)

    would_assign_number = _scan_would_assign_mission_number(repo_root, feature_dir_for_preview)

    # FR-008 (#3131, #3833): resolve the SAME retention decision the merge
    # executor would make -- via the single shared resolver -- off the mission's
    # PRIMARY_METADATA dir: the SAME surface the executor's retention leg reads
    # (``placement_seam(...).read_dir(MissionArtifactKind.PRIMARY_METADATA)`` in
    # ``_run_lane_based_consolidation``) and the abort path reads too. Do NOT read it off
    # ``feature_dir_for_preview`` above -- that is the WORK_PACKAGE_TASK surface
    # (kept for the review-artifact gate and the mission-number scan), a SECOND,
    # independent derivation of "where meta.json lives" that happens to resolve
    # to the same ``kitty-specs/<slug>/`` dir for every topology today; if the
    # WORK_PACKAGE_TASK home ever diverged from PRIMARY_METADATA, a preview read
    # off it would report "will delete" while the real merge retains.
    primary_meta_dir = seam.read_dir(MissionArtifactKind.PRIMARY_METADATA)
    retention_decision = resolve_merge_retention(
        primary_meta_dir,
        explicit_delete_branch=delete_branch,
        explicit_remove_worktree=remove_worktree,
    )

    payload: dict[str, object] = {
        "spec_kitty_version": SPEC_KITTY_VERSION,
        "mission_slug": resolved_feature,
        "target_branch": resolved_target_branch,
        "strategy": resolved_strategy.value,
        "delete_branch": _effective_delete_branch(retention_decision.delete_branch, lanes_manifest),
        "remove_worktree": retention_decision.remove_worktree,
        "push": push,
        "mission_branch": lanes_manifest.mission_branch,
        "lanes": [lane.to_dict() for lane in lanes_manifest.lanes],
        "would_assign_mission_number": would_assign_number,
        "retention": {
            "branch_source": retention_decision.branch_source,
            "worktree_source": retention_decision.worktree_source,
            "warnings": list(retention_decision.warnings),
        },
    }
    if would_assign_number is not None and not json_output:
        console.print(
            f"[cyan]would assign[/cyan] mission_number={would_assign_number} to mission {resolved_feature}"
        )
    if json_output:
        print(json.dumps(payload))
    else:
        console.print_json(json.dumps(payload))


__all__ = ["run_dry_run_forecast"]
