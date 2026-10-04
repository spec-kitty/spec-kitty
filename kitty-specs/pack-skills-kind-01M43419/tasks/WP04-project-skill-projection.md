---
work_package_id: WP04
title: Catalog seam and project-root projection through the managed installer
dependencies:
- WP03
requirement_refs:
- FR-009
- FR-010
- FR-011
- FR-013
- SC-001
- SC-003
- SC-007
- SC-010
- NFR-002
- NFR-004
planning_base_branch: claude/festive-babbage-lhkqac
merge_target_branch: claude/festive-babbage-lhkqac
branch_strategy: Planning artifacts for this mission were generated on claude/festive-babbage-lhkqac.
  During /spec-kitty.implement this WP may branch from a dependency-specific base,
  but completed changes must merge back into claude/festive-babbage-lhkqac unless
  the human explicitly redirects the landing branch.
subtasks:
- T015
- T016
- T017
- T018
- T019
history:
- at: '2026-10-04T10:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/skills/
create_intent:
- src/specify_cli/skills/catalog.py
- src/specify_cli/skills/pack_skill_renderer.py
- tests/specify_cli/skills/test_pack_skill_projection.py
- tests/specify_cli/skills/test_pack_skill_renderer.py
- tests/architectural/test_skill_catalog_seam.py
- tests/integration/test_pack_skill_lifecycle.py
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/skills/catalog.py
- src/specify_cli/skills/pack_skill_renderer.py
- src/specify_cli/skills/installer.py
- src/specify_cli/skills/manifest.py
- src/specify_cli/skills/verifier.py
- src/specify_cli/runtime/agent_skills.py
- src/specify_cli/upgrade/migrations/m_2_0_11_install_skills.py
- src/specify_cli/upgrade/migrations/m_2_1_1_repair_skill_pack.py
- src/specify_cli/upgrade/migrations/m_3_0_3_globalize_skill_pack.py
- src/specify_cli/upgrade/migrations/m_3_2_0rc35_spk_skill_pack.py
- src/specify_cli/tool_surface/providers/managed_skills.py
- src/specify_cli/tool_surface/providers/plugin_bundle.py
- tests/specify_cli/skills/test_pack_skill_projection.py
- tests/specify_cli/skills/test_pack_skill_renderer.py
- tests/architectural/test_skill_catalog_seam.py
- tests/integration/test_pack_skill_lifecycle.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Catalog seam and project-root projection through the managed installer

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile in the frontmatter (`python-pedro`, role implementer) and behave according to its guidance before parsing the rest of this prompt.

## Objective

Deliver FR-009, FR-010, FR-011, FR-013, SC-001, SC-003, SC-007, SC-010, NFR-002, NFR-004 of mission `pack-skills-kind-01M43419` (see `../spec.md`, `../plan.md`, ADR `docs/adr/3.x/2026-09-27-1-pack-skills-share-commands-through-charter-packs.md`).

## Branch Strategy

Planning branch and final merge target: `claude/festive-babbage-lhkqac`. Topology `single_branch`: work happens in the repository root checkout; prepare with `spec-kitty agent action implement WP04 --agent claude`.

## Subtasks

### T015

RED FIRST: write tests/integration/test_pack_skill_lifecycle.py (SC-001) — temp project with claude+codex configured and a fixture org pack registered in charter_packs.org.packs with skill_namespace; activate skill → `.claude/skills/<ns>-<id>/SKILL.md` + `.agents/skills/<ns>-<id>/SKILL.md`; run upgrade-equivalent catalog callers with retire → still present; deactivate → removed; snapshot everything else byte-identical. Mark `@pytest.mark.regression` + issue #5193 while red; record the red run; un-mark once green.

### T016

Renderer (pack_skill_renderer.py): SKILL.md frontmatter (name, description, user-invocable per invocation) + generated preamble running `spec-kitty charter context --include <urn>` for every required URN; prompt form appends body; wrapper form instructs invoking the validated `builtin:spec-kitty.<cmd>` (validated against the command set; unknown target refused) or `cli:` spec-kitty argv. No bindings baked in; no `allowed-tools`.

### T017

Catalog seam catalog.py `resolve_project_skill_catalog(project_root)`: stages rendered pack skills under `.kittify/runtime/pack-skills/<name>/SKILL.md` and returns a merged registry (built-in `SkillRegistry.from_package()` ∪ staged) respecting `snapshot_catalog`. Manifest entries gain optional `origin` (default `builtin`), `source_ref`, `source_hash` (backward-compatible load). Installer: pack skills only to project skill roots of configured agents (AGENT_SKILL_CONFIG), never global; render-name collision fails before any write; an unowned existing dir with that name is preserved and reported; fix retire guard (`installer.py:739` `if retire and skills:`) so the last pack skill is retired even with an empty catalog.

### T018

Migrate every install/assess caller to the seam: verifier.py, runtime/agent_skills.py, init.py (out-of-map edit, justify), the four migrations, upgrade/assessment.py, managed_skills.py, plugin_bundle.py. Architectural test test_skill_catalog_seam.py: AST scan — no `SkillRegistry.from_package` call outside catalog.py/registry.py (allowlist must be empty or justified read-only listings).

### T019

`charter activate/deactivate skill` (cli/commands/charter/activate.py) re-runs projection after commit_plan; deactivate retires manifest-owned pack entries only. Unit tests for renderer, collisions (0 files written, NFR-002), unowned dir, wrapper validation, empty-catalog retire. Layer test green (charter imports no specify_cli).

## Amendments (post-tasks anti-laziness squad — binding)

- T015 ATDD must drive the real paths: `spec-kitty upgrade` (or each of the 4 migrations + verifier repair with retire=True), asserting presence after each; full-tree snapshot before activate vs after deactivate, excluding only `.kittify/runtime/pack-skills/` and the manifest.
- T017: staging counts as a write — run collision/duplicate checks BEFORE staging. NFR-002 snapshot covers all agent roots, staging dir and manifest, for both prepare-time duplicate and install-time collision. Assert nothing written under a fake HOME (never user-global).
- T016: unknown `builtin:spec-kitty.nope` refused with 0 writes; import the canonical command set (no copied literal); assert rendered body excludes the required procedure's text.
- T018: init.py has two `from_package()` sites (~:309, ~:1132) — migrate both; find managed_skills.py's real catalog source (registry_factory default) — migrate it, not vacuously. AST test: allowlist exact and reviewed (empty preferred), flags `SkillRegistry(` construction and `from_package` imports/attribute access.
- `cli/commands/charter/activate.py` is WP03-owned; add only the re-projection hook here (out-of-map edit, noted).

## Definition of Done

- Every subtask done; new branches/helpers carry focused tests in the same commit (Sonar new-code gate).
- `ruff check`, `ruff format --check --force-exclude <changed files>`, `mypy` on changed modules: zero findings; complexity ≤15; no new suppressions.
- Targeted tests for touched modules plus owning subsystem dirs pass; record commands and counts in the activity log.
- Layer direction respected: `charter` never imports `specify_cli`.

## Risks

- Exact-set/totality tests across `tests/charter`, `tests/doctrine`, `tests/architectural` enumerate kinds — find them by running those directories' fast tier.
- Out-of-map edits are allowed only with a one-line rationale in the activity log.

## Reviewer Guidance

Verify each requirement in the objective has a non-vacuous test; reject no-op passes.

## Activity Log

- 2026-10-04 claude (python-pedro, WP04) -- implemented T015-T019. Commits: 00bc3e1f (seam + renderer + manifest provenance + installer), 7302420b (caller migration + AST gate), f8305efb (activate/deactivate hook + SC-001 ATDD + WP03 dead-code rows removed).
  - Red-first evidence (T015): the implementation spike preceded the ATDD file, so the red was recorded against a clean worktree of the base. (1) `tests/integration/test_pack_skill_lifecycle.py` against base: `ModuleNotFoundError: No module named 'specify_cli.skills.catalog'` (collection error). (2) A behavioural probe at base (`charter activate skill deploy-helper` in a claude+codex project with an org pack): `AssertionError: assert False ... (project/'.claude/skills/acme-deploy-helper/SKILL.md').is_file()` -- nothing is projected. Mark `@pytest.mark.regression` was applied while red and removed once green (docstring cites #5193).
  - Tests run (passed/failed):
    - New: `pytest tests/integration/test_pack_skill_lifecycle.py` 6 passed; `tests/specify_cli/skills/test_pack_skill_projection.py` 22 passed; `test_pack_skill_renderer.py` 30 passed; `tests/architectural/test_skill_catalog_seam.py` 24 passed.
    - Gate files: `pytest tests/architectural/{test_no_dead_symbols,test_no_dead_modules,test_ratchet_baselines,test_dead_symbol_allowlist_contract,test_layer_rules,test_skill_catalog_seam,test_charter_no_specify_cli_import,test_scanner_parse_fail_closed}.py -n auto --dist loadfile` -> 224 passed (after the first run caught 2 dead symbols, `prepare_skill_activations` and `PACK_SKILL_STAGING`, fixed by making them module-private).
    - Fast tier `pytest tests/specify_cli/skills tests/upgrade tests/specify_cli/tool_surface tests/charter -m "fast or unit" -n auto --dist loadfile` -> 5412 passed, 7 failed: 5 mine (tests/charter/test_skill_activation.py cascade tests: no agents configured but the hook refused a namespaceless skill; fixed by checking installable agents before resolving the catalog, now 38 passed) and 2 pre-existing (see below).
    - Callers' tests, unfiltered: `pytest tests/runtime/{test_agent_skills,test_generic_asset_scope,test_reassess_under_lock,test_upgrade_preview_bootstrap,test_build_serialized,test_startup_torn_read_escalation,test_check_assets_membership_tolerance}.py tests/init tests/specify_cli/cli/commands/test_init_{integration,provisioning,vibe,pi_letta,llxprt}.py test_doctor_slash_commands.py tests/specify_cli/skills tests/specify_cli/tool_surface tests/upgrade tests/integration/test_init_fresh_project_chain.py ...` first run 44 failed / 2882 passed (28 were `Baseline source is dirty` from my uncommitted tree; re-run after committing, `pytest tests/upgrade tests/runtime/test_reassess_under_lock.py tests/specify_cli/skills tests/integration/test_pack_skill_lifecycle.py tests/architectural/test_skill_catalog_seam.py tests/charter/test_skill_activation.py tests/charter/test_skill_preparation.py` -> 1519 passed, 10 failed).
    - `make test-fast` once at the end -> 2251 passed, 8 skipped, 0 failed.
    - Failures that are not mine: `tests/charter/test_pack_manager.py::test_preparation_refuses_broken_required_inputs[unreadable]` (root chmod, brief); `tests/upgrade/test_migration_robustness.py::TestPermissionErrors::test_readonly_gitignore_clear_error` and `tests/init/test_init_idempotent.py::test_initialized_clone_vibe_pointer_recovery_and_repeat` (both red on a clean worktree of 1821e529); `tests/upgrade/test_mission_corpus_recovery.py` x9 (`git archive c0054153...` -- that object is absent from this clone, environment).
    - ruff check + `ruff format --check --force-exclude` on all changed files clean; mypy on the changed modules shows only the narrow-path Any noise that is also present on unchanged lines (skill_preparation `_source_hash`, assessment.py:74/130, activate.py:674, plugin_bundle.py:246, managed_skills.py:388); no new suppressions.
  - Out-of-map edits (rationale): `src/specify_cli/skills/registry.py` (`CanonicalSkill` gains `origin`/`source_ref`/`source_hash`, defaulted, so a catalog entry carries provenance without a parallel structure); `src/specify_cli/cli/commands/charter/activate.py` + `deactivate.py` (only the re-projection hook `reproject_pack_skills`, per the brief); `src/specify_cli/cli/commands/init.py` (both `from_package` sites, per the brief); `src/charter/activation/skill_preparation.py` + `tests/charter/test_skill_preparation.py` (pure `prepare_skill_activations` renamed `_prepare_skill_activations` and dropped from `__all__`: the dead-symbol gate requires a production caller for a public name and the only one is `prepare_project_skill_activations`; two-line test rename); `tests/architectural/{dead_symbol_allowlist.yaml,_baselines.yaml,test_no_dead_modules.py}` (WP03's transitional rows removed, baselines back to 294 and 2).
  - Deviations / notes:
    - `PACK_SKILL_STAGING` is private (`_PACK_SKILL_STAGING`); tests assert the literal documented path `.kittify/runtime/pack-skills`.
    - ADR/spec/plan text names `prepare_skill_activations` as the seam; code now exposes `prepare_project_skill_activations` publicly and the pure core privately -- WP05 docs pass should reword.
    - `from_local_repo` is gated along with `from_package` (same bypass); the seam owns both, allowlist empty.
    - `runtime/agent_skills.py` uses `resolve_builtin_skill_catalog()` (built-in only) because it feeds the user-global roots; pack skills are filtered out of the global batch in `assess_skill_installation` (`origin == "builtin"`).
    - `charter activate/deactivate skill` runs the pack-only projection (assessment restricted to pack-skill paths plus manifest-owned pack entries; built-in files untouched; no global writes). A refusal after the committed activation exits 1 with a recover-and-rerun message and writes no skill file. With no installable agent configured it neither stages nor refuses.
    - Retire guard: with an empty catalog only pack-origin manifest entries are retired (built-ins are never wiped by an ambiguous empty catalog); a pre-existing unowned same-name directory (even without SKILL.md) is preserved and reported.
    - m_3_0_3 / m_3_2_0rc35 no longer re-add pack-origin manifest entries as "preserved" (would resurrect a retired pack skill); m_3_0_3 `detect` skips pack skills when checking for global links.
    - Manifest serialization omits default provenance fields, so existing manifests stay byte-stable (test pins it).
    - `tests/charter/skill_pack_support.py` default wrapper target `builtin:spec-kitty.merge` is not a canonical command (merge is not in CANONICAL_COMMANDS); the ATDD never uses it as an active wrapper. WP03's fixture default was left alone.
    - The full-tree snapshot in the ATDD seeds `activated_skills: []` so the config round-trips byte-identically; the tree comparison excludes only the staging dir and the manifest (plus the empty `.kittify/runtime` parent).
- 2026-10-04 claude (python-pedro, WP04, review cycle 2) -- fixed all three findings.
  - Process deviation: the SC-001 ATDD (T015) was written AFTER the implementation, not before; the red evidence (ModuleNotFoundError for specify_cli.skills.catalog; `charter activate skill` projecting nothing) was recorded against a clean base worktree.
  - (1) `detect()` of m_2_1_1 / m_3_0_3 / m_3_2_0rc35 returns True on PackSkillCatalogError, so `apply()` reports it as a failed migration (runner records `failed`, no traceback, dry-run included).
  - (2) `resolve_project_skill_catalog(..., stage=False)` is the read-only mode (renders into a process-lifetime temp dir outside the project). Used by every detect, dry-run apply, verifier, upgrade assessment, plugin_bundle and managed_skills assess/expand; install/apply paths still stage.
  - (3) `_stage` removes the staging root only when it exists and has content.
  - Commits: fix(WP04) read-only resolution + staging rmtree (catalog, verifier, assessment, plugin_bundle, managed_skills); fix(WP04) migration detect fail-closed + read-only detect/dry-run (4 migrations, tests/specify_cli/skills/test_pack_skill_read_only.py, 19 tests).
  - Tests: test_pack_skill_read_only.py 19 passed; `tests/upgrade/migrations tests/specify_cli/skills tests/specify_cli/tool_surface tests/integration/test_pack_skill_lifecycle.py tests/architectural/test_skill_catalog_seam.py` -> 1919 passed, 0 failed. ruff clean.
