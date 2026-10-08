"""finalize-tasks command family for ``agent mission`` (#2056 WP07).

This leaf module owns ``finalize_tasks`` — the largest single function in the
pre-decomposition ``mission.py`` (1227 LOC) — plus its two dedicated helpers
``_collect_finalize_artifacts`` and ``_branch_tree_relative_path``. The body is
decomposed into ≤15-CC phase helpers, each with focused tests in
``test_mission_finalize_phases.py``.

INV-6 (the ``--validate-only`` zero-mutation invariant) is preserved exactly:
the bootstrap loop infers all 8 fields in memory but the disk-write phase is
guarded by ``frontmatter_changed and not validate_only`` and the validate-only
report path returns BEFORE any committing/seeding writer runs. An explicit
assertion (``_assert_no_write_in_validate_only``) reinforces the guard. The
T017 tasks.md regeneration — a tracked-file write that bypassed the
frontmatter queue (#3221) — is likewise skipped in validate-only mode, with
its staleness reported instead of repaired, so the invariant covers every
tracked-file write the command performs.

One-way leaf (INV-8): imports lower layers + sibling Seam B/C/D leaves only at
module scope. The cross-cutting symbols the finalize tests patch on the
``mission`` module (``locate_project_root`` /
``_find_feature_directory`` / ``run_command``) are resolved
THROUGH the ``mission`` module at call time so the historical
``mission.<name>`` patch seams keep working without an import cycle. The
command is defined here as a plain callable; ``mission`` registers it on its
Typer ``app`` and re-exports the public names (WP09 finalizes the sweep).

Phase modules (#5627): this module now keeps only the command, its context
and phase orchestration, and the artifact-collection helpers. Each phase body
lives in a sibling leaf module, moved verbatim:

* ``mission_finalize_seams`` -- constants, the owned-envelope ContextVar, ``_emit_json`` and the ``mission``-routed seams
* ``mission_finalize_branch_contract`` -- target-branch resolution and branch-contract persistence
* ``mission_finalize_validation`` -- requirement, dependency and issue-matrix gates
* ``mission_finalize_bootstrap`` -- the per-WP bootstrap loop, ownership gates and the validate-only report
* ``mission_finalize_planning_pin`` -- the planning-commit pin (preserve / refresh)
* ``mission_finalize_lanes`` -- lane computation and the acceptance-matrix scaffold
* ``mission_finalize_commit`` -- the commit pipeline, success report and rollback guards

Every name those modules define is re-exported here, so ``mission_finalize.<name>``
stays importable. A phase module calls through this module at call time only for a
function another finalize module owns and for a name tests patch here; any other call
inside a phase module is direct, so patch that module to intercept it (see
``tests/.../test_mission_finalize_phase_modules.py`` and
``docs/api/finalize-tasks-internals.md``).

Behavior is preserved byte-for-byte from the pre-decomposition ``mission.py``;
the WP01 golden harness is the regression net. ``_stage_finalize_artifacts_in_
coord_worktree`` / ``_resolve_planning_placement`` / ``_planning_commit_worktree``
are NOT relocated here — WP08 moves them to ``commit_router``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, cast

import typer

from specify_cli.cli.console import console as console

if TYPE_CHECKING:
    from specify_cli.lanes.frozen_membership import FrozenLaneMembership
from kernel.paths import repo_tree_path
from mission_runtime import ActionContextError, MissionArtifactKind
from specify_cli.core.checkout_identity import CheckoutIdentity, Intent, resolve_checkout_identity
from mission_runtime import OwnedCheckout
from specify_cli.cli.commands._owned_checkout import (
    OwnedCheckoutOption,
    emit_owned_refusal,
    owned_checkout_option,
    resolve_owned_or_adopt,
    stale_copy_payload,
)
from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES, require_unstaged_index
from specify_cli.ownership.frontmatter_source import (
    FinalizeFrontmatterSource,
    resolve_wp_manifests,
)
from specify_cli.ownership.models import OwnershipManifest
from specify_cli.status import BootstrapResult, WPMetadata
from specify_cli.core.wps_manifest import (
    WpsManifest,
    check_concern_refs_coverage,
)
from specify_cli.cli.commands.agent.mission_check_prerequisites import (
    _read_meta_for_emission,
)
from specify_cli.cli.commands.agent.mission_feature_resolution import (
    _build_setup_plan_detection_error,
    _resolve_mission_dir_name_primary_anchored,
)
from specify_cli.cli.commands.agent.finalize_status_surface import StatusSurfaceGuard, StatusSurfaceLeftover
from specify_cli.cli.commands.agent.finalization_eligibility import (
    FinalizationEligibility,
)
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.cli.commands.agent.mission_parsing import (
    _invalid_mission_specs_owned_files,
    _with_cli_version,
    _extract_wp_ids_from_task_files,
)

# Patch seams (#5627): the phase modules call these through
# ``mission_finalize`` at call time, so they stay module attributes here even
# though this module no longer calls them itself.
from kernel.git import status_entries as status_entries
from specify_cli.cli.console import err_console as err_console
from specify_cli.core.paths import get_main_repo_root as get_main_repo_root
from specify_cli.core.paths import load_meta_fail_closed as load_meta_fail_closed
from specify_cli.core.vcs.git import capture_branch_tip as capture_branch_tip
from specify_cli.lanes.planning_commit_classify import PinClass as PinClass
from specify_cli.lanes.planning_commit_classify import classify_recorded_pin as classify_recorded_pin
from specify_cli.ownership.inference import detect_post_integration_acceptance as detect_post_integration_acceptance
from specify_cli.cli.commands.agent.mission_finalize_seams import (
    FINALIZE_ATTRIBUTABLE_META_FIELDS as FINALIZE_ATTRIBUTABLE_META_FIELDS,
    FINALIZE_TASKS_COMMAND_NAME as FINALIZE_TASKS_COMMAND_NAME,
    INVALID_WP_OWNED_FILES_KITTY_SPECS as INVALID_WP_OWNED_FILES_KITTY_SPECS,
    ISSUE_MATRIX_FILENAME as ISSUE_MATRIX_FILENAME,
    LANE_COMPUTATION_ABORTED_EMPTY_INPUTS as LANE_COMPUTATION_ABORTED_EMPTY_INPUTS,
    META_JSON_FILENAME as META_JSON_FILENAME,
    OWNERSHIP_CONTRADICTION_CODE_CHANGE_EMPTY_OWNED_FILES as OWNERSHIP_CONTRADICTION_CODE_CHANGE_EMPTY_OWNED_FILES,
    PROJECT_ROOT_NOT_FOUND as PROJECT_ROOT_NOT_FOUND,
    TASKS_MD_FILENAME as TASKS_MD_FILENAME,
    _OWNED_ENVELOPE_EXTRAS as _OWNED_ENVELOPE_EXTRAS,
    _bootstrap_canonical_state_via_mission as _bootstrap_canonical_state_via_mission,
    _emit_json as _emit_json,
    _read_wp_frontmatter as _read_wp_frontmatter,
    _resolve_planning_branch_via_mission as _resolve_planning_branch_via_mission,
    _validate_ownership_via_mission as _validate_ownership_via_mission,
    logger as logger,
)
from specify_cli.cli.commands.agent.mission_finalize_branch_contract import (
    TargetBranchPersistOutcome as TargetBranchPersistOutcome,
    _enforce_branch_contract_write_ownership as _enforce_branch_contract_write_ownership,
    _persist_branch_contract_for_finalize as _persist_branch_contract_for_finalize,
    _persist_recovered_pr_bound_contract as _persist_recovered_pr_bound_contract,
    _persist_target_branch_override as _persist_target_branch_override,
    _preflight_recovered_pr_bound_contract as _preflight_recovered_pr_bound_contract,
    _resolve_merge_target_branch as _resolve_merge_target_branch,
    _resolve_target_branch as _resolve_target_branch,
)
from specify_cli.cli.commands.agent.mission_finalize_validation import (
    _DependencyResolution as _DependencyResolution,
    _advisory_issue_matrix_lint as _advisory_issue_matrix_lint,
    _build_requirement_diagnostics as _build_requirement_diagnostics,
    _build_requirement_mapping_failure_payload as _build_requirement_mapping_failure_payload,
    _build_success_criteria_coverage as _build_success_criteria_coverage,
    _classify_one_wp as _classify_one_wp,
    _classify_wp_requirement_refs as _classify_wp_requirement_refs,
    _detect_bare_prose_requirement_ids_fail_loud as _detect_bare_prose_requirement_ids_fail_loud,
    _detect_dependency_conflicts as _detect_dependency_conflicts,
    _emit_requirement_mapping_report as _emit_requirement_mapping_report,
    _load_manifest as _load_manifest,
    _mission_protection_policy as _mission_protection_policy,
    _read_spec_requirement_ids as _read_spec_requirement_ids,
    _resolve_dependencies_and_refs as _resolve_dependencies_and_refs,
    _scaffold_issue_matrix_if_present as _scaffold_issue_matrix_if_present,
    _validate_dependency_graph as _validate_dependency_graph,
    _validate_occurrence_map_ready as _validate_occurrence_map_ready,
    _validate_requirement_mapping as _validate_requirement_mapping,
    _validate_tasks_md_coverage as _validate_tasks_md_coverage,
)
from specify_cli.cli.commands.agent.mission_finalize_bootstrap import (
    _BootstrapState as _BootstrapState,
    _apply_bootstrap_fields as _apply_bootstrap_fields,
    _apply_finalize_delta as _apply_finalize_delta,
    _apply_ownership_inference as _apply_ownership_inference,
    _assert_no_write_in_validate_only as _assert_no_write_in_validate_only,
    _bootstrap_one_wp as _bootstrap_one_wp,
    _branch_strategy_text as _branch_strategy_text,
    _emit_local_canonical_events as _emit_local_canonical_events,
    _emit_validate_only_report as _emit_validate_only_report,
    _enforce_charter_activation_gate as _enforce_charter_activation_gate,
    _flush_frontmatter_writes as _flush_frontmatter_writes,
    _flush_one_frontmatter_write as _flush_one_frontmatter_write,
    _gather_validation_frontmatter as _gather_validation_frontmatter,
    _lane_computation_empty_input_error as _lane_computation_empty_input_error,
    _project_lane_inputs as _project_lane_inputs,
    _raise_lane_computation_empty_input_if_needed as _raise_lane_computation_empty_input_if_needed,
    _raise_ownership_contradictions_if_any as _raise_ownership_contradictions_if_any,
    _raise_stale_canceled_dependencies_if_any as _raise_stale_canceled_dependencies_if_any,
    _record_ownership_glob_diagnostics as _record_ownership_glob_diagnostics,
    _regenerate_or_report_tasks_md as _regenerate_or_report_tasks_md,
    _run_bootstrap_loop as _run_bootstrap_loop,
    _surface_post_integration_acceptance_warnings as _surface_post_integration_acceptance_warnings,
    _validate_owned_files_not_in_mission_specs as _validate_owned_files_not_in_mission_specs,
    _validate_ownership_manifests as _validate_ownership_manifests,
)
from specify_cli.cli.commands.agent.mission_finalize_planning_pin import (
    PlanningCommitResolution as PlanningCommitResolution,
    _PLANNING_REFRESH_STATUS_BY_ACTION as _PLANNING_REFRESH_STATUS_BY_ACTION,
    _PrimaryPinRefreshCommit as _PrimaryPinRefreshCommit,
    _add_planning_commit_to_validation_report as _add_planning_commit_to_validation_report,
    _commit_planning_pin_refresh as _commit_planning_pin_refresh,
    _commit_planning_pin_refresh_locked as _commit_planning_pin_refresh_locked,
    _drift_is_finalize_bookkeeping_only as _drift_is_finalize_bookkeeping_only,
    _execution_has_begun as _execution_has_begun,
    _finalize_bookkeeping_commit_message as _finalize_bookkeeping_commit_message,
    _finalize_pin_refresh_commit_outcome as _finalize_pin_refresh_commit_outcome,
    _guard_lanes_bytes_unchanged_before_commit as _guard_lanes_bytes_unchanged_before_commit,
    _planning_changed_since_pin as _planning_changed_since_pin,
    _planning_commit_payload as _planning_commit_payload,
    _planning_commit_refresh_payload as _planning_commit_refresh_payload,
    _planning_pin_change as _planning_pin_change,
    _preflight_refresh_planning_commit as _preflight_refresh_planning_commit,
    _prepare_primary_pin_refresh_commit as _prepare_primary_pin_refresh_commit,
    _preserve_or_capture_planning_commit_sha as _preserve_or_capture_planning_commit_sha,
    _read_refresh_worktree_status as _read_refresh_worktree_status,
    _refresh_branch_contract_error as _refresh_branch_contract_error,
    _refresh_worktree_status_error as _refresh_worktree_status_error,
    _refresh_worktree_status_findings as _refresh_worktree_status_findings,
    _refuse_planning_pin_refresh as _refuse_planning_pin_refresh,
    _refuse_planning_sha_refresh as _refuse_planning_sha_refresh,
    _render_pending_entries as _render_pending_entries,
    _report_planning_pin_refresh_success as _report_planning_pin_refresh_success,
    _report_planning_sha_decision as _report_planning_sha_decision,
    _report_refresh_status_findings as _report_refresh_status_findings,
    _report_validate_only_pin_change as _report_validate_only_pin_change,
    _resolve_preserve_planning_commit_decision as _resolve_preserve_planning_commit_decision,
    _resolve_refresh_planning_commit_decision as _resolve_refresh_planning_commit_decision,
    _resolve_status_read_dir as _resolve_status_read_dir,
    _restore_planning_pin_candidate as _restore_planning_pin_candidate,
    _validate_only_planning_preview as _validate_only_planning_preview,
)
from specify_cli.cli.commands.agent.mission_finalize_lanes import (
    _cause_detail as _cause_detail,
    _committed_coordination_log as _committed_coordination_log,
    _compute_and_write_lanes as _compute_and_write_lanes,
    _gather_frozen_lane_membership as _gather_frozen_lane_membership,
    _missing_status_surface_cause as _missing_status_surface_cause,
    _preflight_frozen_lane_membership as _preflight_frozen_lane_membership,
    _read_started_wp_ids as _read_started_wp_ids,
    _report_parallelization_risk as _report_parallelization_risk,
    _resolve_acceptance_matrix_home as _resolve_acceptance_matrix_home,
    _scaffold_acceptance_matrix_if_lane_based as _scaffold_acceptance_matrix_if_lane_based,
    _started_on_coordination_branch as _started_on_coordination_branch,
    _status_unreadable_error as _status_unreadable_error,
)
from specify_cli.cli.commands.agent.mission_finalize_commit import (
    OwnedCheckoutCandidateOutsidePlanningError as OwnedCheckoutCandidateOutsidePlanningError,
    FinalizeWriteLedger as FinalizeWriteLedger,
    WRITE_SCOPE_KEPT_WARNING as WRITE_SCOPE_KEPT_WARNING,
    _META_CHANGED_BY_ANOTHER_WRITER as _META_CHANGED_BY_ANOTHER_WRITER,
    _bytes_or_none as _bytes_or_none,
    _COORD_CANDIDATE_KINDS as _COORD_CANDIDATE_KINDS,
    _CommitOutcome as _CommitOutcome,
    _CoordCandidateDirt as _CoordCandidateDirt,
    _FinalizeCommitCandidates as _FinalizeCommitCandidates,
    _FinalizeCommitLanded as _FinalizeCommitLanded,
    _MetaBranchOverrideProgress as _MetaBranchOverrideProgress,
    _apply_finalize_commit_router_result as _apply_finalize_commit_router_result,
    _capture_status_surface as _capture_status_surface,
    _commit_finalize_artifacts as _commit_finalize_artifacts,
    _coord_candidate_dirt as _coord_candidate_dirt,
    _coord_candidate_filenames as _coord_candidate_filenames,
    _emit_finalize_error_with_revert_note as _emit_finalize_error_with_revert_note,
    _emit_success_report as _emit_success_report,
    _emit_tasks_started as _emit_tasks_started,
    _finalize_candidate_display_path as _finalize_candidate_display_path,
    _finalize_candidates_dirty as _finalize_candidates_dirty,
    _mission_write_scope_files as _mission_write_scope_files,
    _print_membership_conflicts as _print_membership_conflicts,
    _report_status_surface_leftover as _report_status_surface_leftover,
    _report_target_branch_revert_failure as _report_target_branch_revert_failure,
    _resolve_finalize_commit_candidates as _resolve_finalize_commit_candidates,
    _restore_mission_write_scope as _restore_mission_write_scope,
    _restore_mission_write_scope_beside_status as _restore_mission_write_scope_beside_status,
    _restore_status_surface as _restore_status_surface,
    _revert_unpersisted_target_branch_override as _revert_unpersisted_target_branch_override,
    _run_commit_pipeline as _run_commit_pipeline,
    _report_write_scope_kept as _report_write_scope_kept,
    _snapshot_mission_write_scope as _snapshot_mission_write_scope,
    _undo_finalize_write_scope as _undo_finalize_write_scope,
    _STATUS_FILE_NAMES as _STATUS_FILE_NAMES,
    _ACTIVE_LEDGER as _ACTIVE_LEDGER,
    active_write_ledger as active_write_ledger,
    begin_write_ledger as begin_write_ledger,
    end_write_ledger as end_write_ledger,
    note_status_files_written as note_status_files_written,
    _warn_missing_meta as _warn_missing_meta,
)


# Dynamic alias mirror of the canonical ``mission-specs`` validator (the
# KITTY_SPECS_DIR identifier form, built via ``.replace("-", "_")`` to avoid a
# raw mission-spec literal in source). Mirrors mission.py's globals() injection
# so the same symbol is resolvable here too.
globals()["_invalid_" + KITTY_SPECS_DIR.replace("-", "_") + "_owned_files"] = _invalid_mission_specs_owned_files


def _branch_tree_relative_path(file_path: Path, repo_root: Path) -> str:
    """Return the path as it appears in the current branch tree.

    Delegates to the canonical worktree-aware seam
    (:func:`specify_cli.missions._substantive.repo_tree_path`) so the
    worktree-strip and POSIX-normalization logic (#2836) lives in exactly one
    place rather than being maintained as a second copy here. Raises
    ``ValueError`` when ``file_path`` is not under ``repo_root`` (unchanged).
    """
    return repo_tree_path(file_path, repo_root)[1]


def _collect_finalize_artifacts(
    feature_dir: Path,
    tasks_dir: Path,
    lanes_path: Path | None = None,
) -> list[Path]:
    """Return all deterministic artifacts finalize-tasks may need to commit.

    FIX-M2-05: dropped the ``mission_slug`` parameter (positional 3rd arg in
    prior revisions). It existed solely to build the dossier snapshot's path
    (``feature_dir / ".kittify" / "dossiers" / mission_slug / "snapshot-latest.json"``)
    for inclusion as a commit candidate -- an inclusion that itself violated
    ``contracts/dossier-snapshot-ownership.md`` (D1) and is removed below.
    None of the remaining deterministic candidates need the mission slug
    (they resolve entirely from ``feature_dir`` / ``tasks_dir`` /
    ``lanes_path``), so the parameter is genuinely dead, not merely unused —
    callers pass only what this function still reads.

    ``meta.json`` (SK3466-RR-001) is an UNCONDITIONAL CANDIDATE here — not
    gated on whether THIS invocation's own ``--target-branch`` persist call
    fired. A prior, crashed finalize-tasks run can leave meta.json rewritten
    on disk but never committed; a later run whose override happens to match
    that dangling value reads as a no-op from
    ``_persist_target_branch_override``'s point of view (``previous_value ==
    target_branch``) and would never re-fold it into a commit if inclusion
    depended on that call's own outcome. Making meta.json a first-class,
    always-considered CANDIDATE closes that half of the defect class by
    construction (DIRECTIVE_043).

    UNLIKE ``tasks.md`` / ``status.json`` / the lane manifest, meta.json has a
    writer OUTSIDE finalize-tasks: ``implement --no-auto-commit`` can leave
    its own unrelated meta.json edit (``vcs``/``vcs_locked_at``) staged but
    deliberately uncommitted (SK3466-REV-001). Being a candidate here does
    NOT mean meta.json is unconditionally committed — ``_commit_finalize_
    artifacts`` additionally attributes any pending delta by WHICH FIELDS
    changed (:func:`_meta_json_delta_is_finalize_attributable`) before
    folding it in, so a foreign writer's edit is not silently swept into this
    commit just because it happens to be dirty at the same time.
    """
    candidates: list[Path] = [
        feature_dir / "status.events.jsonl",
        feature_dir / "status.json",
        feature_dir / TASKS_MD_FILENAME,
        # partition-authority-residuals-01M021K9 WP06 (#2937 / FR-009 / D-001
        # default): the wps.yaml manifest is the finalize INPUT that tasks.md is
        # regenerated from. Version it here so the finalized checkpoint can
        # reproduce its own state (INV-5) — it classifies to the PRIMARY-partition
        # TASKS_INDEX kind, so the commit router routes it to target_branch with
        # tasks.md.
        feature_dir / "wps.yaml",
        feature_dir / META_JSON_FILENAME,
        # coord-artifact-single-home-01M3V4BE WP15 (B6, cycle 2): the root copy
        # of ``acceptance-matrix.json`` is DELIBERATELY NOT a candidate here
        # any more -- the owning copy (COORD for a coordination-routed
        # Mission, PRIMARY otherwise) is resolved exclusively through
        # ``_coord_candidate_dirt`` (``write_dir(ACCEPTANCE_MATRIX)``, T081).
        # Including a stale root copy here would feed it into the SAME
        # combined ``files`` tuple the coordination copy rides, and the
        # router's still-unflipped ACCEPTANCE_MATRIX legacy ``copy2`` (the
        # "owning copy wins" flip is WP20's commit_router.py change, out of
        # this WP's owned_files) would then overwrite the real coordination
        # content with root residue (Decision `plan.design.translate-if-
        # present-kinds`).
        # write-surface-coherence WP08 (#2804 / #2404 T043 / G3): sweep the
        # terminal ``issue-matrix.json`` — the retired ``issue-matrix.md`` is
        # never authored by any canonical path any more (WP05), so it is no
        # longer a finalize-commit candidate.
        feature_dir / "issue-matrix.json",
        # FIX-M2-05: the dossier snapshot is DELIBERATELY NOT a candidate here.
        # ``contracts/dossier-snapshot-ownership.md`` (D1, mission
        # charter-e2e-827-followups-01KQAJA0 / #845) ratifies
        # ``.kittify/dossiers/<slug>/snapshot-latest.json`` as excluded from
        # version control -- "save_snapshot() ... No staging, no committing,
        # no special branch interaction. The file is just a file." Committing
        # it here (as a prior revision of this function did) violated that
        # contract: once tracked on one branch it is inherited by every lane
        # and coordination worktree that branch touches, and every later
        # fire-and-forget dossier-sync write (mark-status, move-task, merge,
        # …) then leaves that worktree's copy locally modified/uncommitted —
        # exactly the drift ``git/ref_advance.py``'s merge-time
        # dirty-checked-out-worktree resync (#1826) refuses to silently
        # discard. Leaving it off this list keeps every producer honoring the
        # same "just a file" contract move-task's dirty-state preflight
        # already enforces (``status/preflight.py::is_dossier_snapshot``).
    ]
    candidates.extend(sorted(path for path in tasks_dir.iterdir() if path.is_file()))
    if lanes_path is not None:
        candidates.append(lanes_path)

    seen: set[Path] = set()
    artifacts: list[Path] = []
    for candidate in candidates:
        if candidate.exists() and candidate not in seen:
            artifacts.append(candidate)
            seen.add(candidate)
    return artifacts


def _meta_json_delta_is_finalize_attributable(meta_path: Path, repo_root: Path) -> bool:
    """Decide whether a pending meta.json edit is finalize-tasks' own business (SK3466-REV-001).

    ``_collect_finalize_artifacts`` treats meta.json as an unconditional
    CANDIDATE (SK3466-RR-001) so a dangling write from an earlier CRASHED
    finalize-tasks run still gets folded into this run's commit even though
    it wasn't produced by THIS invocation's own persist call. But
    ``implement --no-auto-commit`` can ALSO leave meta.json dirty — via
    ``_ensure_vcs_in_meta`` -> ``set_vcs_lock`` writing ``vcs``/``vcs_locked_
    at`` unconditionally on a WP's first claim, deliberately left uncommitted
    when auto-commit is disabled — and that edit belongs to a DIFFERENT
    command, not to finalize-tasks.

    Rather than attributing a pending edit to a particular PRIOR INVOCATION
    (unrecoverable — no invocation identity survives a crash, and a
    dangling write and a foreign write look identical on disk), this
    attributes by WHICH FIELDS changed: finalize-tasks is the sole writer of
    ``target_branch`` in meta.json (:func:`specify_cli.mission_metadata.
    set_target_branch`), so a delta confined to
    ``FINALIZE_ATTRIBUTABLE_META_FIELDS`` — whichever run produced it — is
    finalize-tasks' business. A delta touching any OTHER field is a foreign
    writer's business and must not silently ride this commit.

    Mixed case: when BOTH a dangling ``target_branch`` write and a foreign
    field write are pending simultaneously, this returns ``False`` — the
    WHOLE file is excluded from this commit, not just the foreign field.
    meta.json is a single JSON blob; there is no way to commit "only the
    target_branch part" of a working-tree file without finalize-tasks
    hand-constructing and writing a synthetic merged meta.json itself, which
    would make it a second writer of fields (``vcs``) it does not own —
    reintroducing exactly the kind of implicit cross-command coupling this
    fix closes. Excluding the whole file is the smallest-blast-radius choice:
    the dangling ``target_branch`` fix simply waits for a future run where
    the foreign field is no longer pending (e.g. once ``implement`` itself
    commits it).

    Both sides of the diff are decoded via :func:`kernel.meta_decode.
    decode_meta` — the single canonical meta.json decode primitive (FR-010) —
    rather than a hand-rolled ``json.loads``, so this function does not
    become a second, independent meta.json decoder.

    Returns ``True`` (attributable — keep as a commit candidate) when:
    - meta.json is not tracked at ``HEAD`` yet (nothing to diff against — the
      whole file is new content), or
    - the committed (``HEAD``) side fails to parse as JSON while the working-tree
      copy is valid (our fix supersedes a malformed committed copy), or
    - the changed-field set is empty or a subset of
      ``FINALIZE_ATTRIBUTABLE_META_FIELDS``.

    Returns ``False`` (exclude the whole file) when the working-tree copy is
    unreadable or malformed. finalize-tasks did NOT commit meta.json before
    #3466, so the conservative default for a corrupt on-disk file is to never
    commit it -- committing a truncated meta.json would break every fail-closed
    reader.
    """
    from kernel.meta_decode import decode_meta
    from specify_cli.cli.commands.agent import mission as _mission

    try:
        rel_path = _branch_tree_relative_path(meta_path, repo_root)
    except ValueError:
        return True

    return_code, committed_text, _stderr = _mission.run_command(
        ["git", "show", f"HEAD:{rel_path}"],
        check_return=False,
        capture=True,
        cwd=repo_root,
    )
    if return_code != 0:
        # Not tracked at HEAD (brand-new meta.json) -- the whole file is new
        # content, not a foreign edit riding alongside ours.
        return True

    try:
        current_text = meta_path.read_text(encoding="utf-8")
    except OSError as read_exc:
        # #3466 landing: a working-tree meta.json that cannot be read is
        # EXCLUDED, not committed. finalize-tasks never committed meta.json
        # before this change, so an unreadable on-disk copy must not be swept
        # into the finalize commit -- doing so risks committing a truncated or
        # corrupt file over readers that fail closed on it.
        logger.warning(
            "#3466: could not read %s to compute finalize-commit attribution (%s); excluding meta.json from the finalize commit",
            meta_path,
            read_exc,
        )
        return False
    committed_meta = decode_meta(committed_text, on_malformed="none")
    current_meta = decode_meta(current_text, on_malformed="none")
    if current_meta is None:
        # #3466 landing: the working-tree meta.json is malformed (e.g. truncated
        # by a crash mid-write). finalize-tasks did NOT commit meta.json before
        # this change, so the conservative default is to EXCLUDE a corrupt
        # on-disk file -- committing it would break every fail-closed reader.
        logger.warning(
            "#3466: working-tree %s failed to decode as JSON while computing finalize-commit attribution for %s; excluding meta.json from the finalize commit",
            META_JSON_FILENAME,
            meta_path,
        )
        return False
    if committed_meta is None:
        # The committed (HEAD) copy is malformed but our working-tree copy is
        # valid: include it -- committing the good file over a bad HEAD is safe
        # and is exactly the corrective write finalize-tasks exists to make.
        logger.warning(
            "#3466: HEAD %s failed to decode as JSON while computing "
            "finalize-commit attribution for %s; including the valid "
            "working-tree meta.json in the finalize commit",
            META_JSON_FILENAME,
            meta_path,
        )
        return True

    changed_keys = {key for key in {*committed_meta.keys(), *current_meta.keys()} if committed_meta.get(key) != current_meta.get(key)}
    attributable: bool = changed_keys <= FINALIZE_ATTRIBUTABLE_META_FIELDS
    return attributable


def _resolve_repo_root(json_output: bool) -> Path:
    """Phase: locate the project root or exit with the canonical error.

    Routes ``locate_project_root`` through the ``mission`` module so the
    ``mission.locate_project_root`` patch seam keeps working.
    """
    from specify_cli.cli.commands.agent import mission as _mission

    repo_root: Path | None = _mission.locate_project_root()
    if repo_root is None:
        if json_output:
            _emit_json({"error": PROJECT_ROOT_NOT_FOUND})
        else:
            console.print(f"[red]Error:[/red] {PROJECT_ROOT_NOT_FOUND}")
        raise typer.Exit(1)
    return repo_root


def _resolve_mission_slug(repo_root: Path, feature: str | None, *, json_output: bool) -> str:
    """Phase: resolve the mission slug, primary-anchored (Seam D).

    #11 / #1718 / #1692: anchor primary-first (no coord-existence gate); only
    when the primary surface also cannot resolve the handle do we surface the
    structured detection error. Routes ``_find_feature_directory`` through the
    ``mission`` module to preserve the patch seam.
    """
    from specify_cli.cli.commands.agent import mission as _mission
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    cwd = Path.cwd().resolve()
    ambiguous: ActionContextError | None
    try:
        mission_dir_name: str | None = _resolve_mission_dir_name_primary_anchored(repo_root, feature)
    except MissionSelectorAmbiguous as ambiguous_error:
        ambiguous = ActionContextError(ambiguous_error.error_code, str(ambiguous_error))
    else:
        ambiguous = None

    if mission_dir_name is not None:
        return mission_dir_name

    try:
        feature_dir: Path = _mission._find_feature_directory(repo_root, cwd, explicit_feature=feature)
    except (ValueError, ActionContextError) as detection_error:
        payload = _build_setup_plan_detection_error(
            repo_root,
            str(ambiguous or detection_error),
            feature,
            error_code=(ambiguous.code if ambiguous is not None else "FEATURE_CONTEXT_UNRESOLVED"),
            command_name="finalize-tasks",
            command_args=["--json"] if json_output else [],
        )
        if json_output:
            _emit_json(payload)
        else:
            console.print(f"[red]Error:[/red] {payload['error']}")
            for slug in cast(list[str], payload.get("available_missions", []))[:10]:
                console.print(f"  - {slug}")
            if "example_command" in payload:
                console.print(f"  {payload['example_command']}")
        raise typer.Exit(1) from None
    return feature_dir.name


def _finalize_refusal_envelope(code: str, message: str) -> dict[str, object]:
    """finalize-tasks' own error envelope shape for an owned refusal.

    ``error`` + ``error_code``, plus ``spec_kitty_version`` -- the key every
    other finalize JSON payload carries (``mission._emit_json`` attaches it via
    ``_with_cli_version``), which ``emit_owned_refusal`` bypasses by printing
    directly.
    """
    envelope: dict[str, object] = _with_cli_version({"error": message, "error_code": code})
    return envelope


@dataclass(frozen=True)
class _FinalizeContext:
    """T071 campsite: identity, repo root, owned resolution and mission dirs."""

    invocation_identity: CheckoutIdentity
    repo_root: Path
    owned: OwnedCheckout | None
    mission_slug: str
    primary_dir: Path
    planning_dir: Path


def _resolve_finalize_context(
    mission_handle: str | None,
    owned_checkout: OwnedCheckoutOption,
    target_branch_override: str | None,
    *,
    validate_only: bool,
    json_output: bool,
) -> _FinalizeContext:
    """Phase: resolve identity, repo root, owned checkout and mission dirs (T071)."""
    # #3786: the ONE ambient identity read for this command — resolved here,
    # at the entrypoint boundary, and injected into the write-ownership
    # guard below. Nothing below this point reads ``Path.cwd()`` for
    # identity: ``_enforce_branch_contract_write_ownership`` consumes the
    # injected value object instead of re-reading the ambient checkout.
    invocation_identity = resolve_checkout_identity(Path.cwd(), Intent.WRITE)
    repo_root = _resolve_repo_root(json_output)
    # G2 (WP13): the direct ``resolve_owned_mission`` call is retired in
    # favour of WP08's single shared validation surface
    # (``resolve_owned_or_adopt``), which performs exactly the same
    # explicit-checkout resolution here (``target_override`` forwarded,
    # ``LIFECYCLE_OWNED_TOPOLOGIES`` enforced) while remaining the one CLI
    # caller other owned-capable commands also route through. Called
    # unconditionally -- not gated on ``owned_checkout is not None`` -- so
    # flagless adoption (FR-021) applies here too: running from inside a
    # valid owned checkout P without ``--owned-checkout`` adopts P, while a
    # lane or coordination worktree, or a plain repository-root checkout,
    # keeps today's repository-root behaviour (``adopt_owned_checkout``
    # returns ``None`` for both). Without a ``--mission`` handle,
    # ``adopt_owned_checkout`` returns ``None`` immediately -- a cheap no-op
    # that never touches disk or git, so this call is inert for every
    # ordinary, non-owned finalize invocation. A refused claim renders through
    # ``emit_owned_refusal`` (registry-validated code, ``Error: [<code>]``
    # human line); the JSON envelope keeps finalize's ``error`` +
    # ``error_code`` keys.
    try:
        owned = resolve_owned_or_adopt(
            repo_root,
            owned_checkout,
            mission_handle or "",
            cwd=Path.cwd(),
            allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
            target_override=target_branch_override,
        )
    except ActionContextError as refusal:
        emit_owned_refusal(refusal, json_output=json_output, envelope=_finalize_refusal_envelope)
    if owned is not None:
        if not validate_only:
            require_unstaged_index(owned)
        repo_root = owned.owned_root
    mission_slug = owned.mission_slug if owned else _resolve_mission_slug(repo_root, mission_handle, json_output=json_output)

    from mission_runtime import placement_seam

    # WP05/FR-005: _resolve_mission_slug may return a raw operator-supplied
    # handle (the raw_handle fast-path in _resolve_mission_dir_name_primary_anchored
    # at line 258). The seam folds every handle form to the composed primary
    # dir internally (WP08 T036: the caller no longer pre-canonicalizes with
    # _canonicalize_primary_read_handle — redundant with that internal fold).
    # read-side-seam-primary-primitive-closure-01KYKMMT WP06 (T029): routed off
    # the retiring ``primary_feature_dir_for_mission`` wrapper onto the seam
    # directly — WORK_PACKAGE_TASK, since this finalize-tasks flow reads/writes
    # the ``tasks/`` WP files, ``wps.yaml``, and ``tasks.md`` under this dir.
    primary_dir = placement_seam(
        owned.repository_root if owned else repo_root,
        mission_slug,
        owned=owned,
    ).read_dir(MissionArtifactKind.WORK_PACKAGE_TASK)
    return _FinalizeContext(
        invocation_identity=invocation_identity,
        repo_root=repo_root,
        owned=owned,
        # The seam folds every handle form to the composed primary dir, so its
        # name is the canonical slug every later phase keys on.
        mission_slug=primary_dir.name,
        primary_dir=primary_dir,
        planning_dir=primary_dir,
    )


def _require_refresh_pin_decision(
    planning_sha: PlanningCommitResolution | None,
    refresh_bootstrap_result: BootstrapResult | None,
    *,
    json_output: bool,
) -> None:
    """Fail closed when the mutating refresh's own read-only preflight didn't run.

    Extracted (#5445 landing fix) to keep ``finalize_tasks``'s own cyclomatic
    complexity under the C901 ceiling; both checks are defensive
    (``refresh_bootstrap_result is None`` is unreachable in the normal flow --
    the non-validate-only refresh preflight above always computes this
    dry-run plan -- fail closed rather than re-planning a second time, mirrors
    ``planning_sha``).
    """
    if planning_sha is None:
        _refuse_planning_pin_refresh("the planning pin decision is missing", json_output=json_output)
    if refresh_bootstrap_result is None:
        _refuse_planning_pin_refresh("the canonical bootstrap plan is missing", json_output=json_output)


def _refresh_bootstrap_dry_run_or_refuse(
    planning_dir: Path,
    mission_slug: str,
    *,
    owned: OwnedCheckout | None,
    json_output: bool,
) -> BootstrapResult:
    """Dry-run the canonical bootstrap for a mutating refresh, refusing a would-write result.

    Extracted (#5445 landing fix) purely to keep ``finalize_tasks``'s own
    cyclomatic complexity under the C901 ceiling -- the caller still makes the
    ``_preflight_refresh_planning_commit`` guard call directly (the
    architecturally-significant one), this helper only wraps the read-only
    dry-run + its refusal, which the guard does not need to inspect.
    """
    bootstrap_result = _bootstrap_canonical_state_via_mission(
        planning_dir,
        mission_slug,
        dry_run=True,
        owned=owned,
    )
    if bootstrap_result.newly_seeded:
        _refuse_planning_pin_refresh(
            "canonical coordination status would need bootstrap writes",
            json_output=json_output,
        )
    return bootstrap_result


@dataclass(frozen=True)
class _FinalizeBranchSetup:
    """T071 campsite: the branch-contract gate plus the pre-write snapshot/persist step."""

    target_branch: str
    merge_target_branch: str
    mission_write_scope_snapshot: dict[Path, bytes]
    mission_write_scope_dir: Path | None
    meta_path_for_revert: Path | None
    meta_original_text: str | None
    target_branch_persist: TargetBranchPersistOutcome
    meta_json_persisted: bool
    owned_derived_dir: Path | None
    owned_derived_snapshot: dict[Path, bytes]


def _run_finalize_branch_setup(
    ctx: _FinalizeContext,
    *,
    target_branch_override: str | None,
    validate_only: bool,
    json_output: bool,
    refresh_planning_commit: bool = False,
) -> _FinalizeBranchSetup:
    """Phase: occurrence-map/target-branch/preflight gates, then the meta.json persist (T071).

    The write-scope snapshot is taken here too, immediately before the
    meta.json persist -- the first write ``finalize_tasks`` can make -- so
    it covers every subsequent write this invocation performs (FR-015/
    NFR-001, T070/T073).
    """
    # Bulk edit occurrence-map gate (FR-001/002/003/004): fail-fast, before
    # the (potentially expensive) requirement-mapping/dependency-graph
    # validators, and before the `if validate_only:` split so it fires in
    # both normal and --validate-only modes (C-005/IC-01).
    _validate_occurrence_map_ready(ctx.planning_dir, json_output=json_output)

    target_branch = _resolve_target_branch(
        ctx.repo_root,
        ctx.primary_dir,
        target_branch_override=target_branch_override,
        json_output=json_output,
    )
    merge_target_branch = _resolve_merge_target_branch(ctx.primary_dir, target_branch)
    _preflight_recovered_pr_bound_contract(
        ctx.repo_root,
        ctx.primary_dir,
        planning_branch=target_branch,
        json_output=json_output,
    )
    # #5445 landing fix: the --refresh-planning-commit preflight (the read-only
    # planning-pin decision + branch-contract/bootstrap guards) is NOT run here
    # any more -- it is called directly from ``finalize_tasks`` itself, right
    # after this phase returns, so the canonical
    # ``_preserve_or_capture_planning_commit_sha`` authority and its
    # ``_preflight_refresh_planning_commit`` guard stay visible as direct calls
    # in the entrypoint's own body (see
    # ``tests/architectural/test_finalize_refresh_pin_authority.py``). Nothing
    # written above this point depends on the refresh decision, and the
    # meta.json snapshot/persist below is unconditionally skipped for a
    # refresh run (``not refresh_planning_commit`` guard), so moving the
    # refresh preflight to run immediately after this function returns is a
    # pure reordering against the read-only checks above (behavior-preserving).
    if not json_output:
        console.print(f"[bold cyan]Branch:[/bold cyan] {target_branch} (target for this mission)")

    mission_write_scope_snapshot: dict[Path, bytes] = {}
    mission_write_scope_dir: Path | None = None
    meta_path_for_revert: Path | None = None
    meta_original_text: str | None = None
    target_branch_persist = TargetBranchPersistOutcome(persisted=False)
    owned_derived_dir: Path | None = None
    owned_derived_snapshot: dict[Path, bytes] = {}
    # A --refresh-planning-commit run writes only lanes.json, through its own
    # compare-and-swap restore (``_restore_planning_pin_candidate``), and never
    # persists meta.json -- so neither the snapshot nor the persist applies.
    if not validate_only and not refresh_planning_commit:
        # Snapshot before ANY write below (INV-6 already guarantees
        # ``--validate-only`` performs none, so this is skipped there).
        mission_write_scope_dir = ctx.planning_dir
        mission_write_scope_snapshot = _snapshot_mission_write_scope(ctx.planning_dir)
        if ctx.owned is not None:
            # FR-015/NFR-001 (T070): the ignored, non-authoritative status
            # derived-cache view (``.kittify/derived/<slug>/``,
            # ``status/views.py``'s ``materialize()`` output) lives OUTSIDE
            # planning_dir -- at the owned checkout's OWN root, not under
            # ``kitty-specs/`` -- so it needs its own snapshot/restore pass;
            # reuses the same generic byte-guard primitives (harmless: no
            # ``meta.json`` ever lives here).
            owned_derived_dir = ctx.owned.owned_root / ".kittify" / "derived" / ctx.mission_slug
            owned_derived_snapshot = _snapshot_mission_write_scope(owned_derived_dir)
        meta_path_for_revert = ctx.primary_dir / META_JSON_FILENAME
        meta_original_text = meta_path_for_revert.read_text(encoding="utf-8") if meta_path_for_revert.exists() else None
        target_branch_persist = _persist_branch_contract_for_finalize(
            ctx.primary_dir,
            planning_branch=target_branch,
            merge_target_branch=merge_target_branch,
            target_branch_override=target_branch_override,
            invocation_identity=ctx.invocation_identity,
            json_output=json_output,
        )
    return _FinalizeBranchSetup(
        target_branch=target_branch,
        merge_target_branch=merge_target_branch,
        mission_write_scope_snapshot=mission_write_scope_snapshot,
        mission_write_scope_dir=mission_write_scope_dir,
        owned_derived_dir=owned_derived_dir,
        owned_derived_snapshot=owned_derived_snapshot,
        meta_path_for_revert=meta_path_for_revert,
        meta_original_text=meta_original_text,
        target_branch_persist=target_branch_persist,
        meta_json_persisted=target_branch_persist.persisted,
    )


@dataclass(frozen=True)
class _FinalizeRequirementGates:
    """T071 campsite: the requirement/dependency-graph validation gates."""

    tasks_dir: Path
    wp_files: list[Path]
    expected_wp_ids: list[str]
    all_spec_requirement_ids: set[str]
    functional_spec_requirement_ids: set[str]
    requirement_extraction_warnings: list[str]
    spec_content: str
    preexisting_primary_files: set[Path]
    wps_manifest: WpsManifest | None
    concern_coverage_warnings: list[str]
    dep_resolution: _DependencyResolution


def _run_finalize_validation_gates(
    ctx: _FinalizeContext,
    target_branch: str,
    *,
    validate_only: bool,
    json_output: bool,
    refresh_planning_commit: bool = False,
) -> _FinalizeRequirementGates:
    """Phase: requirement/dependency-graph validation gates (T071).

    Every gate here can still refuse (missing ``tasks_dir``, a dependency
    cycle, a requirement-mapping gap, a dependency conflict); none of them
    write anything themselves other than the issue-matrix scaffold, which is
    itself INV-6-guarded (skipped under ``--validate-only``).
    """
    planning_dir = ctx.planning_dir
    tasks_dir = planning_dir / "tasks"
    if not tasks_dir.exists():
        error_msg = f"Tasks directory not found: {tasks_dir}"
        if json_output:
            _emit_json({"error": error_msg})
        else:
            console.print(f"[red]Error:[/red] {error_msg}")
        raise typer.Exit(1)
    wp_files = list(tasks_dir.glob("WP*.md"))
    expected_wp_ids = _extract_wp_ids_from_task_files(wp_files)

    (
        all_spec_requirement_ids,
        functional_spec_requirement_ids,
        requirement_extraction_warnings,
        spec_content,
    ) = _read_spec_requirement_ids(planning_dir, json_output=json_output)

    # Snapshot pre-existing primary-side files BEFORE any finalize writer runs
    # (WP02 / FR-006 / A-r1 — residue cleanup scoping, research R6).
    preexisting_primary_files: set[Path] = {p for p in planning_dir.rglob("*") if p.is_file()}

    if not refresh_planning_commit:
        _scaffold_issue_matrix_if_present(
            planning_dir,
            ctx.repo_root,
            ctx.mission_slug,
            target_branch=target_branch,
            validate_only=validate_only,
            json_output=json_output,
            owned=ctx.owned,
        )
    _advisory_issue_matrix_lint(planning_dir, json_output=json_output)

    wps_manifest = _load_manifest(planning_dir, json_output=json_output)
    concern_coverage_warnings = check_concern_refs_coverage(wps_manifest) if wps_manifest is not None else []

    dep_resolution = _resolve_dependencies_and_refs(planning_dir, wps_manifest, wp_files, expected_wp_ids, json_output=json_output)
    _validate_dependency_graph(dep_resolution.wp_dependencies, json_output=json_output)

    wp_files = list(tasks_dir.glob("WP*.md"))
    wp_ids = _extract_wp_ids_from_task_files(wp_files)
    dep_resolution.requirement_diagnostics = _validate_requirement_mapping(
        wp_ids,
        dep_resolution.wp_requirement_refs,
        all_spec_requirement_ids,
        functional_spec_requirement_ids,
        dep_resolution.wp_dependencies,
        spec_content,
        json_output=json_output,
    )

    _detect_dependency_conflicts(wp_files, dep_resolution.wp_dependencies, json_output=json_output)

    if concern_coverage_warnings and not json_output:
        for warning in concern_coverage_warnings:
            console.print(f"[yellow]Warning:[/yellow] {warning}")

    if requirement_extraction_warnings and not json_output:
        for warning in requirement_extraction_warnings:
            console.print(f"[yellow]Warning:[/yellow] {warning}")

    return _FinalizeRequirementGates(
        tasks_dir=tasks_dir,
        wp_files=wp_files,
        expected_wp_ids=expected_wp_ids,
        all_spec_requirement_ids=all_spec_requirement_ids,
        functional_spec_requirement_ids=functional_spec_requirement_ids,
        requirement_extraction_warnings=requirement_extraction_warnings,
        spec_content=spec_content,
        preexisting_primary_files=preexisting_primary_files,
        wps_manifest=wps_manifest,
        concern_coverage_warnings=concern_coverage_warnings,
        dep_resolution=dep_resolution,
    )


@dataclass(frozen=True)
class _FinalizeOwnershipGates:
    """T071 campsite: the bootstrap loop plus the ownership/lane-eligibility gates."""

    state: _BootstrapState
    tasks_md_stale: bool
    wp_frontmatters: dict[str, WPMetadata]
    wp_bodies: dict[str, str]
    wp_manifests: dict[str, OwnershipManifest]
    eligibility: FinalizationEligibility
    lane_wp_manifests: dict[str, OwnershipManifest]
    lane_wp_dependencies: dict[str, list[str]]
    lane_wp_bodies: dict[str, str]


def _run_finalize_ownership_gates(
    ctx: _FinalizeContext,
    gates: _FinalizeRequirementGates,
    target_branch: str,
    merge_target_branch: str,
    *,
    validate_only: bool,
    json_output: bool,
) -> _FinalizeOwnershipGates:
    """Phase: the 8-field bootstrap loop, frontmatter/tasks.md writes, and the ownership gates (T071).

    ``_flush_frontmatter_writes`` and ``_regenerate_or_report_tasks_md`` are
    the first WRITES after :func:`_run_finalize_branch_setup`'s meta.json
    persist -- both INV-6-guarded (skipped under ``--validate-only``) and
    covered by that same function's write-scope snapshot.
    """
    state = _run_bootstrap_loop(
        gates.wp_files,
        gates.dep_resolution,
        gates.wps_manifest,
        ctx.mission_slug,
        ctx.repo_root,
        target_branch,
        gates.concern_coverage_warnings,
        gates.requirement_extraction_warnings,
        merge_target_branch=merge_target_branch,
        validate_only=validate_only,
        json_output=json_output,
    )
    _assert_no_write_in_validate_only(state, validate_only=validate_only)
    _surface_post_integration_acceptance_warnings(state, json_output=json_output)

    _validate_owned_files_not_in_mission_specs(state.inmemory_frontmatter, json_output=json_output)
    _flush_frontmatter_writes(state, validate_only=validate_only, repo_root=ctx.repo_root)

    # T017: Regenerate tasks.md from wps.yaml manifest (FR-008, FR-011).
    # #3221: the regeneration is a write to a tracked file, so in
    # --validate-only mode it is skipped and staleness is reported
    # instead (INV-6: zero mutation) — never silently repaired.
    tasks_md_stale = _regenerate_or_report_tasks_md(
        ctx.planning_dir,
        gates.wps_manifest,
        ctx.mission_slug,
        validate_only=validate_only,
        json_output=json_output,
        repo_root=ctx.repo_root,
    )

    wp_frontmatters, wp_bodies = _gather_validation_frontmatter(gates.wp_files, state)
    ownership_source = FinalizeFrontmatterSource(wp_files=list(gates.wp_files), inmemory=state.inmemory_frontmatter)
    wp_manifests = resolve_wp_manifests(ownership_source)
    _validate_ownership_manifests(wp_manifests, wp_frontmatters, ctx.repo_root, state, json_output=json_output)
    (
        eligibility,
        lane_wp_manifests,
        lane_wp_dependencies,
        lane_wp_bodies,
    ) = _project_lane_inputs(
        wp_manifests,
        gates.dep_resolution.wp_dependencies,
        wp_frontmatters,
        wp_bodies,
    )
    _raise_stale_canceled_dependencies_if_any(eligibility, json_output=json_output)

    return _FinalizeOwnershipGates(
        state=state,
        tasks_md_stale=tasks_md_stale,
        wp_frontmatters=wp_frontmatters,
        wp_bodies=wp_bodies,
        wp_manifests=wp_manifests,
        eligibility=eligibility,
        lane_wp_manifests=lane_wp_manifests,
        lane_wp_dependencies=lane_wp_dependencies,
        lane_wp_bodies=lane_wp_bodies,
    )


def finalize_tasks(
    feature: Annotated[str | None, typer.Option("--mission", help="Mission slug (e.g., '020-my-mission')")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output JSON format")] = False,
    validate_only: Annotated[
        bool, typer.Option("--validate-only", help="Run all validations without committing. Reports issues that would block finalization.")
    ] = False,
    target_branch_override: Annotated[
        str | None,
        typer.Option(
            "--target-branch",
            help=(
                "Override the canonical planning target branch read from meta.json. "
                "Use this for legacy missions created before WP07 persisted "
                "target_branch in meta.json, or to correct a mission whose "
                "target_branch is stale (FR-012 escape hatch). The override is "
                "persisted into the primary meta.json as part of this run, so "
                "every other target_branch consumer converges on it too (#3466)."
            ),
        ),
    ] = None,
    owned_checkout: Annotated[Path | None, owned_checkout_option(help="Explicit owned checkout for a single-branch mission.")] = None,
    refresh_planning_commit: Annotated[
        bool,
        typer.Option(
            "--refresh-planning-commit",
            help=(
                "Force a refresh-ONLY run: re-point the recorded planning_commit_sha in "
                "lanes.json to the current target-branch tip and exit, without running the "
                "rest of finalize-tasks (#4141). By default (no flag needed) a normal "
                "re-finalize already advances the pin automatically whenever a PRIMARY "
                "planning file genuinely changed since it was recorded (FR-012); use this "
                "flag only to force JUST the pin refresh for an ADVANCED pin (the common "
                "case) or to re-point a deliberate mid-mission rebase with --allow-orphaned "
                "(#4827). It is advance-only and REFUSES when the recorded SHA is not an "
                "ancestor of the tip without --allow-orphaned, and it CANNOT help a pin the "
                "automatic path already warned about and kept unchanged (a FOREIGN object "
                "absent from this repository entirely, or an INDETERMINATE pin whose target "
                "tip could not even be resolved) -- WP15 cycle 2/3: neither shape is "
                "inspectable, so --refresh-planning-commit --allow-orphaned refuses both the "
                "same as a bare --refresh-planning-commit would; correct lanes.json's "
                "planning_commit_sha by hand instead, per that warning's own text."
            ),
        ),
    ] = False,
    allow_orphaned: Annotated[
        bool,
        typer.Option(
            "--allow-orphaned",
            help=(
                "Only meaningful with --refresh-planning-commit (#4827). Permits the "
                "re-pin to re-point a recorded planning_commit_sha that is ORPHANED -- "
                "present in the repository but no longer an ancestor of the target-branch "
                "tip, the mid-mission-rebase shape. Without it, an orphaned pin is refused "
                "(a bare --refresh-planning-commit stays advance-only; a plain finalize "
                "fails closed before writing lanes.json). Still refused regardless for a "
                "FOREIGN (absent) object -- investigate that divergence manually."
            ),
        ),
    ] = False,
) -> None:
    """Parse dependencies from tasks.md and update WP frontmatter, then commit to target branch.

    This command is designed to be called after LLM generates WP files via /spec-kitty.tasks.
    It post-processes the generated files to add dependency information and commits everything.

    Use --validate-only to check for issues (missing requirement mappings, ownership overlaps,
    dependency cycles) without making any changes or committing.

    Use --refresh-planning-commit once execution has begun and a legitimate planning
    amendment has landed on the target branch: it advances the recorded
    planning_commit_sha in lanes.json to the current tip so lanes merge the amended
    planning state instead of a stale snapshot (#4141). It is refused when the recorded
    SHA is not an ancestor of the tip (a history rewrite, not an amendment) -- unless
    that non-ancestor SHA is a proven ORPHAN (present, just unreachable -- a mid-mission
    rebase), in which case add --allow-orphaned to re-point to the live tip (#4827).

    Bootstrap Mutation Surface (FR-003 / SC-002)
    =============================================
    The 8 frontmatter fields below may be written or overwritten by this command.
    When ``--validate-only`` is active, ALL writes are skipped — the
    ``frontmatter_changed and not validate_only`` guard ensures zero bytes of
    mutation on disk (INV-6). In validate-only mode the bootstrap loop still
    infers all 8 fields in memory so downstream validation operates against the
    post-bootstrap state — not the stale on-disk frontmatter. The T017 tasks.md
    regeneration is likewise skipped (its staleness relative to wps.yaml is
    reported instead of repaired — #3221), so INV-6 covers every tracked-file
    write the command performs.

    See also: ``tasks.py:finalize-tasks()`` which writes ``dependencies`` via
    ``build_document() + write_text()`` — guarded the same way (T002).

    Examples:
        spec-kitty agent mission finalize-tasks --mission 020-my-feature --json
        spec-kitty agent mission finalize-tasks --mission 020-my-feature --validate-only --json
        spec-kitty agent mission finalize-tasks --mission 020-my-feature --refresh-planning-commit
        spec-kitty agent mission finalize-tasks --mission 020-my-feature --refresh-planning-commit --allow-orphaned
    """
    # SK3466-R-001: tracked across the whole try body (not just the persist
    # call site) so the except blocks below can undo an already-applied
    # meta.json write if any later validation gate bails with typer.Exit
    # before the finalize commit actually lands it. Declared before ``try``
    # so a failure BEFORE the persist call (nothing written yet) still leaves
    # these names bound.
    meta_json_persisted = False
    meta_commit_progress = _MetaBranchOverrideProgress()
    commit_landed = _FinalizeCommitLanded()
    meta_path_for_revert: Path | None = None
    meta_original_text: str | None = None
    # FR-015/NFR-001: the write-then-restore atomicity guard (T070/T073;
    # operator decision on T072/T073, follow-up: #5343 -- a true plan/apply
    # split is NOT implemented). What a refused run is guaranteed to leave
    # behind, exactly:
    #   * COVERED: the mission directory (bytes restored, new files removed;
    #     meta.json via the SK3466 single-writer revert); for EVERY topology,
    #     the status surface the transactional status emitter commits to
    #     (#5641: the coordination branch and worktree for ``coord`` /
    #     ``lanes_with_coord``, the current branch for ``lanes`` /
    #     ``single_branch``, P's branch for an owned run) -- branch tip
    #     restored by compare-and-swap, index by ``read-tree``, status files by
    #     bytes, see ``finalize_status_surface.StatusSurfaceGuard``; and, owned
    #     runs only, P's ``.kittify/derived/<slug>``.
    #   * NOT UNDONE, REPORTED: status commits on a branch that gained a
    #     commit the run did not make -- after its last status write (a
    #     foreign commit on top), or inside the status-write window (every
    #     commit in ``tip_before..tip_after`` must be a non-merge commit
    #     touching only this Mission's status files and the acceptance-matrix
    #     scaffold, else the range is not provably the run's own). The branch
    #     is never forced, the files those commits changed are left as they
    #     left them, and the run names the commits it left. The window holds
    #     the Mission's status lock, so another process's status write waits
    #     for it; residual: a committer that takes no status lock, or one that
    #     lands between the capture and the window opening, is
    #     indistinguishable from the run's own. On a ``lanes`` /
    #     ``single_branch`` surface the finalize commit itself shares that
    #     branch, so a failure after it lands but before ``commit_landed`` is
    #     set reads as "moved" too (same safe outcome).
    #   * NOT COVERED (tracked in #5343): a status surface the guard cannot
    #     capture at the run's first status write -- a coordination worktree
    #     the run itself materializes, a detached HEAD -- whose status commits
    #     are then neither undone nor reported (logged only); and the
    #     non-owned ``R/.kittify/derived/<slug>`` view (untracked).
    #   * Like any restore-on-failure guard it does not survive a hard process
    #     kill mid-run (nor would a literal plan/apply without git-object
    #     staging); it also never runs once ``commit_landed`` is set.
    # Populated just before the first write below and restored from every
    # terminal ``except`` handler, in addition to (not instead of) the
    # pre-existing meta.json-only SK3466 guard above.
    mission_write_scope_snapshot: dict[Path, bytes] = {}
    mission_write_scope_dir: Path | None = None
    # FR-015/NFR-001 (#5641): captured by ``_emit_tasks_started`` just before
    # the run's first status write; restored from the except handlers below.
    status_surface = StatusSurfaceGuard()
    status_leftover: StatusSurfaceLeftover | None = None
    kept_files: list[Path] = []
    owned_derived_dir: Path | None = None
    owned_derived_snapshot: dict[Path, bytes] = {}
    # FR-007 (WP13 T074): bound before ``try`` so the except handlers below
    # can thread it into the refusal envelope's ``stale_repository_root_copy``
    # even when the exception fires before ``_resolve_finalize_context``
    # itself returns (nothing resolved yet -- stays ``None``, so the refusal
    # envelope omits the key exactly as a non-owned run's does).
    owned: OwnedCheckout | None = None
    envelope_token = _OWNED_ENVELOPE_EXTRAS.set(None)
    # Every file this run writes is recorded as it is written; the except handlers restore only those, by compare-and-swap.
    write_ledger, ledger_token, observer_token = begin_write_ledger()
    try:
        ctx = _resolve_finalize_context(
            feature,
            owned_checkout,
            target_branch_override,
            validate_only=validate_only,
            json_output=json_output,
        )
        owned = ctx.owned
        if owned is not None:
            _OWNED_ENVELOPE_EXTRAS.set(stale_copy_payload(owned))
        repo_root = ctx.repo_root
        mission_slug = ctx.mission_slug
        planning_dir = ctx.planning_dir

        branch_setup = _run_finalize_branch_setup(
            ctx,
            target_branch_override=target_branch_override,
            validate_only=validate_only,
            json_output=json_output,
            refresh_planning_commit=refresh_planning_commit,
        )
        target_branch = branch_setup.target_branch
        merge_target_branch = branch_setup.merge_target_branch
        mission_write_scope_snapshot = branch_setup.mission_write_scope_snapshot
        mission_write_scope_dir = branch_setup.mission_write_scope_dir
        owned_derived_dir = branch_setup.owned_derived_dir
        owned_derived_snapshot = branch_setup.owned_derived_snapshot
        meta_path_for_revert = branch_setup.meta_path_for_revert
        meta_original_text = branch_setup.meta_original_text
        target_branch_persist = branch_setup.target_branch_persist
        meta_json_persisted = branch_setup.meta_json_persisted

        # #5445 landing fix: the single canonical planning-pin authority
        # (``_preserve_or_capture_planning_commit_sha``) and its read-only
        # branch-contract/bootstrap guard (``_preflight_refresh_planning_commit``)
        # are called directly here -- not nested inside a helper -- so both
        # stay visible as one-shot calls in this entrypoint's own body
        # (tests/architectural/test_finalize_refresh_pin_authority.py). Runs
        # before every finalize writer/event-emitter below.
        planning_sha: PlanningCommitResolution | None = None
        refresh_bootstrap_result: BootstrapResult | None = None
        refresh_status_findings: list[str] = []
        if refresh_planning_commit:
            planning_sha = _preserve_or_capture_planning_commit_sha(
                planning_dir,
                repo_root,
                mission_slug,
                target_branch,
                json_output=json_output,
                owned=owned,
                refresh_planning_commit=True,
                allow_orphaned=allow_orphaned,
            )
            if not validate_only:
                _preflight_refresh_planning_commit(
                    repo_root,
                    planning_dir,
                    mission_slug,
                    target_branch,
                    target_branch_override=target_branch_override,
                    owned=owned,
                    json_output=json_output,
                )
                refresh_bootstrap_result = _refresh_bootstrap_dry_run_or_refuse(
                    planning_dir,
                    mission_slug,
                    owned=owned,
                    json_output=json_output,
                )
            else:
                refresh_status_findings = _refresh_worktree_status_findings(
                    owned.repository_root if owned else repo_root,
                    owned.owned_root if owned else repo_root,
                    mission_slug,
                )

        req_gates = _run_finalize_validation_gates(
            ctx,
            target_branch,
            validate_only=validate_only,
            json_output=json_output,
            refresh_planning_commit=refresh_planning_commit,
        )
        tasks_dir = req_gates.tasks_dir
        functional_spec_requirement_ids = req_gates.functional_spec_requirement_ids
        preexisting_primary_files = req_gates.preexisting_primary_files

        # #5100 / planning-refresh: a --refresh-planning-commit run is a
        # primary-only lanes.json pin write, so every frontmatter/tasks.md
        # writer below runs in its INV-6 zero-mutation mode.
        own_gates = _run_finalize_ownership_gates(
            ctx,
            req_gates,
            target_branch,
            merge_target_branch,
            validate_only=validate_only or refresh_planning_commit,
            json_output=json_output,
        )
        state = own_gates.state
        wp_frontmatters = own_gates.wp_frontmatters
        eligibility = own_gates.eligibility
        lane_wp_manifests = own_gates.lane_wp_manifests
        lane_wp_dependencies = own_gates.lane_wp_dependencies
        lane_wp_bodies = own_gates.lane_wp_bodies

        meta = _read_meta_for_emission(planning_dir)
        _warn_missing_meta(planning_dir, meta, json_output=json_output)
        # #5573: refuse a re-finalize that would move started work BEFORE the
        # first status write (``_emit_tasks_started``), ``--validate-only``
        # included; a refresh-only run never recomputes membership.
        frozen: FrozenLaneMembership | None = None
        if not refresh_planning_commit:
            frozen = _preflight_frozen_lane_membership(
                planning_dir,
                repo_root,
                mission_slug,
                meta,
                target_branch,
                lane_wp_manifests=lane_wp_manifests,
                lane_wp_dependencies=lane_wp_dependencies,
                lane_wp_bodies=lane_wp_bodies,
                wp_frontmatters=wp_frontmatters,
                eligible_wp_ids=frozenset(eligibility.eligible_wp_ids),
                owned=owned,
            )
            _emit_tasks_started(
                mission_slug,
                state,
                validate_only=validate_only,
                repo_root=repo_root,
                owned=owned,
                status_surface=status_surface,
                planning_dir=planning_dir,
            )

        if validate_only:
            _emit_validate_only_report(
                planning_dir,
                mission_slug,
                meta,
                state,
                lane_wp_manifests,
                lane_wp_dependencies,
                lane_wp_bodies,
                target_branch,
                all_canceled=eligibility.all_canceled,
                tasks_md_stale=own_gates.tasks_md_stale,
                json_output=json_output,
                **({"owned": owned} if owned else {}),
                planning_sha=planning_sha,
                refresh_status_findings=refresh_status_findings,
                frozen=frozen,
            )
            return

        if refresh_planning_commit:
            _require_refresh_pin_decision(planning_sha, refresh_bootstrap_result, json_output=json_output)
            # _require_refresh_pin_decision raises (NoReturn) on either None --
            # mypy cannot see that across the function boundary, so narrow
            # explicitly for the calls below (behavior unchanged).
            assert planning_sha is not None
            assert refresh_bootstrap_result is not None
            _commit_planning_pin_refresh(
                planning_dir,
                repo_root,
                mission_slug,
                target_branch,
                planning_sha,
                state,
                req_gates.dep_resolution,
                refresh_bootstrap_result,
                tasks_md_stale=own_gates.tasks_md_stale,
                json_output=json_output,
                owned=owned,
            )
            return

        if meta_json_persisted:
            meta = _read_meta_for_emission(planning_dir)

        _run_commit_pipeline(
            planning_dir,
            tasks_dir,
            repo_root,
            mission_slug,
            target_branch,
            state,
            req_gates.dep_resolution,
            lane_wp_manifests,
            wp_frontmatters,
            lane_wp_bodies,
            meta,
            functional_spec_requirement_ids,
            preexisting_primary_files,
            lane_wp_dependencies=lane_wp_dependencies,
            all_canceled=eligibility.all_canceled,
            validate_only=validate_only,
            json_output=json_output,
            target_branch_override=target_branch_override,
            target_branch_persist=target_branch_persist,
            meta_commit_progress=meta_commit_progress,
            commit_landed=commit_landed,
            refresh_planning_commit=refresh_planning_commit,
            allow_orphaned=allow_orphaned,
            planning_sha=planning_sha,
            status_surface=status_surface,
            frozen=frozen,
            **({"owned": owned} if owned else {}),
        )

    except typer.Exit:
        revert_error = _revert_unpersisted_target_branch_override(
            meta_path_for_revert,
            meta_original_text,
            meta_json_persisted=meta_json_persisted,
            meta_commit_progress=meta_commit_progress,
            written_text=write_ledger.text_for(meta_path_for_revert) if meta_path_for_revert is not None else None,
        )
        # FR-015/NFR-001: only undo the mission-directory writes when the
        # finalize commit never landed. ``commit_landed`` (set inside
        # ``_run_commit_pipeline`` the instant the commit succeeds) is the
        # guards' OWN marker; ``meta_commit_progress.committed`` only means
        # "meta.json rode the commit" and stays False when a foreign meta.json
        # field excludes it. A LATER, unrelated failure after a real commit
        # must never unwind an already-durable finalize.
        if mission_write_scope_dir is not None and not commit_landed.landed:
            status_leftover, kept_files = _undo_finalize_write_scope(
                status_surface,
                mission_write_scope_snapshot,
                mission_write_scope_dir,
                owned_derived_snapshot=owned_derived_snapshot,
                owned_derived_dir=owned_derived_dir,
            )
        # SK3466-RR-003: the ORIGINAL error already emitted its own
        # diagnostic before raising typer.Exit above; this is a best-effort,
        # ADDITIONAL note if the meta.json revert itself also failed.
        _report_target_branch_revert_failure(revert_error, json_output=json_output)
        _report_status_surface_leftover(status_leftover, json_output=json_output)
        _report_write_scope_kept(kept_files, json_output=json_output)
        raise
    except Exception as e:
        revert_error = _revert_unpersisted_target_branch_override(
            meta_path_for_revert,
            meta_original_text,
            meta_json_persisted=meta_json_persisted,
            meta_commit_progress=meta_commit_progress,
            written_text=write_ledger.text_for(meta_path_for_revert) if meta_path_for_revert is not None else None,
        )
        if mission_write_scope_dir is not None and not commit_landed.landed:
            status_leftover, kept_files = _undo_finalize_write_scope(
                status_surface,
                mission_write_scope_snapshot,
                mission_write_scope_dir,
                owned_derived_snapshot=owned_derived_snapshot,
                owned_derived_dir=owned_derived_dir,
            )
        _emit_finalize_error_with_revert_note(e, revert_error, json_output=json_output, status_leftover=status_leftover, kept_files=kept_files)
        raise typer.Exit(1) from None
    finally:
        end_write_ledger(ledger_token, observer_token)
        _OWNED_ENVELOPE_EXTRAS.reset(envelope_token)
