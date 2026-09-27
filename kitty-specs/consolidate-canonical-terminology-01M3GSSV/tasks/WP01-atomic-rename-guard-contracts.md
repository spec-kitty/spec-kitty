---
work_package_id: WP01
title: Atomic rename + guard + machine contracts
dependencies: []
requirement_refs:
- C-001
- C-002
- C-003
- C-004
- C-007
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-009
- FR-010
- NFR-001
- NFR-002
- NFR-003
- NFR-004
planning_base_branch: feat/consolidate-canonical-terminology
merge_target_branch: feat/consolidate-canonical-terminology
branch_strategy: Planning artifacts for this mission were generated on feat/consolidate-canonical-terminology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/consolidate-canonical-terminology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-consolidate-canonical-terminology-01M3GSSV
base_commit: 0d416995d0c90c3609809f16a9f4168571759243
created_at: '2026-09-27T08:05:18.161861+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
- T008
- T009
- T010
- T011
- T012
- T013
- T014
- T015
phase: Phase 1 - Atomic core rename
history:
- at: '2026-09-27T07:39:01Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- src/specify_cli/cli/commands/consolidate.py
- src/specify_cli/consolidation/
- src/specify_cli/lanes/consolidation.py
- tests/consolidation/
- tests/specify_cli/consolidation/
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- CHANGELOG.md
- docs/api/agent-subcommands.md
- docs/api/cli-commands.md
- pyproject.toml
- src/specify_cli/cli/commands/__init__.py
- src/specify_cli/cli/commands/_coordination_doctor.py
- src/specify_cli/cli/commands/accept.py
- src/specify_cli/cli/commands/agent/mission.py
- src/specify_cli/cli/commands/agent/mission_accept_merge.py
- src/specify_cli/cli/commands/consolidate.py
- src/specify_cli/cli/commands/init.py
- src/specify_cli/cli/commands/merge.py
- src/specify_cli/cli/commands/migrate_cmd.py
- src/specify_cli/cli/commands/next_cmd.py
- src/specify_cli/cli/commands/research.py
- src/specify_cli/cli/commands/review/_dead_code.py
- src/specify_cli/consolidation/
- src/specify_cli/coordination/coherence.py
- src/specify_cli/coordination/teardown.py
- src/specify_cli/core/paths.py
- src/specify_cli/core/upstream_contract.json
- src/specify_cli/git/bookkeeping_commit.py
- src/specify_cli/lanes/_git.py
- src/specify_cli/lanes/auto_rebase.py
- src/specify_cli/lanes/consolidation.py
- src/specify_cli/lanes/merge.py
- src/specify_cli/lanes/worktree_allocator.py
- src/specify_cli/merge/
- src/specify_cli/orchestrator_api/commands.py
- src/specify_cli/upgrade/migrations/_merge_driver_seeding.py
- src/specify_cli/upgrade/migrations/m_3_2_7_review_cycle_merge_driver.py
- tests/acceptance/test_post_consolidation.py
- tests/agent/cli/commands/test_merge_target_resolution.py
- tests/agent/test_commands.py
- tests/agent/test_init_command.py
- tests/agent/test_orchestrator_commands_integration.py
- tests/architectural/_gate_coverage.py
- tests/architectural/test_coord_rollback_coherence_guard.py
- tests/architectural/test_json_contract_enumeration.py
- tests/architectural/test_merge_pipeline_ratchets.py
- tests/architectural/test_merge_reconciliation_class_guard.py
- tests/architectural/test_module_shard_registry.py
- tests/architectural/test_no_dead_symbols.py
- tests/architectural/test_no_legacy_terminology.py
- tests/architectural/test_resume_non_reemission_guard.py
- tests/architectural/test_retirement_scrub.py
- tests/architectural/test_src_reachability_guard.py
- tests/architectural/test_status_events_writes_gate.py
- tests/architectural/test_write_surface_placement_guard.py
- tests/ci/test_coverage_guards.py
- tests/cli/commands/test_merge_status_commit.py
- tests/cli/commands/test_merge_strategy.py
- tests/consolidation/
- tests/contract/test_identity_contract_matrix.py
- tests/coordination/test_coherence.py
- tests/coordination/test_projection_teardown.py
- tests/git_ops/test_git_state_detection_unit.py
- tests/git_ops/test_worktree.py
- tests/init/test_init_in_existing_repo.py
- tests/integration/sparse_checkout/test_merge_preflight_blocks.py
- tests/integration/sparse_checkout/test_merge_refresh_and_invariant.py
- tests/integration/sparse_checkout/test_merge_with_allow_override.py
- tests/integration/test_2939_move_task_clean_tree_after_rejection.py
- tests/integration/test_coord_read_residuals_proof.py
- tests/integration/test_issue_4863_merge_abort_no_state.py
- tests/integration/test_lanes_core_coord_read.py
- tests/integration/test_merge_abort_scope.py
- tests/integration/test_merge_cluster_coord_read.py
- tests/integration/test_merge_lane_planning_data_loss.py
- tests/integration/test_merge_lane_worktree_safety.py
- tests/integration/test_merge_primary_checkout_safety.py
- tests/integration/test_merge_resume.py
- tests/integration/test_mission_close.py
- tests/integration/test_post_merge_index_refresh.py
- tests/integration/test_post_merge_unrelated_untracked.py
- tests/integration/test_tool_artifact_owner.py
- tests/lanes/test_lane_base_common_ancestor.py
- tests/lanes/test_merge.py
- tests/lanes/test_merge_policy.py
- tests/lanes/test_worktree_allocator_merge_driver_selfheal.py
- tests/merge/
- tests/migration/test_birth_cutover.py
- tests/mission_runtime/test_consolidated_resolution.py
- tests/mission_runtime/test_lifecycle_phase.py
- tests/review/test_review_cycle_merge_driver.py
- tests/specify_cli/acceptance/test_accept_dirty_kitty_ops.py
- tests/specify_cli/cli/commands/agent/test_wrapper_delegation.py
- tests/specify_cli/cli/commands/review/test_dead_code_baseline.py
- tests/specify_cli/cli/commands/test_coordination_doctor.py
- tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py
- tests/specify_cli/cli/commands/test_issue_3033_post_consolidation_write.py
- tests/specify_cli/cli/commands/test_lifecycle_read_seam_migration.py
- tests/specify_cli/cli/commands/test_merge.py
- tests/specify_cli/cli/commands/test_merge_coord_topology_1772.py
- tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py
- tests/specify_cli/cli/commands/test_merge_dry_run_review_artifact.py
- tests/specify_cli/cli/commands/test_migrate_backfill_merge_commit.py
- tests/specify_cli/cli/commands/test_review_cycle_merge_driver.py
- tests/specify_cli/cli/commands/test_safe_commit_cmd.py
- tests/specify_cli/consolidation/
- tests/specify_cli/coordination/test_residual_writer_routing.py
- tests/specify_cli/coordination/test_status_transition.py
- tests/specify_cli/coordination/test_write_seam_thunk.py
- tests/specify_cli/merge/
- tests/specify_cli/migration/test_backfill_migration_coexistence.py
- tests/specify_cli/retrospective/test_generator_traces_ingest.py
- tests/specify_cli/status/test_merged_at_writer_and_reopen_4090.py
- tests/specify_cli/test_audit_tail_readers.py
- tests/specify_cli/test_lane_consumer_behavior.py
- tests/specify_cli/test_meta_fail_closed_degradation_paths.py
- tests/specify_cli/test_meta_fail_closed_full_census_contract.py
- tests/specify_cli/test_specify_topology_flag.py
- tests/specify_cli/test_workspace_context_tombstone.py
- tests/terminus/test_repro_4973.py
- tests/terminus/test_repro_4982.py
- tests/terminus/test_repro_4985.py
- tests/terminus/test_repro_4991.py
- tests/terminus/test_repro_4997.py
- tests/terminus/test_repro_5021.py
- tests/terminus/test_repro_5038.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Atomic rename + guard + machine contracts

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

---

## Objectives & Success Criteria

This is the **unsplittable atomic core** of mission #3080. The physical package rename breaks
every importer at once (plan **A1/A6**), so the rename, the command surface, the delegation
repoints, the drift-guard baseline update, and the machine-contract regeneration land as **one
write-scope-atomic commit set**. Partial commits leave a red tree and are forbidden.

Complete when:

- **SC-001**: `spec-kitty consolidate` performs lane consolidation with the full former-`merge` flag set (`--resume/--abort/--dry-run/--keep-branch/--keep-worktree/--mission/--feature/--target`); `spec-kitty merge` exits non-zero with a "renamed to `consolidate`" migration message (no silent consolidation, no bare "unknown command"). *(FR-001, FR-002)*
- **SC-002**: 0 regressions across the former `tests/merge/` (now `tests/consolidation/`) suite; an in-flight `state.json` and legacy `meta.json` (incl. `baseline_merge_commit`) still resume/read. *(FR-003, NFR-001)*
- **SC-003**: `test_no_legacy_terminology.py` **fails** a newly-introduced lane-consolidation-sense `spec-kitty merge` (red-first) and **passes** on `git merge --no-ff` / "publish to origin" (green-on-legit). *(FR-009)*
- **SC-005**: Frozen KEEPS verbatim — `baseline_merge_commit`, `MergeStrategy="merge"`, `state.json` filename, merge-drivers, `trigger_mode` `post_merge` — and phase derivation still resolves `PRE_CONSOLIDATION`/`CONSOLIDATED`. *(FR-005, C-002)*
- Quality gates clean: `ruff check .`, `ruff format --check .`, `mypy`, touched functions ≤ complexity 15. *(NFR-003, NFR-004)*

## Context & Constraints

- **Authoritative reads**: `.kittify/charter/charter.md`, [`plan.md`](../plan.md) (esp. **Post-Plan Brownfield Amendments A1–A6** — binding), [`spec.md`](../spec.md), [`research.md`](../research.md), [`data-model.md`](../data-model.md), and [`occurrence_map.yaml`](../occurrence_map.yaml).
- **`occurrence_map.yaml` is the sole classification authority (C-001, DIRECTIVE_035).** Every touched occurrence is classified rename-now / keep before you edit. No bare `sed s/merge/consolidate/`. This is a **semantic** rename: only the **lane-consolidation sense** becomes `consolidate`; **git-merge/branch-integration keeps "merge"/"integrate"**, **publish-to-origin keeps "publish"**.
- **FROZEN KEEPS — never rename** (occurrence_map exceptions, `data-model.md` table):
  - `baseline_merge_commit` — meta.json wire-key, drives phase derivation at `src/mission_runtime/lifecycle_phase.py:237-239`. Freeze the key; boyscout only local prose/identifiers.
  - `MergeStrategy` enum + its `"merge"` value (`merge/config.py` → `consolidation/config.py`) — Sense-B git-strategy serialized contract.
  - `state.json` filename + `.kittify/runtime/merge/<id>/` dir — renaming strands in-flight resumable consolidations.
  - merge-driver plumbing (`cli/commands/merge_driver.py`, `.gitattributes`/git-config) — literal git plumbing, Sense B. **Do not rename `merge_driver.py`.**
  - `trigger_mode: Literal["manual","post_merge","both"]` on the frozen model at `src/runtime/next/_internal_runtime/schema.py:360` — serialized enum value (plan A5). Out of scope.
- **No re-export shim (A3)**: no external consumer imports a *renamed* symbol. Repoint importers directly; do not add a code-level alias (contradicts the clean-rename posture; `data-model.md` NFR-002 → shim count **none**).
- **Grow `__all__`, never shrink (#2057)**; use `git mv` for every file rename to preserve history.
- **Positive fact (A6)**: `MergeState.to_dict = asdict` persists fields only — no class-name/module-path on disk, so the class rename is on-disk-safe. Names `consolidation/`, `ConsolidationState`, `tests/consolidation/` are all free.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: `feat/consolidate-canonical-terminology`
- **Merge target branch**: `feat/consolidate-canonical-terminology`

> Populated by `spec-kitty agent mission tasks`. Do NOT change manually unless the branch topology changed.

## Subtasks & Detailed Guidance

### T001 – Rename `merge/` → `consolidation/` package
- **Purpose**: Physically move the lane-consolidation package so import paths move (occurrence_map `import_paths: rename`).
- **Steps**: `git mv src/specify_cli/merge src/specify_cli/consolidation`; fix all intra-package relative imports; keep `config.py` (`MergeStrategy`/`"merge"` frozen) and internal git-sense symbols verbatim.
- **Files**: `src/specify_cli/merge/**` → `src/specify_cli/consolidation/**` (state.py, executor.py, forecast.py, resolve.py, retention.py, reconciliation.py, git_probes.py, baseline.py, config.py, preflight.py, bookkeeping_projection.py, _constants.py, __init__.py, …).
- **Notes**: `state.py`, `preflight.py`, `executor.py`, `forecast.py`, `resolve.py`, `retention.py`, `bookkeeping_projection.py` are referenced across the repo — see CLAUDE.md "Merge & Preflight Patterns".

### T002 – Rename `lanes/merge.py` → `lanes/consolidation.py` + result symbols
- **Purpose**: The second lane-consolidation module (research §"second module").
- **Steps**: `git mv src/specify_cli/lanes/merge.py src/specify_cli/lanes/consolidation.py`; rename `LaneMergeResult`→`LaneConsolidationResult`, `MissionMergeResult`→`MissionConsolidationResult`; repoint importers.

### T003 – Rename lane-consolidation-sense symbols
- **Purpose**: `MergeState`→`ConsolidationState`, `_run_lane_based_merge`→`_run_lane_based_consolidation` and their siblings (`save_state`/`load_state`/`clear_state`/`has_active_merge`→`has_active_consolidation` where the identifier names the lane-consolidation op).
- **Steps**: Rename symbols across `consolidation/**`; **keep** `MergeStrategy` and the `"merge"`/`"squash"`/`"rebase"` strategy values. Grow `__all__`. Classify each identifier against occurrence_map `code_symbols: manual_review`.
- **Notes**: 51 test files reference `MergeState` (A6) — they move/repoint in T009.

### T004 – `cli/commands/merge.py` → `consolidate.py`, primary command
- **Purpose**: `consolidate` becomes the primary CLI command (FR-001).
- **Steps**: `git mv`; rename body `merge()`→`consolidate()`; register `consolidate` in `cli/commands/__init__.py`; carry the full flag set. Fix the exit-contract ref at old `cli/commands/merge.py:525`.

### T005 – Hidden `merge` migration-error stub
- **Purpose**: `spec-kitty merge` fails loudly (FR-002, C-004; overrides #3080's alias AC).
- **Steps**: Register a **hidden** `merge` command that exits non-zero with a message naming `spec-kitty consolidate`. **No working body, no alias, no shared consolidation logic.** `--resume/--abort/--dry-run` on `merge` also hit the stub.

### T006 – Repoint delegation seams
- **Purpose**: `cli/commands/mission.py:323 top_level_merge = _merge` and `mission_accept_merge.py:252` invoke the command as a **working body** (Paula #1) — repoint to the `consolidate` body, NOT the stub.
- **Steps**: Repoint both seams; update `test_wrapper_delegation.py:130` (currently mocks `top_level_merge`, hiding the break) to assert the working `consolidate` body.

### T007 – [P] Repoint all internal + external importers
- **Purpose**: 129 test files reference `specify_cli.merge` (A6); the unowned external importer `orchestrator_api/commands.py` imports at `:829/:833 _run_lane_based_merge`, `:981 _mark_wp_merged_done`, `:984 lanes.merge`, `:986 merge.config`, `:988 policy.merge_gates`.
- **Steps**: Repoint every internal importer to `consolidation`/`lanes.consolidation`; repoint `orchestrator_api/commands.py`. Note `merge.config` imports `MergeStrategy` (frozen) — repoint the path, keep the symbol.

### T008 – `merge-mission` → `consolidate-mission` orchestrator command
- **Purpose**: Canonical-word consistency on the external orchestrator-api contract (plan **A4** — flagged for operator veto; kept in scope here).
- **Steps**: Rename `@app.command(name="merge-mission")` (`orchestrator_api/commands.py:2129`)→`consolidate-mission`; update `core/upstream_contract.json:92` token to `consolidate-mission` (allowed); **keep `:108 merge-feature` forbidden**.
- **Notes**: If the operator vetoes A4, this subtask is dropped and `upstream_contract.json:92` stays `merge-mission` — confirm before landing.

### T009 – `tests/merge/` → `tests/consolidation/` + fixtures
- **Purpose**: Behavior suite rename (occurrence_map `tests_fixtures: manual_review`); 72 files (A6).
- **Steps**: `git mv tests/merge tests/consolidation`; repoint every import; **keep frozen-KEEP assertions verbatim** (`MergeStrategy` value, `baseline_merge_commit`). Fix `test_merge_compat_surface.py:329` (old module path) + `test_json_contract_enumeration.py:357`.

### T010 – Logger name, baseline.py prose, freeze key
- **Purpose**: FR-010 phase-naming coherence + stale-logger campsite; freeze the wire-key.
- **Steps**: Fix hardcoded logger `merge/_constants.py:21` (`"specify_cli.cli.commands.merge"`→consolidate path). Converge `post-merge` **prose** in `consolidation/baseline.py:5,102,113,136,326,345` onto the canonical vocabulary — **but keep the `baseline_merge_commit` key verbatim**. Do NOT introduce a `POST_CONSOLIDATION` symbol (converge on landed `CONSOLIDATED`/`PRE_CONSOLIDATION`).

### T011 – `_gate_coverage.py:1983` dir rename
- **Purpose**: `tests/architectural/_gate_coverage.py:1983 _PRE_MISSION_MAPPED_SRC_DIRS` lists `"merge"` → update for the dir rename.
- **Steps**: Change the frozenset entry to `"consolidation"`.

### T012 – Drift-guard baseline paths
- **Purpose**: `test_no_legacy_terminology.py:360/:362` pin `lanes/merge.py` + `merge/git_probes.py`; `:491 _currently_real` asserts existence → reds on rename (moved here from IC-07 per A1).
- **Steps**: Update the baseline paths to the consolidation locations so `_currently_real` resolves.

### T013 – New command-surface ratchet (FR-009 fold)
- **Purpose**: A command-surface `"spec-kitty merge"` + lane-consolidation-phrasing ratchet, its own baseline + historical allowlist, scanning `src`, `docs`, **and `packs/`** (SC-003). FR-009 folds here because it shares this file.
- **Steps**: Add the ratchet to `test_no_legacy_terminology.py`. Prove **red-first** (a fixture line with lane-consolidation-sense `spec-kitty merge` fails) and **green-on-legit** (`git merge --no-ff` / "publish to origin" passes). Grandfather the deferred long-tail via the historical allowlist (shrink-only, C-008).
- **Notes**: Do NOT touch the two legacy-terminology reds this file already gates (`status commit` vocabulary) — extend, don't rewrite.

### T014 – [P] Regenerate machine-contract docs
- **Purpose**: `docs/api/cli-commands.md` (carries `## spec-kitty merge` :3063 + `merge-mission` :4789) and `docs/api/agent-subcommands.md` are **generated** + strict-freshness-gated (`check_cli_reference_freshness.py:397-400`) — regenerate, never hand-edit (plan A2).
- **Steps**: Run `python scripts/docs/build_cli_reference.py`; commit the regenerated output. Confirm the freshness gate passes.

### T015 – Version bump + CHANGELOG
- **Purpose**: C-007 — `cli/commands/__init__.py` changed.
- **Steps**: Bump the version in `pyproject.toml`; add a `CHANGELOG.md` entry describing the consolidate rename. (**Do not** prescribe a specific patch level beyond project convention.)

## Test Strategy

- **Behavior preservation (NFR-001)**: run the renamed suite — `PWHEADLESS=1 .venv/bin/python -m pytest tests/consolidation/ -q` — expect the former green count, 0 regressions.
- **Command surface**: assert `spec-kitty consolidate --help` shows the full flag set; `spec-kitty merge` exits non-zero with the migration message; `consolidate --resume` reads `state.json`.
- **Drift guard (red-first)**: `pytest tests/architectural/test_no_legacy_terminology.py -q` — add the failing fixture first (prove red), then the ratchet (prove green + green-on-legit). ≈0.1 s.
- **Frozen-KEEP positive controls (SC-005)**: assert `baseline_merge_commit` key, `MergeStrategy="merge"` value unchanged; phase derivation resolves `PRE_CONSOLIDATION`/`CONSOLIDATED`.
- **Blast radius (CLAUDE.md test policy)**: run `tests/consolidation/`, plus the test files of every module your diff touches (`tests/status/`, `tests/specify_cli/`, orchestrator-api tests), and — because this diff edits `tests/architectural/_gate_coverage.py`, `pytest`-adjacent config, and packaging-relevant surfaces — `tests/architectural/` (cross-cutting). Record commands + passed/failed counts in the PR *Tests run* section. Use narrow foreground file-scoped runs; do NOT run `make test-full`.
- **Typecheck/format**: `mypy`, `ruff check .`, `ruff format --check .` (or `make format-check`) — zero issues.

## Risks & Mitigations

- **Half-rename / whack-a-field** → drive every edit from `occurrence_map.yaml`; full `tests/consolidation/` + import-boundary tests are the net.
- **Renaming a frozen KEEP** (the load-bearing failure) → the SC-005 positive controls; treat `baseline_merge_commit`, `MergeStrategy="merge"`, `state.json`, merge-drivers, `trigger_mode` `post_merge` as untouchable.
- **Red tree mid-mission (A1)** → land as one commit set; do not stage partial importer updates.
- **A4 operator veto** → confirm `merge-mission`→`consolidate-mission` is in scope before landing T008; otherwise keep `upstream_contract.json:92` frozen.
- **Stale-install false reds** → code that shells out to `spec-kitty` only fires after `pip install -e .`; reinstall before recording a red (CLAUDE.md gotcha).

## Review Guidance

- Confirm `occurrence_map.yaml` classifies every touched site; no bare find-replace.
- Verify frozen KEEPS verbatim (grep `baseline_merge_commit`, `MergeStrategy`, `"merge"` strategy value, `state.json`, `merge_driver`, `post_merge`).
- Verify `spec-kitty merge` is a **stub** (non-zero, no shared body), and the delegation seams (`mission.py`, `mission_accept_merge.py`) point at the **working** `consolidate` body (not the stub) — `test_wrapper_delegation.py` asserts this.
- Verify the ratchet is red-first-proven and green-on-legit; the two pre-existing `status commit` reds untouched.
- Confirm `docs/api/*.md` were **regenerated** (freshness gate green), not hand-edited.
- Confirm the implementer ran `mypy` + `ruff format --check .` alongside the test runner.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last). APPEND at the END.

- 2026-09-27T07:39:01Z – system – Prompt created.
