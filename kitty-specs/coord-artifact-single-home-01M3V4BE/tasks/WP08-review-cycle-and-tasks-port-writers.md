---
work_package_id: WP08
title: 'Review-cycle, mark-status and map-requirements: write location and outcomes'
dependencies:
- WP07
- WP19
requirement_refs:
- FR-003
- FR-007
- SC-003
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
subtasks:
- T043
- T044
- T045
- T046
- T047
phase: Phase 3 - Writer migration
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
agent: claude
authoritative_surface: src/specify_cli/review/cycle.py
create_intent:
- tests/review/test_cycle_write_dir.py
- tests/specify_cli/cli/commands/agent/test_tasks_port_commit_outcome.py
- tests/specify_cli/cli/commands/agent/test_review_reject_fix_mode_coord.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/review/cycle.py
- src/specify_cli/cli/commands/agent/tasks_mark_status.py
- src/specify_cli/cli/commands/agent/tasks_map_requirements.py
- tests/review/test_cycle_write_dir.py
- tests/specify_cli/cli/commands/agent/test_tasks_port_commit_outcome.py
- tests/coordination/test_analysis_report_rehome.py
- src/specify_cli/cli/commands/agent/workflow.py
- src/specify_cli/cli/commands/agent/workflow_cores.py
- src/specify_cli/cli/commands/agent/workflow_executor.py
- tests/specify_cli/cli/commands/agent/test_review_reject_fix_mode_coord.py
- src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py
- tests/specify_cli/review/test_cycle_kind_flip.py
- tests/specify_cli/test_read_seam_leniency.py
- tests/specify_cli/test_owned_history_support.py
- tests/architectural/untrusted_path_audit/inventory.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
assignee: ''
shell_pid: ''
---

# Work Package Prompt: WP08 – Review-cycle, mark-status and map-requirements: write location and outcomes

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Finish the tasks-port writer family. Review-cycle records and mark-status status events must be written **in place** on their owning surface, through `PlacementSeam.write_dir`. Each tasks-port consumer must render the per-surface commit outcome that WP07 now carries on `CommitArtifactResult.surfaces`.

Done means:

- On a coordination-routed Mission, a rejection (`spec-kitty agent tasks move-task WPxx --to planned --review-feedback-file <f>`) writes `tasks/<wp>/review-cycle-N.md` directly into the coordination worktree at `write_dir(REVIEW_CYCLE).path`. It is committed in place on the coordination branch, and the repository root checkout keeps **no** copy or residue (spec edge case "Transient staging").
- The mark-status status-event write location is `write_dir(STATUS_STATE)`. Reads keep their read resolver.
- `review/cycle.py:712` and `tasks_map_requirements.py:668` render outcomes (the dead `tasks_mark_status.py:279` shim is out of scope; round 3) through WP05's `render_commit_outcome` / `commit_outcome_payload`, and apply the shared exit-code rule where the command decides an exit code. A skipped or refused surface is never masked (FR-007, SC-003).
- `lanes` / `single_branch` Missions behave as before (C-008).

## Context & Constraints

- **Spec**: FR-003 (writer families "review-cycle", "status transitions: … mark-status"), FR-007 (spec rev 5: "the tasks-port commit wrapper and its committing callers: review-cycle and map-requirements"; mark-status renders nothing), SC-003, US2.1/2.2, edge case "Transient staging".
- **Plan**: IC-04 (review-cycle and mark-status writer rows), IC-07 (tasks-port consumer row).
- **Research**: grounding correction "review/cycle.py:298-303 REVIEW_CYCLE fallback" (no production caller passes `kind=REVIEW_CYCLE`; the writers use the PRIMARY `WORK_PACKAGE_TASK` dir and commit via `commit_artifact(kind=REVIEW_CYCLE)`, which is stage-in-root-then-copy), D8 (consumer list, exit-code rule, "discarded-result sites render a warning only when a surface is not committed/unchanged").
- **Contracts**: `contracts/commit-outcome.md` (rules 1-6, reason codes), `contracts/write-location-accessor.md`.
- **Upstream**: WP07 (`CommitArtifactResult.surfaces`, kind-aware `feature_write_dir`), WP05 (`commit_outcome.py`), WP03/WP04 (accessor).
- **Production entry for review-cycle writes (verified)**: `spec-kitty agent tasks move-task <WP> --to planned --review-feedback-file <path>` → `cli/commands/agent/tasks_verdict_persistence.py` (imports `create_rejected_review_cycle` at ≈L89) → `review/cycle.py::create_rejected_review_cycle` (L1199) → `_review_cycle_wp_dir(...)` (≈L1271) for the directory → `_commit_review_cycle_artifact` (L674) → `commit_router.commit_artifact(..., kind=REVIEW_CYCLE)` at L712. A second caller is `tasks_materialization.py:230-233`. The arbiter *reads* via `_review_cycle_wp_dir` (`review/arbiter.py:31, 415`).
- **Read this before touching `_review_cycle_wp_dir`**: its docstring (review/cycle.py:173-306) records why the write-side default was NOT flipped before. `tests/coordination/test_analysis_report_rehome.py::test_review_cycle_authored_lands_on_coord_ref_and_is_absent_on_primary` (L149) pins the PHYSICAL write to the PRIMARY working tree. It also names three "unrouted sites" to re-verify in the same change: `workflow.py::review`, `workflow_cores.py::has_prior_rejection`, `workflow_executor.py::implement_try_render_fix_mode_prompt`. This WP is that follow-up: the Mission's single-home rule now owns it.
- Load the charter and `spec-kitty charter context --action implement --json`.
- **Model discipline**: implement with sonnet (`claude-sonnet-5`); review with opus.
- **Terminology**: "Mission", never "feature". Name each sense of "primary" (PRIMARY partition, repository root checkout, target branch).
- **Fixture semantics across lanes (post-tasks squad P-m5):** pre-fix assertions use WP02's `make_prefix_coord_mission`; `make_coord_mission` carries only shape-agnostic invariants (its shape changes when WP06 lands); use `make_coord_mission(..., materialized=True)` when a test needs a deterministic MATERIALIZED coordination surface in every lane.
- **Brownfield scout (binding read)**: before coding, read `## WP08` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp01-11.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- `finalize-tasks` allocates execution worktrees per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP08 --agent claude`, and use the printed workspace path.
- **Lane notes (updated by the post-tasks squad)**: this WP shares `cli/commands/agent/workflow.py` with WP19 (R-M3: it may fix the reject→fix-mode readers). It depends on WP19 and WP07, so it runs after WP19 in WP19's lane, and its base also stacks WP07's lane. It owns and re-pins `tests/coordination/test_analysis_report_rehome.py` (P-m3).

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T043 – Red-first: in-place review-cycle and mark-status writes, unmasked outcomes

- **Purpose**: Pin the contract through the pre-existing CLI entry points before changing code (charter ATDD-First, C-005). Commit separately, first.
- **Steps**:
  1. `tests/review/test_cycle_write_dir.py` (new). Use WP02's `make_coord_mission` (parametrize `coord`, `lanes_with_coord`) with a finalized WP that has reached `for_review` / `in_review`. Reuse the existing rejection fixtures: `grep -rl "review-feedback-file\|create_rejected_review_cycle" tests/ | head` shows how other tests reach a rejectable state.
  2. Run `spec-kitty agent tasks move-task WP01 --to planned --review-feedback-file <tmp>/feedback.md --mission <slug> --json` (CliRunner or subprocess). Assert:
     - `git show <coordination_branch>:kitty-specs/<dir>/tasks/<wp-slug>/review-cycle-1.md` equals the bytes written in the coordination worktree;
     - the file exists under `<coord wt>/kitty-specs/<dir>/tasks/<wp-slug>/`;
     - **no** `review-cycle-*.md` exists under the repository root checkout's `kitty-specs/<dir>/tasks/<wp-slug>/`, and `git status --porcelain -- kitty-specs/<dir>` in the root checkout is empty (no transient-staging residue);
     - the target branch history (`git log <creation_base>..<target> -- '*review-cycle-*'`) is empty.
  3. Mark-status: run `spec-kitty agent tasks mark-status T001 --status done --mission <slug> --json` on a pre-fix EMPTY Mission (`make_prefix_coord_mission(worktree="empty")`). The subtask-state event lands in the coordination log after the carried creation events, the lamport continues, and the root log gains nothing.
  4. Masking (red at base): drive `_commit_review_cycle_artifact` with a fake `CoordCommitRouter` whose `commit_artifact` returns a `CommitArtifactResult` with `surfaces=(primary committed, coordination refused STATUS_LOCK_HELD)`. The rendered output or returned outcome must name the refused surface and reason. At base the refused surface is invisible.
  5. Run on the lane base and confirm the failures are the defect (root write, residue, masked surface). Record the output.
- **Files**: `tests/review/test_cycle_write_dir.py`, `tests/specify_cli/cli/commands/agent/test_tasks_port_commit_outcome.py` (masking tests for the three consumers).
- **Edge cases**: the rejection flow holds `feature_status_lock` around allocation (`_allocate_and_write_review_cycle_while_locked`, ≈L878). Your fixture must not hold it. The `in_queue` lock timeout helper (≈L913) reads an env/config. Keep the default.

### Subtask T044 – `review/cycle.py`: write review cycles at `write_dir(REVIEW_CYCLE)`

- **Purpose**: Today `create_rejected_review_cycle` gets its directory from `_review_cycle_wp_dir(..., kind=WORK_PACKAGE_TASK)` (PRIMARY, L306). It writes into the repository root checkout, and `commit_artifact(kind=REVIEW_CYCLE)` stages that content onto the coordination branch: stage-in-root-then-copy. Move the physical write to the owning surface.
- **Steps**:
  1. Read the full docstring at L173-306 and the REVIEW_CYCLE branch at L286-303.
  2. Add a writer-side resolution. In `create_rejected_review_cycle` (≈L1271), compute the sub-artifact dir as `placement_seam(main_repo_root, slug, owned=owned).write_dir(MissionArtifactKind.REVIEW_CYCLE).path / "tasks" / <wp_slug>` (mirror how `_review_cycle_wp_dir` composes the per-WP subdir under the Mission dir; reuse its segment validation). Two options:
     - Preferred: keep `_review_cycle_wp_dir` as the shared owner function, but give it an explicit write-side mode that resolves through `write_dir`. The arbiter's reads keep the read mode.
     - Alternative: a new private `_review_cycle_write_dir(...)` used only by the writer.
     Either way, the WP20 census scans `review/cycle.py::_review_cycle_wp_dir`. If the write moves to a new helper, note its qualname in the Activity Log so WP20 scans the right function.
  3. Readers (`arbiter.py:415`, `resolve_review_cycle_pointer` ≈L491, the verdict readers) keep resolving through read resolvers. On a MATERIALIZED coordination surface they read the coordination copy, which is where the file now lives. Verify `tests/review/test_arbiter_coord_root.py` and `tests/coordination/test_verdict_dir_co_resolution.py` stay green.
  4. `_commit_review_cycle_artifact` (L674-760): `artifact_path` is now a coordination-worktree path, so `commit_artifact` commits it in place (commit_router in-place branch). Keep the durability read-back (`git show <placement-ref>:<evidence-ref>`). `_evidence_ref(operation_root, artifact_path)` (≈L803) must compute the Mission-relative ref from a coordination-worktree path. Check whether it relativizes against `operation_root` (the repository root checkout) and fix it to relativize against the containing worktree. Add a test.
  5. **Re-pin** `tests/coordination/test_analysis_report_rehome.py::test_review_cycle_authored_lands_on_coord_ref_and_is_absent_on_primary`. Its "repo-root-relative physical path in the PRIMARY tree" assertion is stale under the single-home rule (Standing Order 4: stale → re-pin). Keep "lands on coord ref" and "absent on primary". Change the physical-location expectation to the coordination worktree. Log the rationale.
  6. Re-verify the three unrouted sites the docstring names (`workflow.py::review`, `workflow_cores.py::has_prior_rejection`, `workflow_executor.py::implement_try_render_fix_mode_prompt`). They must still find a prior rejection now that it lives only on the coordination surface. Add one CLI-level test that rejects and then runs the fix-mode render path (or `has_prior_rejection`). **This is BLOCKING (post-tasks squad R-M3)**: write the CLI-level reject-then-fix-mode test in `tests/specify_cli/cli/commands/agent/test_review_reject_fix_mode_coord.py`. Reject via `move-task --to planned --review-feedback-file`, then run `agent action implement <WP>` and assert it renders the fix-mode prompt and that `has_prior_rejection` sees the coordination-surface review cycle. If any reader reads a hand-joined PRIMARY path, **fix it here**. This WP now owns `workflow.py`, `workflow_cores.py` and `workflow_executor.py`. `workflow.py` is shared with WP19, and this WP depends on WP19, so they run in one lane in that order.
  7. Update the docstring: the write-side flip has shipped (this Mission); remove the "cannot yet change" text.
- **Files**: `src/specify_cli/review/cycle.py`; out-of-map re-pin of `tests/coordination/test_analysis_report_rehome.py`.
- **Validation**: T043 review-cycle cases are green, no root residue, and the arbiter/verdict tests are green.
- **Edge cases**: owned checkouts (`owned=`) go through `write_dir`'s owned arm (WP04). The allocation must count existing `review-cycle-N.md` on the owning surface (the coordination worktree), or cycle numbers restart. Assert that `review-cycle-2.md` follows `-1.md` on a second rejection.

### Subtask T045 – `tasks_mark_status.py`: split read vs write location

- **Purpose**: `_ms_resolve_read_dir` (L209-237) sets `st.status_dir` from `resolve_status_surface(...).parent` for non-owned handles, and from `ports.coord.feature_write_dir(handle)` for owned ones. `st.status_dir` feeds the status-event write, so a read resolver is used as a write location (FR-014's defect class).
- **Steps**:
  1. Trace every use of `st.status_dir` (`grep -n "status_dir" src/specify_cli/cli/commands/agent/tasks_mark_status.py`). Separate the uses that *write* the event log from any that only read.
  2. For the write leg, use `ports.coord.feature_write_dir(handle)` for both owned and non-owned handles. After WP07 it returns `write_dir(STATUS_STATE).path`, which keeps the port as the single seam. If a read leg genuinely needs the read surface, keep a separate `st.status_read_dir` from the read resolver.
  3. `st.feature_dir` (TASKS_INDEX, PRIMARY via `ports.fs.planning_read_dir`) is unchanged.
  4. Keep the WP20 census qualname `_ms_resolve_read_dir`. If you rename it, record the new qualname in the Activity Log.
- **Files**: `src/specify_cli/cli/commands/agent/tasks_mark_status.py`.
- **Validation**: T043 mark-status case is green; existing mark-status tests (`grep -rl "mark-status\|mark_status" tests/ | head -20`) are green.
- **Edge cases**: the pre30 layout guard runs after resolution and must still see `st.feature_dir`. `write_dir` on a remote-only Mission refuses. Ensure the CLI renders that as an error with the hint, not a traceback.

### Subtask T046 – Render per-surface outcomes at the two live tasks-port consumers (mark-status struck; see Binding)

- **Purpose**: The consumers today read only `status` / `placement_ref` / `commit_hash` (FR-007 masking).
- **Steps**:
  1. `review/cycle.py:712`: the `VerdictPersistenceOutcome` message must include the surface outcomes. When any surface is `refused` / `error`, classify as `persistence_failed` with the named reason (exit-code rule). When the coordination group is `skipped` with `COORD_RECORD_IN_ROOT_CHECKOUT`, surface it in the message. Use `render_commit_outcome(result)` lines. Add an optional `surfaces` field to the outcome payload if one is emitted as JSON (additive).
  2. ~~`tasks_mark_status.py:279`~~ **Dropped (operator decision)**: dead `_ms_commit` shim, not reached by `_do_mark_status`. The live write path `_ms_emit_subtask_state` (L359, L406-413) gets the write-location fix instead. (Former step: replace the "Failed to auto-commit" branch with the rendered lines. `--json` callers get `commit_outcome_payload(...)` under an additive key.
  3. `tasks_map_requirements.py:668`: keep `st.commit_result_payload` for `committed`. Add `surfaces` (payload) additively, and when not committed/unchanged, print the rendered warning instead of silently skipping.
  4. No hand formatting of `SurfaceOutcome` anywhere. WP20's consumer-pin test will AST-check these three sites for `render_commit_outcome` / `commit_outcome_payload`.
- **Files**: the three owned source files.
- **Validation**: masking tests from T043 are green; JSON keys are additive only (existing keys and values unchanged; assert via snapshot of keys).

### Subtask T047 – Controls and coverage

- **Purpose**: Close the WP with controls and NFR-003 coverage.
- **Steps**:
  1. **C-008**: the same rejection on a `lanes` Mission writes the review cycle where it does today (PRIMARY dir) and commits to the same ref. Mark-status on `lanes`: same event path as before.
  2. **No residue**: after every coordination scenario, assert an empty root `git status --porcelain -- kitty-specs/<dir>`.
  3. **Second-cycle numbering** (from T044) and **owned-checkout** case (if WP02 provides an owned builder; otherwise a unit test on the owned arm with a fake seam).
  4. Unit tests for any new helper (write-mode resolution, `_evidence_ref` against a coordination worktree path).
  5. Transitional repro assertions live in these owning-module files (FR-016).
- **Files**: the two new test files.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **BLOCKER: flip `_review_cycle_wp_dir`'s default kind to `REVIEW_CYCLE` (operator decision).**
  - Readers and writers then move together: `review/cycle.py:520`, `review/arbiter.py:415`, `tasks_verdict_persistence.py:734` (the safety verdict reader), `workflow_cores.py:419`, `workflow_executor.py:1127`, and the writer at `cycle.py:1271`.
  - Moving only the writer would make rejections invisible to the readers (fail-open).
  - **Do NOT re-pin `tests/coordination/test_verdict_dir_co_resolution.py`.** It is a valid guard: its AST guard allows `kind=REVIEW_CYCLE` with exactly 3 positionals.
- **Approval leg (now owned)**: `tasks_verdict_persistence.py:880,915` (`create_rejected_review_cycle(verdict="approved")`) must land on the same surface.
- **`workflow.py::review` (L1999-2025)** hand-joins `_resolve_workflow_read_dir(kind=WORK_PACKAGE_TASK)/"tasks"/wp_slug`, `mkdir`s it, and numbers feedback with `next_review_feedback_source_path(sub_artifact_dir)`. Route it through `_review_cycle_wp_dir`. Otherwise the numbering restarts at 1 and an empty PRIMARY dir is created on every review.
- **`_evidence_ref` (L803)** relativizes against `operation_root` and yields `.worktrees/...-coord/kitty-specs/...`; the `git show <coord>:<that>` read-back then misses (`destination_readback_missing`). Relativize against `write_dir(REVIEW_CYCLE).checkout_root` (P-M3).
- **Path-dependent internals** must all receive the coordination dir: `_resolve_review_body`, the provenance guard, `_local_matching_retained_review_cycles` and cycle allocation.
- **Drop the dead `tasks_mark_status.py:279` (`_ms_commit`) shim from scope (operator decision).**
  - The live path is `_ms_emit_subtask_state` (L359). Its non-owned arm (L406-413) calls the flat `emit_inner_state_changed(st.status_dir, ...)` and **commits nothing**.
  - Fix the write location there (read/write split) and assert on the **file**, not on a branch tip.
  - The T046 consumer list becomes `review/cycle.py:712` and `tasks_map_requirements.py:668` only.
- **Output change**: `_ms_output` (L441-442) `status_events_path` / `status_snapshot_path` values change for coordination Missions. That is not additive-only; say so in the PR body.
- **C901**: `_mr_emit_output` (`tasks_map_requirements.py:688`) is at 11, so put the `surfaces` payload in a helper. `resolve_review_cycle_pointer` is at 10.
- **Stale pins (now owned; re-pin with rationale)**:
  - `tests/specify_cli/review/test_cycle_kind_flip.py::test_physical_write_home_is_primary_so_rehome_guard_stays_green` (L201-231);
  - `tests/specify_cli/test_read_seam_leniency.py::test_review_cycle_wp_dir_preserves_primary_home` (L145);
  - `tests/specify_cli/test_owned_history_support.py` (~L318-325).
  - `tests/integration/test_review_durability_matrix.py:1605` is CI-owned; run it by name only.
- **Valid guards**: `test_verdict_dir_co_resolution.py` (all), `test_cycle_kind_flip.py::test_verdict_reader_authority_is_decoupled_from_write_side_kind` (L159), `test_read_seam_leniency.py::test_review_cycle_wp_dir_stays_silent_when_coord_deleted`.
- **New path joins**: any new `/ "tasks" / wp_slug` join needs a row in `tests/architectural/untrusted_path_audit/inventory.md` (now owned) for `test_untrusted_path_containment.py`.
- **Lock ordering**: `create_rejected_review_cycle` runs under the verdict-queue lease. Confirm that the lease is not the workspace lock (I-SEED-2) and record the finding.
- **PUBLISHED case**: after consolidation `REVIEW_CYCLE` resolves to the target (WP04). Add one post-consolidation reject test.
- **Single write authority**: WP03 removed the local-head refusal; do not expect `COORD_WRITE_SURFACE_UNMATERIALIZED` for a local head.
- **I10 (round 4)**: the post-consolidation REVIEW_CYCLE write follows **research D23**. The removed local-head refusal is **D22**.

## Targeted test surface

- New: `tests/review/test_cycle_write_dir.py`, `tests/specify_cli/cli/commands/agent/test_tasks_port_commit_outcome.py`.
- Owning-module and affected tests (by file): `tests/review/test_arbiter.py`, `tests/review/test_arbiter_coord_root.py`, every `tests/review/test_*cycle*.py`, `tests/coordination/test_analysis_report_rehome.py`, `tests/coordination/test_verdict_dir_co_resolution.py`, and the mark-status / map-requirements tests (`grep -rl "tasks_mark_status\|tasks_map_requirements\|map-requirements" tests/`).
- Subsystem dirs (fast tier): `tests/review/`, `tests/specify_cli/cli/commands/agent/` (by file where slow).
- Baseline: `make test-fast`.
- Named architectural gates only: `tests/architectural/test_no_write_side_rederivation.py`, `tests/architectural/test_write_surface_placement_guard.py`, `tests/architectural/test_merge_reconciliation_class_guard.py` (review-cycle driver ruling), `tests/architectural/test_layer_rules.py`.
- Never run the bare `tests/architectural/`, any e2e or integration directory, performance or stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006). Record commands and counts in the Activity Log. Classify unexplained reds with the CLAUDE.md baseline-red gotcha before you treat them as yours.
- Post-tasks squad additions, by name: `tests/specify_cli/cli/commands/agent/test_review_reject_fix_mode_coord.py`, `tests/coordination/test_analysis_report_rehome.py`, and the existing tests of `workflow.py` / `workflow_cores.py` / `workflow_executor.py` (`tests/specify_cli/cli/commands/agent/test_workflow.py` plus `grep -rl has_prior_rejection tests/`).

## Quality gates

- Keep C901 ≤ 15 for every touched function (NFR-004). `create_rejected_review_cycle` and `_commit_review_cycle_artifact` are long, so extract helpers for the new outcome classification.
- Run `ruff check`, `ruff format --check` and `mypy --strict` on the changed files, with no new suppressions (NFR-005).
- Reach ≥ 90% coverage of new and changed lines, with a focused test per new branch or helper (NFR-003). If you add public symbols, run `tests/architectural/test_no_dead_symbols.py`.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5519 #5513

## Definition of Done

- T043 tests were committed first and RED on the lane base, with the output recorded.
- Review cycles are written in place on the owning surface with no root residue, and cycle numbering continues across rejections.
- The mark-status write location comes from the accessor (via the port).
- The three consumers render via the shared renderer, with JSON changes additive.
- `test_analysis_report_rehome.py` (now owned, post-tasks squad P-m3) is re-pinned with rationale.
- **BLOCKING**: the CLI-level reject-then-fix-mode test is green on a coordination-routed Mission, with any reader fixes made in this WP (R-M3).
- The C-008 controls are green, the quality gates are green, and commands and counts are logged.

## Risks & Mitigations

- **Fail-open verdict readers**: a reader that still joins a PRIMARY path would miss a rejection that now lives only on the coordination surface, a safety regression. Mitigate with the T044 step 6 CLI test plus `test_verdict_dir_co_resolution.py`.
- **Evidence read-back mismatch**: `_evidence_ref` relativization from a worktree path. Cover it with a unit test.
- **Merge-driver class**: `review-cycle-*.md` carries the `spec-kitty-review-cycle` driver. In-place writes don't change that. Keep `test_merge_reconciliation_class_guard.py` green.

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies red→green: the T043 tests are RED on the WP's base and GREEN on the final commit.
- Inspect the `test_analysis_report_rehome.py` re-pin. It must not weaken "absent on primary" or "lands on coord ref".
- Confirm no consumer hand-formats outcomes, and the JSON is additive.
- Confirm there is no root residue after a coordination rejection (run the CLI scenario yourself in a throwaway repo if in doubt).

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
