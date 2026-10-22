---
work_package_id: WP01
title: Test seeding helper and codemod (tidy-first)
dependencies: []
requirement_refs:
- FR-004
- NFR-001
- SC-004
planning_base_branch: feat/event-write-hygiene
merge_target_branch: feat/event-write-hygiene
branch_strategy: Planning artifacts for this mission were generated on feat/event-write-hygiene. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/event-write-hygiene unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Tidy-first
history:
- at: '2026-10-22T13:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/_support/
create_intent:
- tests/_support/status_seed.py
- tests/status/test_status_seed_helper.py
execution_mode: code_change
model: ''
owned_files:
- tests/_support/status_seed.py
- tests/status/test_status_seed_helper.py
- tests/_factories/coord_mission.py
- tests/agent/test_context_resolve_unit.py
- tests/agent/test_status_state_phantom_degrade.py
- tests/agent/test_workflow_feedback_pointer_2x_unit.py
- tests/agent/test_workflow_review_cycle_pointer.py
- tests/agent/test_workflow_review_lane_gate.py
- tests/architectural/test_2093_authority_invariant.py
- tests/architectural/test_no_op_stable_writes.py
- tests/characterization/test_trio_pure_cores.py
- tests/characterization/test_trio_transitions.py
- tests/charter_offering/test_spk_show_me_skill.py
- tests/cli/test_agent_retrospect_missing_record.py
- tests/cli/test_charter_activate_warning.py
- tests/cli/test_move_task_planned_guard.py
- tests/consolidation/test_2959_skip_review_artifact_check.py
- tests/consolidation/test_canceled_dependency_lane.py
- tests/consolidation/test_conflict_resolution_integration.py
- tests/consolidation/test_coord_teardown_order_3926.py
- tests/consolidation/test_done_bookkeeping_seam.py
- tests/consolidation/test_event_count_union_4091.py
- tests/consolidation/test_issue_2709_projection_union.py
- tests/consolidation/test_merge_done_recording.py
- tests/contract/test_machine_facing_canonical_fields.py
- tests/coordination/test_status_transition_write_dir.py
- tests/core/test_mission_create_idempotency_guard.py
- tests/cross_branch/test_parity.py
- tests/git_ops/test_atomic_status_commits_unit.py
- tests/integration/migration/test_noop_upgrade_leaves_history_untouched.py
- tests/integration/migration/test_residue_dir_not_treated_as_mission.py
- tests/integration/refinalize_frozen_lanes_support.py
- tests/integration/review/test_approve_without_force.py
- tests/integration/review/test_reject_from_in_review.py
- tests/integration/test_2646_stale_verdict_closes_via_fr001.py
- tests/integration/test_ac5_hash_guard.py
- tests/integration/test_custom_mission_runtime_walk.py
- tests/integration/test_dossier_snapshot_no_self_block.py
- tests/integration/test_explicit_checkout_commands.py
- tests/integration/test_implement_review_retrospect_smoke.py
- tests/integration/test_mission_archiving.py
- tests/integration/test_owned_next_runtime.py
- tests/integration/test_placement_partition_golden_path.py
- tests/integration/test_prompt_builder_owned_arms.py
- tests/integration/test_rejection_cycle.py
- tests/integration/test_review_cycle_rejection_only.py
- tests/integration/test_review_durability_matrix.py
- tests/integration/test_review_handoff.py
- tests/integration/test_two_partition_preview.py
- tests/integration/test_worktree_topology_claim_base.py
- tests/integration/test_wp_file_hash_stability.py
- tests/integration/test_wp_integrity_p0_repro.py
- tests/lanes/test_claim_base.py
- tests/lanes/test_issue_4889_destroyed_lane_guard.py
- tests/lanes/test_recovery_post_merge.py
- tests/lanes/test_recovery_write_dir.py
- tests/migration/test_mission_state_repair.py
- tests/mission_runtime/test_claim_commit.py
- tests/mission_runtime/test_resolution_target_branch.py
- tests/next/test_decision_unit.py
- tests/next/test_finalized_task_routing.py
- tests/next/test_next_claimable_payload.py
- tests/next/test_next_command_integration.py
- tests/next/test_prompt_builder_review_base.py
- tests/next/test_runtime_bridge_unit.py
- tests/orchestrator_api/test_issue_4889_caller_independence.py
- tests/perf/test_tasks_status_baseline.py
- tests/post_merge/test_2684_review_override_recognition.py
- tests/post_merge/test_review_artifact_consistency.py
- tests/reliability/fixtures/mission.py
- tests/retrospective/test_reducer_integration.py
- tests/retrospective/test_tracer_writer_write_dir.py
- tests/review/test_arbiter.py
- tests/review/test_artifacts.py
- tests/review/test_cycle_write_dir.py
- tests/review/test_pre_review_gate_integration.py
- tests/review/test_verdict_save_performance.py
- tests/review/test_verdict_seam_reader_collapse.py
- tests/runtime/_next_mission_scaffold.py
- tests/runtime/next/test_cli_guard_family.py
- tests/runtime/next/test_committed_authority.py
- tests/runtime/next/test_coord_topology_fixture.py
- tests/runtime/next/test_merged_mission_terminal.py
- tests/runtime/test_artifact_presence_placement.py
- tests/runtime/test_cli_guard_family.py
- tests/runtime/test_next_board_authority.py
- tests/runtime/test_run_state_hardening.py
- tests/runtime/test_runtime_bridge_read_path_branches.py
- tests/runtime/test_workspace_context_unit.py
- tests/specify_cli/acceptance/test_accept_candidate_source_tree_4254.py
- tests/specify_cli/acceptance/test_accept_idempotency.py
- tests/specify_cli/acceptance/test_accept_pre30_hard_reject.py
- tests/specify_cli/acceptance/test_populate_criteria_from_review_evidence.py
- tests/specify_cli/cli/commands/_review_fixtures.py
- tests/specify_cli/cli/commands/agent/_rework_loop_harness.py
- tests/specify_cli/cli/commands/agent/test_2684_force_provenance.py
- tests/specify_cli/cli/commands/agent/test_approval_after_forced_review_exit.py
- tests/specify_cli/cli/commands/agent/test_cancellation_provenance.py
- tests/specify_cli/cli/commands/agent/test_check_unchecked_subtasks_snapshot_source.py
- tests/specify_cli/cli/commands/agent/test_claim_ancestry_gate.py
- tests/specify_cli/cli/commands/agent/test_claim_event_source.py
- tests/specify_cli/cli/commands/agent/test_finalize_provenance_guard.py
- tests/specify_cli/cli/commands/agent/test_finalize_tasks_commit_surface.py
- tests/specify_cli/cli/commands/agent/test_fixmode_ownership_4673.py
- tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py
- tests/specify_cli/cli/commands/agent/test_implement_runtime_frontmatter_claim.py
- tests/specify_cli/cli/commands/agent/test_issue_3311_finalize_rewrites_active_lanes.py
- tests/specify_cli/cli/commands/agent/test_issue_4141_refresh_planning_commit.py
- tests/specify_cli/cli/commands/agent/test_issue_4827_repin_orphaned_planning_commit.py
- tests/specify_cli/cli/commands/agent/test_issue_5328_finalize_refresh_dry_run.py
- tests/specify_cli/cli/commands/agent/test_issue_5328_refresh_fail_closed.py
- tests/specify_cli/cli/commands/agent/test_move_task_agent_persistence_3029.py
- tests/specify_cli/cli/commands/agent/test_move_task_approval_body_collision.py
- tests/specify_cli/cli/commands/agent/test_move_task_approval_evidence.py
- tests/specify_cli/cli/commands/agent/test_move_task_done_exit.py
- tests/specify_cli/cli/commands/agent/test_move_task_durability.py
- tests/specify_cli/cli/commands/agent/test_move_task_orchestration.py
- tests/specify_cli/cli/commands/agent/test_move_task_reject_fix_approve_cycle.py
- tests/specify_cli/cli/commands/agent/test_move_task_rollback_clears_claim.py
- tests/specify_cli/cli/commands/agent/test_status_baseline_wiring.py
- tests/specify_cli/cli/commands/agent/test_tasks.py
- tests/specify_cli/cli/commands/agent/test_tasks_backward_emit.py
- tests/specify_cli/cli/commands/agent/test_tasks_canonical_cleanup.py
- tests/specify_cli/cli/commands/agent/test_tasks_cli_contract.py
- tests/specify_cli/cli/commands/agent/test_tasks_cli_contract_coord.py
- tests/specify_cli/cli/commands/agent/test_tasks_core_backed_orchestration.py
- tests/specify_cli/cli/commands/agent/test_tasks_dependency_readiness.py
- tests/specify_cli/cli/commands/agent/test_tasks_json_bytes.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_cli_4899.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_gate_observability.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_pre_review_identity_read.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py
- tests/specify_cli/cli/commands/agent/test_tasks_parsing_validation.py
- tests/specify_cli/cli/commands/agent/test_tasks_planning_artifact_lifecycle.py
- tests/specify_cli/cli/commands/agent/test_tasks_status_committed_authority.py
- tests/specify_cli/cli/commands/agent/test_tasks_status_progress.py
- tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py
- tests/specify_cli/cli/commands/agent/test_verdict_attribution_4670.py
- tests/specify_cli/cli/commands/agent/test_workflow.py
- tests/specify_cli/cli/commands/agent/test_workflow_canonical_cleanup.py
- tests/specify_cli/cli/commands/agent/test_wrapper_delegation.py
- tests/specify_cli/cli/commands/review/test_lane_gate_no_artifact_rendering.py
- tests/specify_cli/cli/commands/test_accept_clean_tree.py
- tests/specify_cli/cli/commands/test_accept_guidance_liveness.py
- tests/specify_cli/cli/commands/test_accept_merge_commit.py
- tests/specify_cli/cli/commands/test_accept_normalize_encoding.py
- tests/specify_cli/cli/commands/test_accept_readiness_no_write.py
- tests/specify_cli/cli/commands/test_implement_claim.py
- tests/specify_cli/cli/commands/test_materialize.py
- tests/specify_cli/cli/commands/test_merge.py
- tests/specify_cli/cli/commands/test_tasks_move_task_cwd.py
- tests/specify_cli/cli/commands/test_workspace_husk_resolution_1833.py
- tests/specify_cli/consolidation/test_done_evidence_snapshot.py
- tests/specify_cli/core/test_dependency_graph_canceled.py
- tests/specify_cli/core/test_stale_sweep_snapshot.py
- tests/specify_cli/integration/test_migration_e2e.py
- tests/specify_cli/migration/test_normalize_mission_lifecycle.py
- tests/specify_cli/next/test_runtime_bridge_composition.py
- tests/specify_cli/review/test_arbiter.py
- tests/specify_cli/status/test_lane_uninitialized.py
- tests/specify_cli/status/test_lifecycle.py
- tests/specify_cli/status/test_post_mission_lifecycle_events.py
- tests/specify_cli/status/test_progress.py
- tests/specify_cli/status/test_progress_integration.py
- tests/specify_cli/status/test_reconstruct_wp_view.py
- tests/specify_cli/test_accept_gate_convergence.py
- tests/specify_cli/test_accept_no_commit_readonly.py
- tests/specify_cli/test_acceptable_ending.py
- tests/specify_cli/test_acceptance.py
- tests/specify_cli/test_acceptance_regressions.py
- tests/specify_cli/test_canonical_acceptance.py
- tests/specify_cli/test_runtime_hard_fail.py
- tests/specify_cli/test_terminal_state_gate_integrity.py
- tests/status/conftest.py
- tests/status/test_cutover_eligibility.py
- tests/status/test_dependency_guard.py
- tests/status/test_derived_view_slug_traversal.py
- tests/status/test_diffcov_2684_runtime_state_gaps.py
- tests/status/test_emit.py
- tests/status/test_reducer.py
- tests/status/test_render_parity_golden.py
- tests/status/test_review_claim_role_aware.py
- tests/status/test_snapshot_schema_version.py
- tests/status/test_work_package_lifecycle.py
- tests/tasks/test_move_task_git_validation_unit.py
- tests/tasks/test_pre_commit_wp_guard_unit.py
- tests/tasks/test_tasks_2x_unit.py
- tests/upgrade/migrations/test_m_3_2_0a4_normalize_mission_lifecycle.py
- tests/utils.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Test seeding helper and codemod (tidy-first)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter, and follow its guidance before reading the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

If this WP was returned from review, the feedback reference is in the event log (`spec-kitty agent tasks status --mission event-write-hygiene-01M5HS55`). Address every item, and record what you changed with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

- **New helper**: add `tests/_support/status_seed.py`, a test-only helper that seeds `status.events.jsonl` through the production **atomic** primitive.
- **Codemod**: move every test off `specify_cli.status.store.append_event` (the plain, non-atomic door that WP02 deletes) and onto that helper. The census counts 189 files and 382 call sites, plus one identity spy.
- **Exception**: `tests/specify_cli/test_locked_frontmatter_writers.py:524` tests the door's in-place notify behaviour. WP02 owns it. Do not codemod it.
- **Exception**: the door's own tests stay untouched, because WP02 deletes them together with the door. Those are `tests/status/test_store.py` and `tests/specify_cli/status/test_store_sanitized.py`.
- **Done when**: `rg -n "\bappend_event\b" tests` matches only:
  - `tests/status/test_store.py` and `tests/specify_cli/status/test_store_sanitized.py`;
  - the architectural gate files `tests/architectural/test_status_unsafe_allowlist.py` and `tests/architectural/test_status_events_writes_gate.py`, which WP02 handles;
  - unrelated `append_event` names: `glossary.events.append_event`, `spec_kitty_events.persistence.append_event`, `BookkeepingTransaction.append_event` (a method call, `.append_event(`) and the runtime engine's `_append_event`.
- Every codemodded file passes with its assertions unchanged (SC-004). No `src/` file changes.

## Context & Constraints

- **References**:
  - spec: `kitty-specs/event-write-hygiene-01M5HS55/spec.md` (FR-004, NFR-001, SC-004);
  - plan: `plan.md` (IC-01 and Engineering Alignment);
  - census: `research-census.md` (sections 1–2 list every import shape and call site);
  - `research.md` R-3 (semantic differences).
- Charter: tidy-first campsite step (Standing Order 2). Behaviour-preserving. No `# noqa` or `# type: ignore` additions.
- **Semantic differences, accepted and documented**: the atomic path differs from the deleted door in three ways. The census found no test that relies on any of them.
  - It adds a trailing newline to an existing file that lacks one.
  - It refuses a symlinked log.
  - It replaces the inode, and the new file has mode 0600.
- **Durability-matrix caution**: `tests/integration/test_review_durability_matrix.py` (around line 1812) runs a worker that blocks on the first `os.replace` of the log. Do not add seeding inside that blocked context. Codemod only the seeds that run before it.

## Branch Strategy

- **Strategy**: single_branch. Work in the repository root checkout on `feat/event-write-hygiene`.
- **Planning base branch**: `feat/event-write-hygiene`
- **Merge target branch**: `feat/event-write-hygiene`

These fields are populated by `spec-kitty agent mission finalize-tasks`. Run `spec-kitty agent action implement WP01 --agent claude --mission event-write-hygiene-01M5HS55`; the CLI resolves the write checkout. There is no lane worktree.

## Subtasks & Detailed Guidance

### Subtask T001 – Seeding helper and its tests

- **Purpose**: one canonical way for tests to seed status rows. It must go through the same atomic primitive production uses, so tests stop exercising a write path production never takes.
- **Steps**:
  1. Create `tests/_support/status_seed.py`:
     ```python
     """Test-only seeding of ``status.events.jsonl`` through the atomic store primitive.

     Production writes the status log only through the status FSM
     (``emit_status_transition`` / ``BookkeepingTransaction``), which persists
     through ``status.store``'s atomic primitives. Tests that need a pre-seeded
     log use this helper so fixtures take the same write path. Rows are
     serialized by ``store.serialize_event_line`` exactly as before.
     """
     from __future__ import annotations
     from collections.abc import Iterable
     from pathlib import Path
     from specify_cli.status import store
     from specify_cli.status.models import StatusEvent

     __all__ = ["seed_status_event", "seed_status_events"]

     def seed_status_events(feature_dir: Path, events: Iterable[StatusEvent]) -> None:
         """Append *events* to ``feature_dir``'s status log as one atomic write."""
         store.append_events_atomic(feature_dir, list(events))

     def seed_status_event(feature_dir: Path, event: StatusEvent) -> None:
         """Append one *event* to ``feature_dir``'s status log atomically."""
         seed_status_events(feature_dir, [event])
     ```
     Check the real import path of `StatusEvent` (the facade is `specify_cli.status`), and match the import style of the surrounding `tests/_support` modules.
  2. Add focused tests in `tests/status/test_status_seed_helper.py`:
     - (a) The bytes produced equal `"".join(store.serialize_event_line(e.to_dict()) + "\n" for e in events)` on a fresh directory (NFR-001).
     - (b) Two sequential single seeds equal one batched seed of the same two events.
     - (c) An empty batch creates no file. `append_raw_rows_atomic` returns early, so assert the path does not exist.
     - (d) The rows read back with `store.read_events` equal the inputs.
     Build realistic events with the same `StatusEvent(...)` constructor shape the existing tests use (copy one from `tests/status/conftest.py`).
- **Files**: `tests/_support/status_seed.py` (new), `tests/status/test_status_seed_helper.py` (new).
- **Validation**: `.venv/bin/python -m pytest tests/status/test_status_seed_helper.py -q`.

### Subtask T002 – Codemod module-level imports

- **Purpose**: retarget the about 150 files that import the door at module level.
- **Steps**:
  1. Write a throwaway codemod script in the scratchpad, never in the repo. Base it on `ast` plus exact line and column edits, or on `libcst` if `.venv` has it (`.venv/bin/python -c "import libcst"`).
  2. For each file in this WP's `owned_files`:
     - Find `ImportFrom` nodes whose module is `specify_cli.status.store` or `specify_cli.status._unsafe` and whose names include `append_event`. Handle the single-name, multi-name and parenthesised multi-line forms. The census confirms there are no aliased imports.
     - Remove `append_event` from that import. Drop the whole statement when no names remain. Otherwise keep the remaining names, in their original order and formatting style.
     - Add `from tests._support.status_seed import seed_status_event` after the remaining imports, in the project's import grouping. `ruff check --fix --select I` on the changed files will sort it.
     - Rewrite every `Call` whose `func` is `Name(id="append_event")` to `seed_status_event(...)`, with the arguments unchanged.
  3. Also handle module-attribute calls (`store.append_event(...)` after `from specify_cli.status import store`). Rewrite each one to `seed_status_event(...)` and add the import. If the module still uses `store` for something else, keep that import.
  4. **Do not touch**:
     - `.append_event(` method calls (`BookkeepingTransaction`);
     - `glossary`'s `append_event`;
     - `spec_kitty_events.persistence.append_event`;
     - any `append_event` defined locally in a test;
     - the two door test files.
- **Files**: the module-level importers from the census, all listed in `owned_files`.
- **Notes**: keep the diff minimal: no reformatting of untouched lines. Afterwards run `ruff format --force-exclude <changed files>`, then `ruff check <changed files>`. Several test files are on the formatter-debt ratchet, and `--force-exclude` keeps their formatting untouched.

### Subtask T003 – Function-local imports and the identity spy

- **Purpose**: the census found 45 function-local import sites in 33 files, and one spy that a naive import rewrite misses.
- **Steps**:
  1. Extend the codemod so it rewrites imports nested inside functions or fixtures. Put the replacement `from tests._support.status_seed import seed_status_event` at the same nesting level, to keep the lazy-import intent.
  2. **Identity spy**: `tests/integration/refinalize_frozen_lanes_support.py:311` checks or patches the door by object identity without importing it. Read the surrounding code first.
     - **Always delete the :311 spy line** (post-tasks review). The next line (:312) already spies `append_raw_rows_atomic`, so retargeting :311 to it, or to `_append_serialized_atomic`, would double-record `status_dirs`. Keep the :312 spy and the assertions it feeds.
     - Record the deletion in `spec-kitty agent tasks add-history WP01 --note`.
  3. Shared fixture modules cover many tests: `tests/utils.py`, `tests/_factories/coord_mission.py`, `tests/status/conftest.py` and four more listed in the census. Rewrite them carefully, and run their dependants.
- **Validation**: `rg -n "status\.store import[^\n]*\bappend_event\b|_unsafe import[^\n]*\bappend_event\b|store\.append_event\(" tests` returns only the two door test files.

### Subtask T004 – Batch multi-row seeds; run the blast radius

- **Purpose**: each atomic call rewrites and fsyncs the whole file. Loops that seed many rows one at a time in perf, stress or timing-tier tests can slow down.
- **Steps**:
  1. Find loops like `for ev in events: seed_status_event(d, ev)` in `tests/perf`, `tests/performance`, `tests/concurrency` and anything marked `stress` or `timing`. Rewrite them as `seed_status_events(d, events)` when the loop body only seeds. Rewrite only where order and contents stay identical.
  2. Run the codemodded files in batches, using the fast tier where it applies:
     ```bash
     PWHEADLESS=1 .venv/bin/python -m pytest <files> -q -p no:cacheprovider -n auto --dist loadfile
     ```
     Do NOT run `make test-full` or a bare `tests/architectural` sweep (NO_FULL_HEAVY_SUITES_IN_MISSION). For any architectural file you changed, run that file alone.
  3. Classify every red failure against the merge base before treating it as yours (see the CLAUDE.md baseline-red gotcha). A failure that also reproduces on `326d588f` is pre-existing: record it, don't fix it.
  4. Run `make test-fast` once.
- **Notes**: record commands and pass/fail counts in `spec-kitty agent tasks add-history WP01 --note`, since the PR needs them.

## Test Strategy

- Run the new helper tests (T001), every codemodded file (T004) and `make test-fast`.
- Run `.venv/bin/mypy tests/_support/status_seed.py tests/status/test_status_seed_helper.py`, then `ruff check` and `ruff format --check --force-exclude` on the changed files.

## Risks & Mitigations

- **A codemod over-matches a different `append_event`.** Rewrite only names bound by an import from `specify_cli.status.store` or `_unsafe`, or attribute calls on a `store` module object. Review `git diff --stat`, and spot-check 10 random files.
- **Hidden reliance on the plain door's semantics.** The census found none. If a test does fail, explain why in its own commit message, and make the fixture setup explicit rather than weakening the assertion.
- **Durability-matrix hang.** See Context.

## Review Guidance

- **Assertions**: confirm that no assertion changed. Only imports and call names changed, plus the spy and batching changes, each justified in history.
- **Search check**: confirm the `rg` check in T003 is clean.
- **Durability-matrix**: confirm nothing seeds inside its blocked context.
- **Quality**: confirm the helper has `__all__`, docstrings and type annotations, and that mypy and ruff are clean.

## Progress & Status

Use `spec-kitty agent tasks add-history WP01 --note "..."`, `spec-kitty agent tasks mark-status T001 --status done` and `spec-kitty agent tasks move-task WP01 --to for_review` (the CLI chooses the valid transition path).
