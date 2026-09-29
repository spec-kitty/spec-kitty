"""Mission lifecycle commands for AI agents — thin command-registration shim.

#2056 SHIM (de-godded). This module WAS a ~4150-LOC / 62-symbol god module; the
``decompose-mission-god-module`` effort (https://github.com/Priivacy-ai/spec-kitty/issues/2056)
extracted every cohesive seam into a dedicated one-way leaf module. What remains
here is a thin shim that owns ONLY:

* the ``mission`` Typer ``app`` and its 9 ``@app.command`` registrations
  (each delegating to a seam command function), and
* a re-export block that keeps every historical ``mission.<name>`` patch
  target + ``from ...mission import <name>`` edge resolving (no business logic).

⚠️ Do NOT add new responsibilities here. Route new behavior to the relevant
seam and, if it must be patchable/importable as ``mission.<name>``, add a
deliberate ``as`` re-export below. Seam map (all one-way: seam → lower layers,
never back to ``mission``):

* feature-dir resolution        → ``mission_feature_resolution`` (Seam D, WP02)
* parsers / owned-files / emit   → ``mission_parsing``            (Seam C, WP03)
* record-analysis command        → ``mission_record_analysis``    (Seam A, WP04)
* branch-context + branch resolve → ``mission_branch_context``     (Seam B, WP05)
* check-prerequisites            → ``mission_check_prerequisites`` (WP05)
* create                         → ``mission_create``             (WP05)
* setup-plan + plan-commit       → ``mission_setup_plan``         (WP06)
* accept / merge delegators      → ``mission_accept_merge``       (WP06)
* finalize-tasks                 → ``mission_finalize``           (WP07)
* planning-commit primitives     → ``coordination.commit_router`` (WP08 of #2056)
* repair (Gap-2 cure)            → ``mission_repair`` (WP08 of coord-write-placement-closure-01KYCF83)
"""

from __future__ import annotations

from specify_cli.core.constants import (
    KITTY_SPECS_DIR,
)
import logging
from pathlib import Path

import typer
from specify_cli.cli.console import console
from typing import cast

# Re-exported so the WP06 merge seam's ``mission.resolve_mission_handle`` access
# and historical patch targets keep resolving.
from specify_cli.cli.selector_resolution import resolve_mission_handle as resolve_mission_handle
# Re-exported so the WP06 accept/merge seams can resolve the top-level delegators
# via the ``mission`` module — preserving both the lazy-import boundary (the seams
# never import the accept/merge graph at module scope) and the historical
# ``mission.top_level_accept`` / ``mission.top_level_merge`` patch targets.
from specify_cli.cli.commands.accept import accept as _accept
from specify_cli.cli.commands.consolidate import consolidate as _merge
from specify_cli.core.git_ops import get_current_branch as get_current_branch
from specify_cli.core.git_ops import is_git_repo as is_git_repo
from specify_cli.core.git_preflight import (
    build_git_preflight_failure_payload,
    run_git_preflight,
)
from specify_cli.core.paths import locate_project_root as locate_project_root
from specify_cli.core.paths import get_main_repo_root as get_main_repo_root
# Re-exported so the WP06 merge seam's ``mission.get_feature_target_branch``
# access keeps resolving.
from specify_cli.core.paths import get_feature_target_branch as get_feature_target_branch
from specify_cli.core.worktree import (
    validate_feature_structure as validate_feature_structure,
)

# #2056 WP07 finalize-tasks relocation: the following names were the finalize
# body's direct dependencies. ``finalize_tasks`` now lives in
# ``mission_finalize`` and imports them straight from their canonical modules,
# but they remain deliberate ``mission.<name>`` re-exports so historical patch
# targets (``mission.run_command``) and ``from ...mission import <name>``
# test/edge imports keep resolving. The ``as`` form marks them intentional
# (WP09 finalizes the comprehensive shim sweep).
from specify_cli.core.git_ops import run_command as run_command
from specify_cli.frontmatter import write_frontmatter as write_frontmatter
from specify_cli.status import WPMetadata as WPMetadata
from specify_cli.status import read_wp_frontmatter as read_wp_frontmatter
from specify_cli.status import bootstrap_canonical_state as bootstrap_canonical_state
from specify_cli.ownership import infer_ownership as infer_ownership
from specify_cli.ownership import validate_ownership as validate_ownership
from specify_cli.ownership.audit_targets import validate_audit_coverage as validate_audit_coverage
from specify_cli.ownership.frontmatter_source import (
    FinalizeFrontmatterSource as FinalizeFrontmatterSource,
    resolve_wp_manifests as resolve_wp_manifests,
)
from specify_cli.ownership.validation import validate_glob_matches as validate_glob_matches
from specify_cli.core.dependency_graph import detect_cycles as detect_cycles
from specify_cli.core.dependency_graph import validate_dependencies as validate_dependencies
from specify_cli.core.wps_manifest import (
    load_wps_manifest as load_wps_manifest,
    check_concern_refs_coverage as check_concern_refs_coverage,
    dependencies_are_explicit as dependencies_are_explicit,
    generate_tasks_md_from_manifest as generate_tasks_md_from_manifest,
)
from specify_cli.missions._resolve_planning_branch import (
    PlanningBranchResolutionFailed as PlanningBranchResolutionFailed,
)
# Re-exported so the setup-plan seam's historical patch boundary and configured
# content-template selection remain available after setup-plan extraction.
from specify_cli.runtime.resolver import (
    resolve_configured_template as resolve_configured_template,
)
from specify_cli.runtime.resolver import resolve_template as resolve_template

# Seam D (#2056 WP02): the shared feature-dir resolution surface lives in a
# dedicated one-way leaf module. These names are imported here (and re-exported
# from this module in WP09) so every historical ``mission.<name>`` patch target
# keeps resolving. INV-8: the seam imports lower layers only, never back here.
from specify_cli.cli.commands.agent.mission_feature_resolution import (
    _build_setup_plan_detection_error as _build_setup_plan_detection_error,
    _resolve_mission_dir_name_primary_anchored as _resolve_mission_dir_name_primary_anchored,
)

# Seam D pure re-exports (consumed by ``mission.<name>`` patch targets / test
# imports such as ``from ...mission import _read_feature_meta`` and
# ``_primary_anchored_feature_dir``; the WP05 lifecycle-families relocation moved
# the in-body callers into the check-prerequisites family). The ``as`` form marks
# them deliberate re-exports (WP09 finalizes the comprehensive shim sweep).
from specify_cli.cli.commands.agent.mission_feature_resolution import (
    _find_feature_directory as _find_feature_directory,
    _planning_read_dir as _planning_read_dir,
    _primary_anchored_feature_dir as _primary_anchored_feature_dir,
    _read_feature_meta as _read_feature_meta,
)

# Seam C (#2056 WP03): parsers, owned-files validators, and JSON-emit shims live
# in a dedicated one-way leaf module. Re-imported here so ``mission.<name>``
# patch targets and ``tasks.py``'s ``_parse_requirement_refs_from_tasks_md``
# import edge keep resolving (final shim sweep is WP09).
from specify_cli.cli.commands.agent.mission_parsing import (
    _emit_json as _emit_json,
    _extract_wp_ids_from_task_files as _extract_wp_ids_from_task_files,
    _invalid_mission_specs_owned_files,
    _owned_files_yaml_is_explicit_empty_list as _owned_files_yaml_is_explicit_empty_list,
    _parse_requirement_ids_from_spec_md as _parse_requirement_ids_from_spec_md,
    _parse_requirement_refs_from_tasks_md as _parse_requirement_refs_from_tasks_md,
    _raw_frontmatter_has_field as _raw_frontmatter_has_field,
)

# Seam C pure re-exports (consumed by ``mission.<name>`` patch targets; the WP05
# lifecycle-families relocation moved the in-body callers into the new family
# modules). The ``as`` form marks them deliberate (WP09 finalizes the sweep).
from specify_cli.cli.commands.agent.mission_parsing import (
    _emit_console_or_json_error as _emit_console_or_json_error,
    _utc_now_iso as _utc_now_iso,
)

# Explicit re-export (consumed by ``from ...mission import`` in other modules /
# tests, e.g. test_wp_header_regex_depth.py); the ``as`` form marks it a
# deliberate re-export so the lint does not flag it unused. (WP09 finalizes the
# comprehensive shim re-export sweep.)
from specify_cli.cli.commands.agent.mission_parsing import (
    _parse_wp_sections_from_tasks_md as _parse_wp_sections_from_tasks_md,
)

# Seam A (#2056 WP04): the record-analysis command + its two dedicated helpers
# (and the small _git_dirty_paths git helper) live in a one-way leaf module.
# Re-imported here so ``mission.<name>`` patch targets keep resolving; the
# command is registered on ``app`` below. WP09 completes the shim by also
# re-exporting the two record-analysis helpers that the WP04 relocation left
# importable only from the seam — ``_resolve_record_analysis_placement_ref`` and
# ``_enforce_analysis_report_write_preflight`` — so the historical
# ``from ...mission import <name>`` test imports (e.g.
# ``test_wp06_sc2_paused_mission_blockers.py``,
# ``tests/integration/test_protected_primary_spec_commit.py``) keep resolving.
from specify_cli.cli.commands.agent.mission_record_analysis import (
    record_analysis,
)
from specify_cli.cli.commands.agent.mission_record_analysis import (
    _enforce_analysis_report_write_preflight as _enforce_analysis_report_write_preflight,
    _resolve_record_analysis_placement_ref as _resolve_record_analysis_placement_ref,
)

# WP04 (write-side-seam-matrix-tracer-01KYP3MH / T015): the acceptance-verdict
# command is a one-way leaf, same shape as record-analysis above; it is
# registered on ``app`` below (mirrors the record-analysis registration
# idiom — the module owns the plain callable, this app registers it).
from specify_cli.cli.commands.agent.acceptance_verdict import acceptance_verdict

# Seam B / lifecycle families I (#2056 WP05): the branch-context command and the
# deterministic branch-resolution helpers it shares with setup-plan/finalize-tasks
# live in a one-way leaf module. Re-imported here so every historical
# ``mission.<name>`` patch target resolves AND the not-yet-relocated
# setup_plan/finalize_tasks/lifecycle callers (below) see ``mission.<name>``
# monkeypatches (they reference these re-imported module globals). The command is
# registered on ``app`` below (WP09 finalizes the shim sweep).
from specify_cli.cli.commands.agent.mission_branch_context import (
    branch_context as branch_context,
)
from specify_cli.cli.commands.agent.mission_branch_context import (
    _resolve_planning_branch as _resolve_planning_branch,
)

# Pure re-exports (consumed by ``mission.<name>`` patch targets / WP06's
# relocated callers, not referenced in this module's body); the ``as`` form
# marks them deliberate so the lint does not flag them unused.
# ``_get_current_branch`` / ``_show_branch_context`` are accessed via the
# ``mission`` module by the WP06 merge / setup-plan seams; ``_inject_branch_contract``
# is imported from ``mission`` by tests.
from specify_cli.cli.commands.agent.mission_branch_context import (
    _get_current_branch as _get_current_branch,
    _inject_branch_contract as _inject_branch_contract,
    _show_branch_context as _show_branch_context,
)
from specify_cli.cli.commands.agent.mission_branch_context import (
    _git_local_or_remote_branch_exists as _git_local_or_remote_branch_exists,
    _resolve_feature_target_branch as _resolve_feature_target_branch,
    _resolve_primary_branch_for_recommendation as _resolve_primary_branch_for_recommendation,
    _switch_to_start_branch as _switch_to_start_branch,
)

# Lifecycle families I (#2056 WP05): the check-prerequisites command, its emit
# helpers, and the shared ``meta.json`` readers live in a dedicated leaf module.
# Re-imported here so ``mission.check_prerequisites`` (the agent-alias dispatch
# target + patch target) and ``mission._read_meta_for_emission`` (finalize-tasks)
# keep resolving; the command is registered on ``app`` below.
from specify_cli.cli.commands.agent.mission_check_prerequisites import (
    check_prerequisites as check_prerequisites,
)
from specify_cli.cli.commands.agent.mission_check_prerequisites import (
    _read_meta_for_emission as _read_meta_for_emission,
)

# Pure re-exports (consumed by ``mission.<name>`` patch targets / WP05's
# create family, not referenced in this module's body); the ``as`` form marks
# them deliberate so the lint does not flag them unused.
from specify_cli.cli.commands.agent.mission_check_prerequisites import (
    _emit_check_prerequisites_detection_error as _emit_check_prerequisites_detection_error,
    _emit_check_prerequisites_result as _emit_check_prerequisites_result,
    _paths_only_payload as _paths_only_payload,
    _read_meta_for_pr_bound as _read_meta_for_pr_bound,
)

# Lifecycle families I (#2056 WP05): the ``create`` command, decomposed into
# ≤15-CC phase helpers, lives in a dedicated leaf module. Re-imported here so
# ``mission.create_mission`` keeps resolving — ``lifecycle.py`` binds
# ``agent.mission as agent_feature`` and calls ``agent_feature.create_mission``;
# the command is registered on ``app`` below.
from specify_cli.cli.commands.agent.mission_create import (
    create_mission as create_mission,
)

# Lifecycle families II (#2056 WP06): the ``setup-plan`` command (decomposed into
# ≤15-CC phase helpers) and its planning-commit helpers live in a dedicated leaf
# module. Re-imported here so ``mission.setup_plan`` (consumed by ``lifecycle.py``)
# and the test-imported ``CommitToBranchResult`` / ``_commit_to_branch`` /
# ``_kind_for_artifact`` keep resolving; the command is registered on ``app`` below.
from specify_cli.cli.commands.agent.mission_setup_plan import (
    setup_plan as setup_plan,
)
from specify_cli.cli.commands.agent.mission_setup_plan import (
    CommitToBranchResult as CommitToBranchResult,
    _commit_to_branch as _commit_to_branch,
    _kind_for_artifact as _kind_for_artifact,
)

# Lifecycle families II (#2056 WP06): the thin ``accept`` / ``merge`` delegators
# and the worktree finders live in a dedicated leaf module. Re-imported here so
# ``mission.accept_feature`` / ``mission.merge_feature`` (test imports) and the
# ``mission._find_feature_worktree`` patch target keep resolving; the commands
# are registered on ``app`` below.
from specify_cli.cli.commands.agent.mission_accept_merge import (
    accept_feature as accept_feature,
    merge_feature as merge_feature,
)
from specify_cli.cli.commands.agent.mission_accept_merge import (
    _find_feature_worktree as _find_feature_worktree,
    _find_latest_feature_worktree as _find_latest_feature_worktree,
)

# finalize-tasks family (#2056 WP07): ``finalize_tasks`` (the worst-offender
# 1227-LOC function, now decomposed into ≤15-CC phase helpers) plus its two
# dedicated helpers live in a one-way leaf module. Re-imported here so
# ``mission.finalize_tasks`` (consumed by ``lifecycle.py``) and the test-imported
# ``_collect_finalize_artifacts`` / ``_branch_tree_relative_path`` keep resolving;
# the command is registered on ``app`` below (WP09 finalizes the shim sweep). The
# finalize seam resolves the cross-cutting patched symbols (``locate_project_root``
# / ``_find_feature_directory`` / ``run_command``) THROUGH this module at call
# time, so those patch seams keep
# working without an import cycle.
from specify_cli.cli.commands.agent.mission_finalize import (
    finalize_tasks as finalize_tasks,
)
from specify_cli.cli.commands.agent.mission_finalize import (
    _branch_tree_relative_path as _branch_tree_relative_path,
    _collect_finalize_artifacts as _collect_finalize_artifacts,
)

# Planning-commit residue (#2056 WP08): ``_planning_commit_worktree`` /
# ``_resolve_planning_placement`` / ``_stage_finalize_artifacts_in_coord_worktree``
# were RELOCATED into the canonical ``coordination/commit_router`` (the staging
# helper collapsed into the router's existing ``_stage_artifacts_in_coord_worktree``).
# ``tasks.py`` now imports them straight from commit_router; these deliberate
# ``as`` re-exports keep the historical ``mission.<name>`` patch targets + test
# imports resolving (WP09 owns the final shim sweep). INV-8: one-way — the import
# flows mission → commit_router, never back.
from specify_cli.coordination.commit_router import (
    _planning_commit_worktree as _planning_commit_worktree,
    _resolve_planning_placement as _resolve_planning_placement,
    _stage_finalize_artifacts_in_coord_worktree as _stage_finalize_artifacts_in_coord_worktree,
)

# WP08 (coord-write-placement-closure-01KYCF83, FR-005/NFR-005, Gap-2): the
# ``agent mission repair`` command lives in its own leaf module (mirrors every
# other seam above) — no business logic here, just the app registration.
from specify_cli.cli.commands.agent.mission_repair import (
    repair as repair_mission,
)

# Preserve the dynamic ``_invalid_<dir>_owned_files`` alias as a re-export so
# patch targets keep resolving. The alias name is built from ``KITTY_SPECS_DIR``
# at runtime (``.replace("-", "_")``) rather than hardcoding a raw mission-spec
# literal in source, mirroring the canonical ``mission-specs`` validator.
globals()["_invalid_" + KITTY_SPECS_DIR.replace("-", "_") + "_owned_files"] = _invalid_mission_specs_owned_files

# Module-level re-export bindings (not ``import ... as`` so mypy treats them as
# explicit module attributes): the WP06 accept/merge seams resolve the top-level
# delegators via ``mission.top_level_accept`` / ``mission.top_level_merge`` (the
# canonical patch targets), preserving the lazy-import boundary — the seams never
# import the accept/merge graph at module scope.
top_level_accept = _accept
top_level_merge = _merge

logger = logging.getLogger(__name__)

app = typer.Typer(name="mission", help="Mission lifecycle commands for AI agents", no_args_is_help=True)

# Register the relocated commands on this module's Typer app so the CLI surface
# is unchanged (each seam defines the callable; mission.py owns the app — one-way:
# the seams never import ``app``).
app.command(name="record-analysis")(record_analysis)
app.command(name="acceptance-verdict")(acceptance_verdict)
app.command(name="branch-context")(branch_context)
app.command(name="create")(create_mission)
app.command(name="check-prerequisites")(check_prerequisites)
app.command(name="setup-plan")(setup_plan)
app.command(name="accept")(accept_feature)
app.command(name="merge")(merge_feature)
app.command(name="finalize-tasks")(finalize_tasks)
app.command(name="repair")(repair_mission)


TASKS_MD_FILENAME = "tasks.md"
SETUP_PLAN_COMMAND_NAME = "spec-kitty agent mission setup-plan"
FINALIZE_TASKS_COMMAND_NAME = "spec-kitty agent mission finalize-tasks"
INVALID_WP_OWNED_FILES_KITTY_SPECS = "INVALID_WP_OWNED_FILES_KITTY_SPECS"
PROJECT_ROOT_NOT_FOUND = "Could not locate project root"
PROJECT_ROOT_NOT_FOUND_MESSAGE = f"{PROJECT_ROOT_NOT_FOUND}. Run from within spec-kitty repository."


def _enforce_git_preflight(
    repo_root: Path,
    *,
    json_output: bool,
    command_name: str,
) -> None:
    """Run git preflight and exit with deterministic remediation payload on failure."""
    if not (repo_root / ".git").exists():
        return

    preflight = run_git_preflight(repo_root, check_worktree_list=True)
    if preflight.passed:
        return

    payload = build_git_preflight_failure_payload(preflight, command_name=command_name)
    if json_output:
        _emit_json(payload)
    else:
        console.print(f"[red]Error:[/red] {payload['error']}")
        for cmd in cast(list[str], payload.get("remediation", [])):
            console.print(f"  - Run: {cmd}")
    raise typer.Exit(1)
