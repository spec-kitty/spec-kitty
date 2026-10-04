---
work_package_id: WP04
title: CLI marker-only batch and SPLIT-BY-KIND files (#5619 part 1)
dependencies: []
requirement_refs:
- FR-005
- FR-008
- C-001
- C-004
- SC-002
- NFR-003
planning_base_branch: issue-5618-regression-slice-cleanup
merge_target_branch: issue-5618-regression-slice-cleanup
branch_strategy: Planning artifacts for this mission were generated on issue-5618-regression-slice-cleanup. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5618-regression-slice-cleanup unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-regression-slice-cleanup-01M42WCF
base_commit: f98c216117b54273851815c8d9d2b95477180331
created_at: '2026-10-04T07:31:16.862252+00:00'
subtasks:
- T016
- T017
- T018
- T019
- T020
- T021
phase: Phase 1 - Ledger follow-through (#5619)
history:
- at: '2026-10-04T07:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/specify_cli/cli/commands/
create_intent:
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_cli_4899.py
- tests/architectural/test_recompile_never_regenerates_mission_src.py
execution_mode: code_change
model: sonnet
owned_files:
- tests/cli/test_auth_login_mismatch_exit.py
- tests/cli/test_auth_logout_mismatch.py
- tests/cli/test_auth_saas_target_cleanup.py
- tests/cli/test_move_task_planned_guard.py
- tests/cli/test_tasks_finalize_lanes_minting.py
- tests/specify_cli/cli/commands/agent/test_emit_review_result.py
- tests/specify_cli/cli/commands/agent/test_finalize_lane_dependency_cycle.py
- tests/specify_cli/cli/commands/agent/test_implement_compact_identity_4665.py
- tests/specify_cli/cli/commands/agent/test_issue_4593_behind_count_full_history.py
- tests/specify_cli/cli/commands/agent/test_issue_5328_refresh_fail_closed.py
- tests/specify_cli/cli/commands/agent/test_move_task_agent_persistence_3029.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_seam.py
- tests/specify_cli/cli/commands/agent/test_tasks_move_task_cli_4899.py
- tests/specify_cli/cli/commands/agent/test_tasks_transition_core.py
- tests/specify_cli/cli/commands/charter/test_charter_write_root_4785.py
- tests/specify_cli/cli/commands/charter/test_recompile_preserves_mission_4908.py
- tests/specify_cli/cli/commands/test_accept_guard.py
- tests/specify_cli/cli/commands/test_cli_boundary_mission_types.py
- tests/specify_cli/cli/commands/test_cli_boundary_remaining_callers.py
- tests/specify_cli/cli/commands/test_decision.py
- tests/specify_cli/cli/commands/test_doctor_flatten_remote_reverify_4979.py
- tests/specify_cli/cli/commands/test_issue_matrix_not_applicable.py
- tests/specify_cli/cli/commands/test_move_task_flag_aliases.py
- tests/specify_cli/cli/commands/test_workflow_guard.py
- tests/architectural/test_recompile_never_regenerates_mission_src.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – CLI marker-only batch and SPLIT-BY-KIND files (#5619 part 1)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission regression-slice-cleanup-01M42WCF`). All feedback items must be addressed before the work is complete.

---

## Objectives & Success Criteria

- **Goal**: Remove the `regression` mislabel from CLI unit/component/contract tests and split mixed files, per the #5619 ledger.
- **Independent test**: `--collect-only -m regression` over the owned files selects only the ledger KEEP pins; the 4 AST pins of `test_auth_saas_target_cleanup.py` are retired with planted break B re-proved.
- **Issue**: #5619 — read the full issue body (ledger + planted-break table) before starting: `https://github.com/spec-kitty/spec-kitty/issues/5619`.
- Every removal (RETIRE, trimmed SHIFT-LEFT test, retired AST pin) has a planted-break record with a RED covering guard.

## Context & Constraints

- Spec: `kitty-specs/regression-slice-cleanup-01M42WCF/spec.md`; plan: `.../plan.md`; research: `.../research.md` (R-02 marker routing, R-03 planted breaks in worktrees).
- Charter: `.kittify/charter/charter.md` — Standing Order #4 (judge the test; red-first; never retry-to-green), `NO_FULL_HEAVY_SUITES_IN_MISSION`.
- Procedure: `packs/internal/procedures/test-suite-quality-assessment.procedure.yaml` (step: verify each fix/retirement with a planted break); built-in `test-desiderata-and-boundaries` and `testing-principles` styleguides; `development-assist-test-cleanup` procedure.
- `tests/regression/README.md` — what `regression` means and the exit rule for green pins.
- Ledger rows may be stale against current `main`: apply the verdict's intent to the file's current shape and record any deviation.

## Branch Strategy

- **Strategy**: lanes (execution worktree per computed lane from `lanes.json`)
- **Planning base branch**: `issue-5618-regression-slice-cleanup`
- **Merge target branch**: `issue-5618-regression-slice-cleanup`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implement command: `spec-kitty agent action implement WP04 --agent claude --mission regression-slice-cleanup-01M42WCF`

## Shared Protocol (binding for every subtask in this WP)

### Planted-break protocol (RETIRE / SHIFT-LEFT / FIX evidence — FR-008, C-005)

1. Work in this WP's lane worktree. Edit the named product file under `src/` to disable
   exactly the behaviour the guard names (the issue ledger names the edit; reproduce it).
2. Run ONLY the named guard files:
   `uv run --frozen pytest <guard files> -q -p no:randomly` — pytest's `pythonpath = src`
   makes the worktree's `src/` win for in-process tests. For tests that shell out to the
   `spec-kitty` CLI or `python -m specify_cli`, prefix `PYTHONPATH=$PWD/src`.
3. Record `N failed / M passed` (RED is required for a removal).
4. Revert: `git checkout -- src/` and confirm `git status --short src/` prints nothing.
   **A planted break is never committed.**
5. If the guard stays GREEN, the verdict flips to KEEP (or FIX): keep the test and say so.
6. Append one row per break to the WP's Activity Log and to the evidence file named in
   the WP (format: `| id | product edit | guard files | result | reverted |`).

### Marker edits

- MARKER-ONLY: remove `regression` (module `pytestmark` entry or decorator). Keep the
  tier markers (`fast`, `unit`, `integration`, `git_repo`, ...). If the test is left with
  no tier marker, add the marker its siblings in the same directory use.
- SPLIT-BY-KIND: move the marker from module level onto only the ledger-named tests
  (decorator), or split those tests into a sibling file — prefer the decorator unless the
  ledger says "split the file".
- Rewrite stale docstrings that call a green test "red-first" / "stays red on main": per
  `tests/regression/README.md` exit rule, say the defect is fixed and the test is a
  permanent guard; keep the issue number as history.
- Never touch `p0_repro` (C-003).

### Validation (run before handing to review)

```bash
uv run --frozen pytest <every file you touched> -q                 # record counts
uv run --frozen pytest <touched files> -q --durations=0 | tail -15  # before and after timing
uv run --frozen ruff check <touched files>
uv run --frozen ruff format --check --force-exclude <touched files>
uv run --frozen pytest <touched files> -m regression --collect-only -q | tail -1
```

Run the marker gates once at the end of the WP:
`uv run --frozen pytest tests/architectural/test_marker_job_completeness.py tests/architectural/test_fast_tier_marker_completeness.py -q`.
Never run `make test-full` or whole heavy directories (C-002). If a test is red on
`origin/main` too, it is baseline: note it, do not fix it.

### Commits

- Conventional Commits, type `test` (e.g. `test(status): ...`). One logical change per commit;
  seam tests land in a commit BEFORE the commit that trims the slow test.
- Every commit message ends with the trailer
  `Co-Authored-By: Stijn Dejongh <stijn.dejongh@sddevelopment.be>`.
- No AI model identifiers in commit messages.
- Product code under `src/` is never changed (C-001). If a test exposes a real product
  defect, stop and report it; it becomes a filed issue, not a fix here.


## Subtasks & Detailed Guidance

### Subtask T016 – MARKER-ONLY batch
Drop `regression` (keep/add tier markers) on: `tests/cli/test_auth_login_mismatch_exit.py`, `tests/cli/test_auth_logout_mismatch.py`, `tests/cli/test_move_task_planned_guard.py`, `agent/test_finalize_lane_dependency_cycle.py`, `agent/test_issue_4593_behind_count_full_history.py`, `agent/test_issue_5328_refresh_fail_closed.py`, `agent/test_move_task_agent_persistence_3029.py`, `agent/test_tasks_transition_core.py` (pure unit, sole guard per break H — keep the test), `charter/test_charter_write_root_4785.py` (break C proves it is a real oracle — keep, unmark), `test_cli_boundary_mission_types.py`, `test_cli_boundary_remaining_callers.py`, `test_decision.py`, `test_doctor_flatten_remote_reverify_4979.py`, `test_issue_matrix_not_applicable.py`, `test_move_task_flag_aliases.py`, `test_workflow_guard.py`; and the malformed-JSON test only in `agent/test_emit_review_result.py`. (`agent/` = `tests/specify_cli/cli/commands/agent/`, unprefixed = `tests/specify_cli/cli/commands/`.)

### Subtask T017 – Fix wrong tier co-marks on KEEP files
- `agent/test_implement_compact_identity_4665.py`: the `fast` co-mark is wrong (it is not fast-tier) — remove `fast`, keep `regression`, keep/add the correct tier (`integration`/`git_repo` per what it does).
- `test_accept_guard.py`: the `unit` co-mark is wrong — remove `unit`, keep `regression`.
- `tests/cli/test_tasks_finalize_lanes_minting.py`: KEEP, add the missing tier marker.
- Check `tests/architectural/test_fast_tier_marker_completeness.py` stays green.

### Subtask T018 – SPLIT-BY-KIND `test_auth_saas_target_cleanup.py`
- 11 tests: 4 AST pins (shape-only; break A reds only the AST pin, break B leaves all 11 green while `tests/cli/commands/test_auth_status.py` goes red), 7 behaviour units.
- Planted break **P-5619-B**: make `format_saas_mismatch_warning` compare raw strings (no normalisation); confirm `tests/cli/commands/test_auth_status.py` RED (2) and all 11 here GREEN. Revert.
- Retire the 4 AST pins (covering guard: `tests/cli/commands/test_auth_status.py`); unmark the 7 behaviour tests.

### Subtask T019 – SPLIT-BY-KIND `test_tasks_move_task_seam.py`
- Move the 3 #4899 CLI classes into new `tests/specify_cli/cli/commands/agent/test_tasks_move_task_cli_4899.py` (they keep `regression` + their tier marker); the `_MOVE_SET` battery stays in the seam file, unmarked.
- Check the pr-landing gotcha: the seam file's `_MOVE_SET` pin must not change; grep the repo for registries listing the seam file name (`git grep test_tasks_move_task_seam`) and add the new file where needed.

### Subtask T020 – SPLIT-BY-KIND `charter/test_recompile_preserves_mission_4908.py`
- 23 collected (ledger says 19): 1 e2e keeps `regression`; the reader units are unmarked; the src-grep test moves to new `tests/architectural/test_recompile_never_regenerates_mission_src.py` with `pytestmark = pytest.mark.architectural` (copy the grep test verbatim, then delete it from the source file).
- Run `tests/architectural/test_marker_job_completeness.py` after.

### Subtask T021 – Validate and record evidence
- Run the Validation block over all owned files; record the per-file `-m regression` before/after and P-5619-B.

## Risks & Mitigations

- A planted break left in `src/` → C-005 violation: run `git status --short src/` before every commit.
- A covering guard that stays green → the slower test is the last guard: keep it (verdict flips to KEEP).
- Removing a marker can drop a test out of every CI selection only if no tier marker remains: run the marker gates.

## Review Guidance

- Re-run at least one planted break per removal family yourself and confirm RED; confirm `git diff --stat origin/main -- src/` is empty.
- Check each removed test maps to a recorded RED guard; check each MARKER-ONLY file keeps a tier marker.
- Confirm seam tests landed in an earlier commit than the trims.

## Activity Log

- 2026-10-04T07:40:00Z – system – Prompt created.
