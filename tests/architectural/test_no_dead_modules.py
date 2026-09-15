"""No-dead-modules architectural gate (Mission B / Process Gap 2).

The Mission B post-merge review surfaced a process gap:

    WP08 cycle 1 shipped 370 lines + 14 ATDD tests with **zero live
    callers in `src/`**. The "no live caller" anti-pattern slipped past
    both the implementer's self-check and the cycle-1 reviewer's initial
    scan.

That cycle-1 failure was structural, not human:

    src/charter/activation/mission_type_profiles.py exported MissionTypeProfile,
    resolve_governance, UnknownMissionTypeError. 14 tests called those
    symbols directly. Zero src/ files imported them. The cycle-2 fix
    wired resolve_governance into prompt_builder.py; a hard CI gate
    would have caught the missing wiring in cycle 1.

This test is that hard gate. It walks every `*.py` file under `src/`,
derives the module's dotted name (e.g. ``src/charter/activation/mission_type_profiles.py``
→ ``charter.activation.mission_type_profiles``), and verifies that **at least one
other file under `src/` imports it** -- via any of:

* ``from charter.activation.mission_type_profiles import resolve_governance``
* ``from charter import mission_type_profiles``
* ``import charter.activation.mission_type_profiles``
* ``from charter.activation.mission_type_profiles.submodule import X``
* relative-import equivalents (``from . import X``, ``from .X import Y``)

Modules with zero such callers MUST appear in ``_ALLOWLIST`` with a
documented rationale. The allowlist categories are:

1. Auto-discovered packages -- ``upgrade.migrations.m_*`` modules loaded
   by ``pkgutil.iter_modules`` glob in
   ``src/specify_cli/upgrade/migrations/__init__.py``.

2. Build-script schema generators -- ``doctrine.*.models`` and
   ``doctrine.*.schema_models`` modules consumed by
   ``scripts/generate_schemas.py`` via dotted-string
   ``importlib.import_module``.

3. External CLI entry points -- modules invoked as
   ``python -m specify_cli.<path>`` from outside the import graph
   (e.g. the git pre-commit hook installed by ``hook_installer.py``).

4. Documented backward-compatibility shims -- top-level files whose
   module docstring is ``Backward-compat shim -- canonical home is
   ...``. Their role is to keep legacy import paths green.

5. WP-in-flight slot-holder adapters -- ``compat/_adapters/*`` files
   carrying the ``# adapter:no-logic`` marker, reserved for the WP07
   compat-planner wiring.

6. Frozen-contract internal re-exports -- ``next/_internal_runtime/
   {emitter,lifecycle,models}.py`` re-export modules from the
   shared-package-boundary-cutover internalization.

7. Grandfathered orphans -- modules that *should* have a runtime
   caller but currently don't (legitimate WP08-style "library written
   but never wired" cases). Each carries a ``# TODO(triage):`` comment;
   a follow-up mission must either wire them or delete them.

The ratchet is bidirectional: if a new file under ``src/`` lands with
zero callers and is not in the allowlist, the test fails. If an
allowlisted file gains a caller (good news -- the wiring landed), the
test ALSO fails so the maintainer remembers to shrink the allowlist.

See ``work/process-gap-2-no-dead-modules.md`` for the assessment that
produced this list.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from specify_cli.ast_analysis.imports import (
    module_of_import_from as _resolve_import_from,
)


pytestmark = [pytest.mark.architectural]


_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

# Files we never count as candidates because they cannot have a meaningful
# "caller" relationship -- package init shims are imported implicitly when
# the package is referenced, and CLI entry shims are referenced via
# pyproject.toml [project.scripts] rather than via Python imports.
_SKIP_FILENAMES: frozenset[str] = frozenset({"__init__.py", "__main__.py"})

# File-name prefixes to skip -- ``_compat*`` files are intentional
# re-export shims whose absence of static callers is the point.
_SKIP_FILENAME_PREFIXES: tuple[str, ...] = ("_compat",)


# Allowlist of modules whose lack of static src/ callers is documented and
# intentional. The allowlist is split into per-category frozensets so the
# ratchet-baseline meta-test (`tests/architectural/test_ratchet_baselines.py`)
# can track Cat-7 (grandfathered orphans) separately from the auto-discovery
# categories. See Slice F FR-112 for the refactor rationale.
#
# THIS ALLOWLIST IS A RATCHET. When an entry gains a real caller, remove
# it from this set -- the test enforces shrinkage. When a new orphan
# appears, do NOT add it here as a reflex: investigate first, then
# either wire it from runtime, delete it, or add it under category 7
# with a ``# TODO(triage):`` comment and a follow-up tracker ticket.

# ---------- 1. Auto-discovered via pkgutil.iter_modules ----------
# Loaded by src/specify_cli/upgrade/migrations/__init__.py's
# auto_discover_migrations() which scans the directory for
# m_*.py files. No static import; the @MigrationRegistry.register
# decorator fires at import time. base.py is excluded from this
# list because it IS imported statically (every migration does
# `from .base import BaseMigration`).
_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS: frozenset[str] = frozenset(
    {
        "specify_cli.upgrade.migrations.m_0_10_0_python_only",
        "specify_cli.upgrade.migrations.m_0_10_12_charter_cleanup",
        "specify_cli.upgrade.migrations.m_0_10_14_update_implement_slash_command",
        "specify_cli.upgrade.migrations.m_0_10_1_populate_slash_commands",
        "specify_cli.upgrade.migrations.m_0_10_2_update_slash_commands",
        "specify_cli.upgrade.migrations.m_0_10_6_workflow_simplification",
        "specify_cli.upgrade.migrations.m_0_10_8_fix_memory_structure",
        "specify_cli.upgrade.migrations.m_0_10_9_repair_templates",
        "specify_cli.upgrade.migrations.m_0_11_1_improved_workflow_templates",
        "specify_cli.upgrade.migrations.m_0_11_1_update_implement_slash_command",
        "specify_cli.upgrade.migrations.m_0_11_2_improved_workflow_templates",
        "specify_cli.upgrade.migrations.m_0_11_3_workflow_agent_flag",
        "specify_cli.upgrade.migrations.m_0_12_0_documentation_mission",
        "specify_cli.upgrade.migrations.m_0_12_1_remove_kitty_specs_from_gitignore",
        "specify_cli.upgrade.migrations.m_0_13_0_research_csv_schema_check",
        "specify_cli.upgrade.migrations.m_0_13_0_update_charter_templates",
        "specify_cli.upgrade.migrations.m_0_13_0_update_research_implement_templates",
        "specify_cli.upgrade.migrations.m_0_13_1_exclude_worktrees",
        "specify_cli.upgrade.migrations.m_0_13_5_add_commit_workflow_to_templates",
        "specify_cli.upgrade.migrations.m_0_13_8_target_branch",
        "specify_cli.upgrade.migrations.m_0_14_0_centralized_feature_detection",
        "specify_cli.upgrade.migrations.m_0_16_2_remove_wp_status_gitignore_rule",
        "specify_cli.upgrade.migrations.m_0_2_0_specify_to_kittify",
        "specify_cli.upgrade.migrations.m_0_4_8_gitignore_agents",
        "specify_cli.upgrade.migrations.m_0_6_5_commands_rename",
        "specify_cli.upgrade.migrations.m_0_6_7_ensure_missions",
        "specify_cli.upgrade.migrations.m_0_7_2_worktree_commands_dedup",
        "specify_cli.upgrade.migrations.m_0_7_3_update_scripts",
        "specify_cli.upgrade.migrations.m_0_8_0_remove_active_mission",
        "specify_cli.upgrade.migrations.m_0_8_0_worktree_agents_symlink",
        "specify_cli.upgrade.migrations.m_0_9_0_frontmatter_only_lanes",
        "specify_cli.upgrade.migrations.m_0_9_2_research_mission_templates",
        "specify_cli.upgrade.migrations.m_0_9_3_surface_repair_wiring",  # WP01: auto-discovered sentinel migration
        "specify_cli.upgrade.migrations.m_0_9_4_roo_deprecation",  # WP07: Roo Code deprecation; auto-discovered, never statically imported
        "specify_cli.upgrade.migrations.m_2_0_0_charter_directory",
        "specify_cli.upgrade.migrations.m_2_0_0_historical_status_migration",
        "specify_cli.upgrade.migrations.m_2_0_0_retire_git_hooks",
        "specify_cli.upgrade.migrations.m_2_0_11_install_skills",
        "specify_cli.upgrade.migrations.m_2_0_11_remove_clarify_command",
        "specify_cli.upgrade.migrations.m_2_0_1_fix_generated_command_templates",
        "specify_cli.upgrade.migrations.m_2_0_1_tool_config_key_rename",
        "specify_cli.upgrade.migrations.m_2_0_2_charter_context_bootstrap",
        "specify_cli.upgrade.migrations.m_2_0_6_consistency_sweep",
        "specify_cli.upgrade.migrations.m_2_0_7_fix_stale_overrides",
        "specify_cli.upgrade.migrations.m_2_0_9_state_gitignore",
        "specify_cli.upgrade.migrations.m_2_1_1_repair_skill_pack",
        "specify_cli.upgrade.migrations.m_2_1_2_fix_charter_doctrine_skill",
        "specify_cli.upgrade.migrations.m_2_1_2_fix_glossary_context_skill",
        "specify_cli.upgrade.migrations.m_2_1_2_fix_orchestrator_api_skill",
        "specify_cli.upgrade.migrations.m_2_1_2_fix_runtime_next_skill",
        "specify_cli.upgrade.migrations.m_2_1_2_install_git_workflow_skill",
        "specify_cli.upgrade.migrations.m_2_1_2_install_mission_system_skill",
        "specify_cli.upgrade.migrations.m_2_1_2_remove_release_skill",
        "specify_cli.upgrade.migrations.m_2_1_3_fix_planning_repository_terminology",
        "specify_cli.upgrade.migrations.m_2_1_4_enforce_command_file_state",
        "specify_cli.upgrade.migrations.m_2_2_0_profile_context_deployment",
        "specify_cli.upgrade.migrations.m_3_0_0_canonical_context",
        "specify_cli.upgrade.migrations.m_3_0_2_restore_prompt_commands",
        "specify_cli.upgrade.migrations.m_3_0_3_globalize_skill_pack",
        "specify_cli.upgrade.migrations.m_3_1_1_charter_rename",
        "specify_cli.upgrade.migrations.m_3_1_1_direct_canonical_commands",
        "specify_cli.upgrade.migrations.m_3_1_1_event_log_merge_driver",
        "specify_cli.upgrade.migrations.m_3_1_1_normalize_status_json",
        "specify_cli.upgrade.migrations.m_3_2_0rc35_codex_to_skills",
        "specify_cli.upgrade.migrations.m_3_2_0rc35_update_planning_templates",
        "specify_cli.upgrade.migrations.m_3_2_0a4_normalize_mission_lifecycle",
        "specify_cli.upgrade.migrations.m_3_2_0a4_safe_globalize_commands",
        "specify_cli.upgrade.migrations.m_3_2_0rc35_strip_selection_config",
        "specify_cli.upgrade.migrations.m_3_2_0rc35_unified_bundle",
        "specify_cli.upgrade.migrations.m_3_2_0rc35_kittify_profile_handoff",
        "specify_cli.upgrade.migrations.m_3_2_0rc35_repository_root_checkout_terminology",
        "specify_cli.upgrade.migrations.m_3_2_0rc35_fix_prompt_file_workaround",
        "specify_cli.upgrade.migrations.m_3_2_0rc35_charter_bundle_v2",
        "specify_cli.upgrade.migrations.m_3_2_0rc35_charter_manifest_defaults_repair",
        "specify_cli.upgrade.migrations.m_unify_charter_activation_finalize",
        "specify_cli.upgrade.migrations.m_3_2_0rc43_retire_profile_context_command",
        # doctrine-drg-silent-drop-boundary (#3629): consumer-project migration
        # that consolidates context-sources.* onto the *-references fields;
        # auto-discovered, never statically imported.
        "specify_cli.upgrade.migrations.m_3_3_1_context_sources_consolidation",
        # NOTE: WP01 (charter-pack-activation-layer-01KSYE4V) was expected to
        # add the three entries below.  They are added here as a WP01 gap fix
        # so the WP05 architectural gate passes before lanes are merged.
        "specify_cli.upgrade.migrations.m_3_2_0rc28_github_diff_attributes",
        "specify_cli.upgrade.migrations.m_3_2_0rc30_fix_runtime_next_result_default",
        "specify_cli.upgrade.migrations.m_3_2_0rc35_activate_builtin_mission_types",
        # WP05 (charter-pack-activation-layer-01KSYE4V) migration added here.
        "specify_cli.upgrade.migrations.m_3_2_0rc35_default_charter_pack",
        # NOTE: m_3_2_0rc35_sync_state_gitignore was removed from this allowlist
        # (2026-07-04 campsite) — it is now statically imported by
        # m_3_2_3_encoding_provenance_gitignore_backfill (below), so it has a
        # real src/ caller and is no longer an orphan.
        # pi-and-letta-agent-support-01KT4Q26 WP01: backfill migration for
        # .pi/ and .letta/ gitignore entries and skill-pack repair.
        # Auto-discovered via pkgutil.iter_modules; never statically imported.
        "specify_cli.upgrade.migrations.m_3_2_0rc35_pi_letta_backfill",
        # 3.2.0rc35 skill-pack migration: auto-discovered via
        # pkgutil.iter_modules; never statically imported by design.
        "specify_cli.upgrade.migrations.m_3_2_0rc35_spk_skill_pack",
        # 3.3.0 session-presence migrations: auto-discovered via
        # pkgutil.iter_modules in migrations/__init__.py; never statically
        # imported by runtime code — the @MigrationRegistry.register
        # decorator fires at import time.  These two modules landed on
        # upstream/main (#1756) before this mission; the core-misc path
        # filter was not triggered there, so the allowlist gap went
        # undetected until this mission's status/ changes triggered the
        # core-misc suite. Pre-existing upstream debt, not a mission regression.
        "specify_cli.upgrade.migrations.m_3_3_0_session_presence_all_harnesses",
        "specify_cli.upgrade.migrations.m_3_3_0_session_presence_claude_code",
        # 3.2.0rc39 orientation-block refresh migration: auto-discovered via
        # pkgutil.iter_modules; never statically imported by runtime code.
        "specify_cli.upgrade.migrations.m_3_2_0rc39_refresh_orientation_block",
        # do-dispatch-open-op-lifecycle-01KTSJ2H WP05 (FR-011): Op record
        # schema v2 migration. Auto-discovered via pkgutil.iter_modules in
        # migrations/__init__.py and registered through
        # @MigrationRegistry.register at import time; never statically
        # imported by runtime code. Test-exercised by
        # tests/upgrade/test_op_record_schema_v2_migration.py.
        "specify_cli.upgrade.migrations.m_3_3_0_op_record_schema_v2",
        # 3.2.0rc45 standalone governance skill retirement migration:
        # auto-discovered via pkgutil.iter_modules in migrations/__init__.py.
        "specify_cli.upgrade.migrations.m_3_2_0rc45_retire_standalone_skill_surface",
        # 3.2.3 encoding-provenance/gitignore backfill migration: auto-discovered
        # via pkgutil.iter_modules + @MigrationRegistry.register; never statically
        # imported by runtime code. (It statically imports
        # m_3_2_0rc35_sync_state_gitignore, which is why that module is no longer
        # an orphan and was removed from this allowlist.)
        "specify_cli.upgrade.migrations.m_3_2_3_encoding_provenance_gitignore_backfill",
        # 3.2.4 derived-mission-views gitignore backfill migration (#2370):
        # auto-discovered via pkgutil.iter_modules + @MigrationRegistry.register;
        # never statically imported by runtime code. Landed in #2370 without its
        # allowlist entry (the core-misc path filter was not triggered there);
        # the gap surfaced here. Same sibling shape as the m_3_2_3 backfill above.
        "specify_cli.upgrade.migrations.m_3_2_4_derived_views_gitignore_backfill",
        # 3.2.4 runtime-dirs (.kittify/migrations/ + .kittify/logs/) gitignore
        # backfill migration (#2384): auto-discovered via pkgutil.iter_modules +
        # @MigrationRegistry.register; never statically imported by runtime code.
        # Same sibling shape as the m_3_2_3/m_3_2_4 backfills above.
        "specify_cli.upgrade.migrations.m_3_2_4_runtime_dirs_gitignore_backfill",
        # 3.2.5 .agents/skills/ + skills-manifest gitignore backfill migration
        # (#2412): auto-discovered via pkgutil.iter_modules +
        # @MigrationRegistry.register; never statically imported by runtime
        # code. Same sibling shape as the two backfills above.
        "specify_cli.upgrade.migrations.m_3_2_5_agents_skills_gitignore_backfill",
        # 3.2.6rc3 .worktrees/ gitignore backfill migration (#3689):
        # auto-discovered via pkgutil.iter_modules + @MigrationRegistry.register;
        # never statically imported by runtime code. Same sibling shape as the
        # gitignore backfills above.
        "specify_cli.upgrade.migrations.m_3_2_6rc3_worktrees_gitignore_backfill",
        # 3.2.6rc3 blanket-.cursor/ gitignore narrowing migration (#2498):
        # auto-discovered via pkgutil.iter_modules + @MigrationRegistry.register;
        # never statically imported by runtime code. Same sibling shape as the
        # gitignore backfills above.
        "specify_cli.upgrade.migrations.m_3_2_6rc3_narrow_cursor_gitignore",
        # 3.2.6rc3 .kittify/lint-report.json gitignore backfill migration
        # (#3435): auto-discovered via pkgutil.iter_modules +
        # @MigrationRegistry.register; never statically imported by runtime
        # code. Same sibling shape as the gitignore backfills above.
        "specify_cli.upgrade.migrations.m_3_2_6rc3_lint_report_gitignore_backfill",
        "specify_cli.upgrade.migrations.m_3_2_6_gate_artifact_merge_drivers",  # auto-discovered (#2804)
        "specify_cli.upgrade.migrations.m_3_2_6_meta_traces_merge_drivers",  # auto-discovered (#2709)
        "specify_cli.upgrade.migrations.m_3_2_6_decisions_event_log_merge_driver",  # auto-discovered (#2709)
        "specify_cli.upgrade.migrations.m_3_2_6_retire_rtk_search_tooling",  # auto-discovered (#3009)
        # auto-discovered (write-side-seam-matrix-tracer-01KYP3MH WP05/FR-008);
        # repoints the #2804 gate-artifact merge driver from issue-matrix.md
        # to issue-matrix.json
        "specify_cli.upgrade.migrations.m_3_2_6_issue_matrix_driver_repoint",
        # doctrine-delivery-reachability-01KYMXD6 WP07/T037 (FR-018): normalizes
        # absent activated_<kind> keys to explicit [] in the resolved activation
        # store. Auto-discovered via pkgutil.iter_modules + @MigrationRegistry
        # .register (decorator on NormalizeActivationAbsenceMigration); never
        # statically imported by runtime code -- same sibling shape as the
        # m_3_2_6_* migrations above.
        "specify_cli.upgrade.migrations.m_3_2_x_normalize_activation_absence",
        # runtime-state-corpus-cutover-01KXZ0AX WP02 (FR-010, #2816): auto-discovered
        # corpus cutover migration for existing deployments. Auto-discovered via
        # pkgutil.iter_modules + @MigrationRegistry.register; never statically
        # imported by runtime code. Named m_zz_* (not a numeric-prefix name) so it
        # sorts alphabetically AFTER the m_unify_charter_activation* folds at the
        # same tied target_version="3.2.6rc1" (see the module docstring).
        "specify_cli.upgrade.migrations.m_zz_runtime_state_backfill",
        # verdict-seam-write-unification-01KZ9Q35 pre-merge remediation (#3236,
        # FR-012/SC-008): auto-discovered upgrade migration that backfills each
        # kitty-specs/ mission's stranded terminal review-cycle .md verdict into
        # status.events.jsonl. Auto-discovered via pkgutil.iter_modules +
        # @MigrationRegistry.register; never statically imported by runtime code.
        # Named m_zz_* (same ordering rationale as the runtime-state sibling
        # above) at the tied target_version="3.2.6rc1".
        "specify_cli.upgrade.migrations.m_zz_verdict_provenance_backfill",
        # review-cycle-verdict-seam-rebuild-01KZ2W7W WP18/T079 (T017): installs
        # the review-cycle-*.md fail-closed merge driver for already-init'd
        # clones. Auto-discovered via pkgutil.iter_modules + @MigrationRegistry
        # .register; never statically imported by runtime code -- same sibling
        # shape as the m_3_2_6_* merge-driver migrations above. Cross-WP,
        # unowned-gate edit (WP18 does not own this test file); disclosed in
        # the WP18 implementation report.
        "specify_cli.upgrade.migrations.m_3_2_7_review_cycle_merge_driver",
        # WIRE-M2-03 (2026-08-22): wires the F2-T1 one-shot F1-strict
        # lifecycle-envelope rewrite into `spec-kitty upgrade`, over the
        # project-level and every mission-level event log. Auto-discovered
        # via pkgutil.iter_modules + @MigrationRegistry.register; never
        # statically imported by runtime code -- same sibling shape as the
        # m_zz_* backfill migrations above. (This is also why
        # `specify_cli.status.migrate_lifecycle_envelope` was removed from
        # Category 7 above -- it now has a real src/ caller: this module.)
        "specify_cli.upgrade.migrations.m_3_2_9_migrate_lifecycle_envelope",
        # #4259: machine-scoped, idempotent rewrite of a stale
        # config.toml [sync].server_url naming the retired first-party
        # app endpoint to the canonical hosted target. Auto-discovered
        # via pkgutil.iter_modules + @MigrationRegistry.register; never
        # statically imported by runtime code -- same sibling shape as
        # the m_zz_* backfill migrations above.
        "specify_cli.upgrade.migrations.m_4_0_0_retired_hosted_target",
    }
)

# ---------- 2. Build-script schema generators ----------
# Loaded by scripts/generate_schemas.py via dotted-string
# importlib.import_module to derive JSON schemas from Pydantic
# models. Never imported by runtime code.
#
# Also carries constant modules wired from scripts/ rather than src/ —
# same "consumed from scripts/, not src/" pattern as the schema generators
# above (scripts/generate_schemas.py).
_CATEGORY_2_BUILD_SCHEMA_GENERATORS: frozenset[str] = frozenset(
    {
        "charter.offering.agent_profiles.schema_models",
        "charter.offering.import_candidates.models",
        # charter.offering.model_task_routing.models removed (model-discipline-dispatch-binding-01KWPW36
        # WP03): ProfileInvocationExecutor.invoke() now wires loader.py/evaluator.py into the
        # dispatch seam, and both import this module -- it has a live src/ caller as of WP03's
        # _compute_recommendation() wiring, so it no longer belongs in this build-script-only
        # allowlist.
    }
)

# ---------- 3. External CLI / hook entry points ----------
_CATEGORY_3_EXTERNAL_CLI_ENTRYPOINTS: frozenset[str] = frozenset(
    {
        # specify_cli.policy.commit_guard_hook removed (#254): the pre-commit
        # hook's PATH fallback now reaches it through a real src/ caller,
        # commit_guard_hook_cmd.commit_guard_hook_cli(), so it is no longer
        # genuinely dead -- it no longer belongs in this build-script-only
        # allowlist.
    }
)

# ---------- 4. Documented backward-compat shims ----------
# Re-export modules whose docstring starts with
# ``Backward-compat shim -- canonical home is ...``. Tests pin
# the re-export contract; the lack of src/ callers is the point.
#
# Fully drained by unshim-wave1 WP02 (#2289): ``specify_cli.tasks_support``
# was the last documented back-compat shim; its ~35 test sites were re-anchored
# onto ``specify_cli.task_utils`` and the module deleted, so this category is now
# empty (baseline category_4_backcompat_shims: 0).
#
# 0 -> 1 (charter-code-topology-01M152G1 landing remediation, retire-doctrine-term
# M2): ``doctrine`` (src/doctrine.py) is an intentional deprecation shim -- a single
# MODULE file (not a package) kept only so pre-existing external/legacy callers that
# still spell ``import doctrine`` / ``from doctrine import X`` keep working during the
# CR-06 deprecation window, after the relocation of src/doctrine/ to
# src/charter/offering/. Nothing under src/ imports it (that is the point of a
# backcompat shim for EXTERNAL callers); it has zero src/ callers by design.
_CATEGORY_4_BACKCOMPAT_SHIMS: frozenset[str] = frozenset(
    {
        "doctrine",
    }
)

# ---------- 5. WP-in-flight slot-holder adapters ----------
# Carry the `# adapter:no-logic` marker; reserved for the WP07
# compat-planner wiring. Removing them now would break
# tests/architectural/test_compat_shims.py's slot-presence
# assertion. See src/specify_cli/compat/__init__.py for the
# compat-shim mission context.
#
# charter.activation.scope_router removed (post-merge remediation cycle 1, 2026-05-19):
# prompt_builder.py now imports build_with_scope from charter.activation.scope_router,
# giving scope_router a live src/ caller. The WP09→WP11 wiring trigger has
# been reached; the allowlist entry is removed. See HIGH-1 in
# mission-review-report.md.
_CATEGORY_5_WP_IN_FLIGHT_ADAPTERS: frozenset[str] = frozenset(
    {
        # compat._adapters.{detector,gate,version_checker} removed: dead pure-shim
        # files deleted (zero functional callers; salvaged from closed #2159/#2049).
        # runtime.next._internal_runtime.workflow_registry removed:
        # WP11 wired get_workflow() into planner.py (planner imports it
        # via workflow_registry at module scope), so the module now has a
        # live src/ caller.  WP11 removal trigger reached.
        # charter.activation.scope_router removed: post-merge remediation cycle 1
        # wired prompt_builder._governance_context through build_with_scope.
        #
        # charter.offering.missions.mission_step_repository: live caller landed in
        # charter.mission_steps (charter-pack-activation-layer-01KSYE4V WP09)
        #
        # charter.extractor removed: the prose->triad scraper (SECTION_MAPPING,
        # write_extraction_result, extract_with_ai, and the retirement husk
        # left behind, Extractor/_detect_catalog_references) is fully deleted
        # by charter-deadcode-noop-campsite WP02 -- module removed, test-only
        # references retired/reconstructed. Category fully drained (1->0).
        #
        # pack-metadata-manifest-unification (#3500-#3503 / ADR 2026-08-16-1,
        # 2026-08-16): this is a deliberately library-first schema slice. The
        # unified-schema *models* land here; their production wiring (org/fetched
        # writers, the pack_id-keyed resolver cutover, the lineage/accompanies
        # production callers) is the deferred integration WP, tracked in #3518.
        # These two modules are the not-yet-wired adapters awaiting that WP; the
        # AST ratchet test_pack_lineage_no_parallel_resolver.py + the schema/
        # identity/counts unit suites exercise them meanwhile.
        "specify_cli.doctrine.pack_descriptor",
        "specify_cli.doctrine.pack_lineage",
    }
)

# ---------- 6. Frozen-contract internal re-exports ----------
# Internalized from spec-kitty-runtime under
# shared-package-boundary-cutover-01KQ22DS. The CLI imports
# the implementation files (engine.py, events.py); these three
# exist as the per-task-layout public surface frozen in
# kitty-specs/.../contracts/internal_runtime_surface.md.
_CATEGORY_6_FROZEN_RUNTIME_REEXPORTS: frozenset[str] = frozenset(
    {
        "runtime.next._internal_runtime.emitter",
        "runtime.next._internal_runtime.lifecycle",
        "runtime.next._internal_runtime.models",
    }
)

# ---------- 7. Grandfathered orphans (HiC triage queue) ----------
# Modules that look like genuine "library written but never
# wired" cases. Tests exercise them, but no runtime caller does.
# Each MUST eventually be wired, deleted, or formally adopted
# into one of the categories above. Do not add new entries to
# this category without filing a follow-up tracker ticket.
#
# Per Slice F C-006 (binding), Cat-7 MUST shrink by >= 2 entries
# per major release; target = 0 by 4.0. WP01 of Slice F shrinks
# this list from 10 -> 7 by deleting three modules outright
# (charter.offering.templates.repository, glossary.prompts,
# glossary.rendering) per DM-01KRX6N0YAFBY7MTJC0CN3D3E4.
#
# issue-116-wire-or-prune-orphaned-collateral (2026-08-27): shrinks this list
# 5 -> 2 by deleting the three sync-transport collateral orphans
# (core.batch_partition, dossier.drift_detector, migration.envelope_seam)
# outright -- none had a viable low-risk wiring target after the sync
# transport's removal (issue #5). See the inline note below for detail.
_CATEGORY_7_GRANDFATHERED_ORPHANS: frozenset[str] = frozenset(
    {
        # unshim-wave1-01KWKVHB (#2292) drained this set 6 -> 2 by deleting
        # task_profile, sync.replay, sync.tracker_client_glue and
        # retrospective.lifecycle outright (WP01 T005 executed + WP03 T008).
        # The two survivors carry documented deferral verdicts:
        # - auth.transport: DELETE approved by ADR
        #   docs/adr/3.x/2026-05-18-2-delete-specify-cli-auth-transport.md,
        #   execution deferred to Robert (HiC C-001 no-touch boundary).
        "specify_cli.auth.transport",
        # - policy.audit: KEEP -> adopt-as-follow-up. Real designed
        #   governance-evidence seam (append-only policy-audit.jsonl);
        #   wiring is design work tracked in a follow-up issue, not deleted.
        "specify_cli.policy.audit",
        # charter-activation-split (#806) restored EXPERIMENTAL replay
        # semantics, leaving these activation-adjacent seams without static
        # src/ callers. TODO(triage): #925 owns wire-or-prune disposition.
        "charter.parser",
        "charter.activation.template_resolver",
        # sync.admission_operations: REMOVED (issue-5-delete-sync-transport,
        # 2026-08-25). The module was deleted outright with the sync transport;
        # its #3262 WP11 wiring consumer no longer exists, so there is nothing
        # left to triage.
        #
        # ---- issue-5-delete-sync-transport collateral, adjudicated (issue #116,
        # 2026-08-27): three modules whose ONLY src/ caller was the deleted sync
        # transport (cli/commands/sync.py + the sync/delivery packages) were
        # registered here pending wire-or-prune triage. Each was investigated for
        # a viable low-risk wiring target and found to have none -- their sole
        # reason to exist died with the sync transport (issue #5) -- so all three
        # were PRUNED (deleted outright) rather than wired or kept allowlisted:
        # - core.batch_partition: batch-400 poison-isolation bisection (#2755);
        #   its sole caller was the deleted sync push fan-out. Deleted.
        # - dossier.drift_detector: dossier drift detection; its sole caller was
        #   the deleted dossier push trigger chain (dossier/snapshot.py's own
        #   save path lost its trigger in the same deletion). Deleted.
        # - migration.envelope_seam: the deliberate migration<->import envelope
        #   re-export surface (#2262); its sole callers were the deleted
        #   delivery.targets and the deleted sync status-report writer.
        #   mission_state.py's own envelope assembly is prose-referenced only.
        #   Deleted.
        # migration.verdict_provenance_backfill: REMOVED (verdict-seam-write-
        #   unification-01KZ9Q35 pre-merge remediation, 2026-08-06 -- predates and is
        #   unrelated to the M2 canonical-integration entries below). The eventual-wiring
        #   follow-up (#3236) landed: the FR-012/SC-008 backfill is now called from `src/`
        #   by the auto-discovered upgrade migration
        #   `upgrade.migrations.m_zz_verdict_provenance_backfill` (and its
        #   `stranded_verdict_findings` predicate by the `accept` provenance diagnostic),
        #   so the module has live `src/` callers and is no longer an orphan. Shrink
        #   3 -> 2 -- reverses the post-merge green-up bump.
        #
        # ---- M2 canonical integration (2026-08-22): reviewed M1 candidates that
        # landed a module with no src/ runtime caller; each candidate's own
        # sandbox ran targeted suites and never this gate. Registered here so the
        # fact is visible, not hidden (M2-CANONICAL-INTEGRATION.json lists them).
        # All four were wired and removed in turn by WIRE-M2-01..04 (2026-08-22,
        # LOCAL-RC train lrc-w1; see tests/architectural/_baselines.yaml's
        # category_7_grandfathered_orphans for the full 7 -> 3 shrink sequence):
        # tracker.gateway: REMOVED (WIRE-M2-01). Wired into
        #   LocalTrackerService._build_engine (local_service.py) -- Beads
        #   mutations now build their connector via
        #   gateway.build_gateway_beads_connector instead of the ungated
        #   factory.build_connector, so the module has a live src/ caller and
        #   is no longer an orphan. Shrink 7 -> 6.
        # D2-T1 dashboard.csp: REMOVED (WIRE-M2-02). send_csp_header()
        #   is now called from all 35 send_response() sites across
        #   handlers/{base,api,features,glossary,lint,static}.py, so the module has
        #   live src/ callers and is no longer an orphan. Shrink 6 -> 5.
        # status.migrate_lifecycle_envelope: REMOVED (WIRE-M2-03). The F2-T1
        #   one-shot F1-strict envelope rewrite is now called from `src/` by the
        #   auto-discovered upgrade migration
        #   `upgrade.migrations.m_3_2_9_migrate_lifecycle_envelope`, so the module
        #   has a live `src/` caller and is no longer an orphan. Shrink 5 -> 4.
        # zeitgeist_client.grammar: REMOVED (WIRE-M2-04, HIC-M2-DISPOSITIONS-
        #   2026-08-22 item 2). live_frame.py now imports grammar (`from . import
        #   grammar`) and routes every identity field it parses (session_ref,
        #   actor.user, repo, branch, focus_ref) through grammar.ident()/
        #   grammar.ident(..., REF_RE) before it reaches a PresenceView/FocusView
        #   or an internal dict key -- mirrors zeitgeist/editor.py's own
        #   rendering-time identity sanitization. Real src/ caller landed; no
        #   longer an orphan. Shrink 4 -> 3.
        # All four M2-canonical-integration entries are closed; none remain open.
        #
        # E3 #9 credential resolution (2026-08-25): zeitgeist_client.resolution
        # was registered here as the seam library awaiting the #8 zeitgeist
        # handler as its caller. BURNED (E3 #8, 2026-08-25):
        # status/zeitgeist_bridge.py resolves credentials at the fan-out seam,
        # so the module has a live src/ caller and is no longer an orphan.
        # Shrink 4 -> 3 (baseline updated in _baselines.yaml).
    }
)

# ---------- 8. Dispatched governed Ops (zero src/ coupling by design) ----------
# ``acceptance.post_consolidation`` (mission lifecycle-gate-execution-context,
# WP06/T031, FR-303 dead-symbol/module case, no new tracker ticket) is a plain
# library module whose entry point (``verify_deferred_invariants``) is run as
# an ordinary governed Op dispatched ad hoc via ``spec-kitty dispatch`` --
# never imported from another ``src/`` module. This is a load-bearing design
# constraint, not an oversight: the module docstring states "there is no new
# CLI verb and no call-in from merge/executor.py" (zero `merge/` coupling,
# contract C7), and the sibling CI enforcer
# (``scripts/ci/check_dangling_deferrals.py``) is deliberately "zero-coupled
# to src/specify_cli" (its own docstring) -- it duplicates the on-disk wire
# value instead of importing this module. The real, documented caller is the
# operator/agent following docs/guides/accept-and-merge.md
# #deferred-invariants-and-the-post-consolidation-gate, not a static import.
_CATEGORY_8_DISPATCHED_GOVERNED_OPS: frozenset[str] = frozenset(
    {
        "specify_cli.acceptance.post_consolidation",
    }
)


# ---------- 9. Auto-discovered doctor siblings ----------
# Loaded by src/specify_cli/cli/commands/doctor.py's
# `_auto_discover_doctor_siblings()`, which scans the package for
# `_*_doctor.py` modules and calls each module's `register(app)` via
# pkgutil.iter_modules + importlib.import_module -- the same dynamic
# auto-discovery seam as category 1's migrations, so there is no static
# importer. Introduced by mission operator-config-ergonomics (#3506). The
# eventual root fix is a structural auto-exempt for this seam (mirroring the
# migration handling), tracked in #3508; until then the three siblings are
# enumerated here.
_CATEGORY_9_AUTO_DISCOVERED_DOCTOR_SIBLINGS: frozenset[str] = frozenset(
    {
        "specify_cli.cli.commands._bytecode_doctor",
        "specify_cli.cli.commands._channel_doctor",
        "specify_cli.cli.commands._env_file_doctor",
        "specify_cli.cli.commands._provenance_doctor",
    }
)


# Aggregate of every per-category set. The existing
# `test_no_new_dead_modules_under_src` check below treats this as the
# effective allowlist; the per-category frozensets above are the surface
# inspected by the ratchet-baseline meta-test
# (tests/architectural/test_ratchet_baselines.py).
_ALLOWLIST: frozenset[str] = (
    _CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS
    | _CATEGORY_2_BUILD_SCHEMA_GENERATORS
    | _CATEGORY_3_EXTERNAL_CLI_ENTRYPOINTS
    | _CATEGORY_4_BACKCOMPAT_SHIMS
    | _CATEGORY_5_WP_IN_FLIGHT_ADAPTERS
    | _CATEGORY_6_FROZEN_RUNTIME_REEXPORTS
    | _CATEGORY_7_GRANDFATHERED_ORPHANS
    | _CATEGORY_8_DISPATCHED_GOVERNED_OPS
    | _CATEGORY_9_AUTO_DISCOVERED_DOCTOR_SIBLINGS
)


def _is_candidate(path: Path) -> bool:
    """True iff *path* is a python module we want to gate on."""
    if "__pycache__" in path.parts:
        return False
    name = path.name
    if name in _SKIP_FILENAMES:
        return False
    return not any(name.startswith(prefix) for prefix in _SKIP_FILENAME_PREFIXES)


def _module_dotted(path: Path) -> str:
    """Return the dotted module name for *path* relative to ``src/``.

    Example: ``src/charter/activation/mission_type_profiles.py`` →
    ``charter.activation.mission_type_profiles``.
    """
    rel = path.relative_to(_SRC_ROOT).with_suffix("")
    return ".".join(rel.parts)


def _package_of(path: Path) -> str:
    """Return the dotted package containing *path* (for relative imports).

    For ``src/cli/commands/foo.py`` returns ``cli.commands``. For
    ``src/cli/commands/__init__.py`` also returns ``cli.commands`` (the
    init file's "containing package" is itself).
    """
    rel = path.relative_to(_SRC_ROOT).with_suffix("")
    parts = list(rel.parts)
    # Drop the final segment (either the module name or "__init__"); both
    # cases resolve relative imports against the same parent.
    return ".".join(parts[:-1])


def _collect_import_targets(
    tree: ast.Module,
    containing_pkg: str,
) -> list[tuple[str, str, tuple[str, ...] | None]]:
    """Walk *tree* and yield ``(kind, resolved_module, imported_names)``.

    ``kind`` is ``"from"`` for ``ImportFrom`` and ``"import"`` for ``Import``.
    ``imported_names`` is a tuple of names for ``from X import a, b`` and
    ``None`` for plain ``import X``.

    We walk the FULL tree (including nested / function-level imports) so
    that lazy import patterns -- common in this codebase for keeping CLI
    startup fast -- still count as callers.
    """
    out: list[tuple[str, str, tuple[str, ...] | None]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            resolved = _resolve_import_from(node, containing_pkg)
            names = tuple(alias.name for alias in node.names)
            out.append(("from", resolved, names))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                out.append(("import", alias.name, None))
    return out


def _is_asset_blob(path: Path) -> bool:
    """True if *path* is a shipped doctrine ``asset`` blob, not a module.

    An ``ArtifactKind.ASSET`` blob is packaged data/logic shipped with a
    doctrine pack and loaded by file path (never imported), identified by a
    sibling ``<name>.asset.yaml`` sidecar manifest. The dead-code gates must
    not treat such a blob as an un-wired internal module.
    """
    return (path.parent / f"{path.name}.asset.yaml").is_file()


def _iter_src_python_files() -> list[Path]:
    """Yield every importable ``*.py`` under ``src/`` (sorted, deterministic).

    Excludes doctrine ``asset`` blobs (shipped, loaded by path — see
    :func:`_is_asset_blob`).
    """
    return sorted(p for p in _SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts and not _is_asset_blob(p))


def _has_caller(
    target_path: Path,
    target_dotted: str,
    file_imports: list[tuple[Path, list[tuple[str, str, tuple[str, ...] | None]]]],
) -> bool:
    """Return True iff any OTHER file in *file_imports* imports *target_dotted*.

    A "caller" is any of:

    * ``from <target_dotted> import X`` (with any X)
    * ``from <parent> import <leaf>`` where parent.leaf == target_dotted
    * ``from <target_dotted>.<sub> import X`` (sub-module import)
    * ``import <target_dotted>`` / ``import <target_dotted>.<sub>``

    Relative imports inside the importer's tree have already been
    resolved to absolute form by ``_resolve_import_from``.
    """
    parts = target_dotted.split(".")
    parent = ".".join(parts[:-1])
    leaf = parts[-1]
    dotted_prefix = target_dotted + "."

    for caller_path, imports in file_imports:
        if caller_path == target_path:
            continue
        for kind, mod, names in imports:
            if kind == "from":
                if mod == target_dotted:
                    return True
                if mod == parent and names is not None and leaf in names:
                    return True
                if mod.startswith(dotted_prefix):
                    return True
            else:  # plain ``import X``
                if mod == target_dotted or mod.startswith(dotted_prefix):
                    return True
    return False


def _format_failure(
    *,
    new_orphans: list[str],
    stale_allowlist_entries: list[str],
) -> str:
    parts: list[str] = []
    if new_orphans:
        bullets = "\n  - ".join(sorted(new_orphans))
        parts.append(
            "No-dead-modules gate FAILED. The following src/ modules have\n"
            "ZERO non-test callers (no other src/ file imports them):\n"
            f"  - {bullets}\n"
            "\n"
            "This is the 'library written but never wired' anti-pattern\n"
            "(Mission B post-merge review, Process Gap 2). Fix options:\n"
            "\n"
            "  1) Wire the module from a runtime caller (best -- the code\n"
            "     ships AND is exercised in production paths).\n"
            "  2) Delete the module if it's not needed (preferred over\n"
            "     allowlisting if the module has no real consumer).\n"
            "  3) Add the module to `_ALLOWLIST` in this file under the\n"
            "     correct category, with a one-line rationale. Use\n"
            "     category 7 (`# TODO(triage):`) for genuinely orphaned\n"
            "     modules that need follow-up.\n"
            "\n"
            "See tests/architectural/test_no_dead_modules.py for the\n"
            "category guide and the WP08 cycle-1 case study that\n"
            "motivated this gate."
        )
    if stale_allowlist_entries:
        bullets = "\n  - ".join(sorted(stale_allowlist_entries))
        parts.append(
            "Stale `_ALLOWLIST` entries detected. The following modules\n"
            "are listed in the allowlist but now have at least one real\n"
            "src/ caller (good news -- the wiring landed):\n"
            f"  - {bullets}\n"
            "\n"
            "Fix: remove these entries from `_ALLOWLIST` in\n"
            "tests/architectural/test_no_dead_modules.py so the ratchet\n"
            "correctly reflects the smaller orphan surface."
        )
    return "\n\n".join(parts)


def test_no_new_dead_modules_under_src() -> None:
    """Pin the no-dead-modules invariant as a one-way ratchet.

    Every ``*.py`` file under ``src/`` (excluding ``__init__.py``,
    ``__main__.py``, and ``_compat*`` shims) must have at least one
    non-test caller in ``src/``, or appear in ``_ALLOWLIST`` with a
    documented rationale.

    The test fails on BOTH directions:

    * a new orphan appears (new module without a caller and not in the
      allowlist) -- this catches the WP08-style failure;
    * an allowlist entry gains a caller (the wiring landed but the
      entry was not removed) -- this keeps the ratchet honest.
    """
    candidate_files = [p for p in _iter_src_python_files() if _is_candidate(p)]

    # Build the import index over ALL src files (including __init__/__main__,
    # since they perform package-level imports that legitimately wire
    # submodules) but excluding files we can't parse.
    file_imports: list[tuple[Path, list[tuple[str, str, tuple[str, ...] | None]]]] = []
    for path in _iter_src_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, OSError):
            # A parse failure is a different defect; skip rather than
            # mask the no-dead-modules signal.
            continue
        containing_pkg = _package_of(path)
        file_imports.append((path, _collect_import_targets(tree, containing_pkg)))

    actual_orphans: set[str] = set()
    for path in candidate_files:
        dotted = _module_dotted(path)
        if not _has_caller(path, dotted, file_imports):
            actual_orphans.add(dotted)

    new_orphans = sorted(actual_orphans - _ALLOWLIST)
    stale_allowlist_entries = sorted(_ALLOWLIST - actual_orphans)

    assert not new_orphans and not stale_allowlist_entries, _format_failure(
        new_orphans=new_orphans,
        stale_allowlist_entries=stale_allowlist_entries,
    )
