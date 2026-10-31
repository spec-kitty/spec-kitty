---
work_package_id: WP01
title: Red-first regression for the stale consolidation baseline
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6770-consolidate-rerun-fresh-baseline
merge_target_branch: issue-6770-consolidate-rerun-fresh-baseline
branch_strategy: Planning artifacts for this mission were generated on issue-6770-consolidate-rerun-fresh-baseline. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6770-consolidate-rerun-fresh-baseline unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Red
history:
- at: '2026-10-30T23:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/terminus/
create_intent:
- tests/terminus/test_repro_6770.py
execution_mode: code_change
model: ''
owned_files:
- tests/terminus/test_repro_6770.py
- tests/terminus/test_rollback_door.py
- tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Red-first regression for the stale consolidation baseline

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
(or any user-defined profile), and behave according to its guidance before parsing the rest of
this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log
  (`spec-kitty agent tasks status`).
- Address every item before declaring the WP done, and record what changed with
  `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

Deliver the executable proof of #6770 **before** any product change, and flip the two existing
tests that currently pin the opposite behaviour. When this WP is done:

- `tests/terminus/test_repro_6770.py` exists, is collected, and **fails** on the un-fixed tree
  for the reason the issue reports.
- `tests/terminus/test_rollback_door.py` and
  `tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py` assert the
  post-fix expectation ("a fully rolled-back run leaves no record; the re-run starts fresh and
  still reaches done") and therefore fail on the un-fixed tree too.
- The red run (command plus the exact assertion lines) is recorded in this WP's history and in
  the mission tracer files.

Acceptance: SC-001, SC-002, SC-003 (as failing assertions now, green after WP02).

## Context & Constraints

Read first:

- `kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/spec.md` — user stories, edge cases.
- `kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/research.md` — the reproduction this
  test formalises, and the code chain that causes it.
- `kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/plan.md` — IC-02.

The production chain under test (read it, do not re-derive it):

- `src/specify_cli/consolidation/executor.py::_report_rollback` — the single post-mutation
  rollback door (#5385). Prints `RollbackReport.render()` and re-raises.
- `src/specify_cli/consolidation/rollback.py::rollback_to_snapshot` /
  `_clear_bookkeeping` — a full restore empties per-attempt progress but leaves the record file.
- `src/specify_cli/consolidation/resolve.py::_load_or_create_merge_state` — any existing record
  is loaded as a resume (`is_resume=True`).
- `src/specify_cli/consolidation/phase_claim.py::_resolve_pre_mutation_target_sha` —
  read-persisted-first; it is the reconciliation window base.
- `src/specify_cli/cli/commands/consolidate.py::_dispatch_abort` + `_abort_restore_or_keep_record`
  — a target tip the record cannot explain is `NOT_RESTORED`, so the abort keeps the record and
  exits 1.

Constraints:

- Real git, real CLI, no mocks of git or of the fixtures (charter, ATDD-first). The only patch
  allowed is the one-shot reconciliation FAIL and the assertion spy.
- Do not weaken any existing assertion while re-pinning: keep the "every branch restored",
  "clean checkout", "content gone" and "re-run reaches done" assertions exactly as they are.

## Branch Strategy

- **Strategy**: single_branch on `issue-6770-consolidate-rerun-fresh-baseline`
- **Planning base branch**: `issue-6770-consolidate-rerun-fresh-baseline`
- **Merge target branch**: `issue-6770-consolidate-rerun-fresh-baseline`

Execution worktrees are allocated per computed lane from `lanes.json` by
`spec-kitty agent action implement WP01 --agent claude --mission consolidate-rerun-fresh-baseline`.

## Subtasks & Detailed Guidance

### Subtask T001 – Author `tests/terminus/test_repro_6770.py` (the regression)

- **Purpose**: turn the reported scenario into an executable assertion, on real git.
- **Steps**:
  1. Module docstring: the #6770 shape, the #5667 recurrence it re-opens, and the two
     consequences (stale window base, wedged `--abort`). Note the red-first expectation and the
     command that shows it.
  2. Fixture: `build_lanes_mission(tmp_path, wps=("WP01", "WP02"), target_branch="develop", mid8="01M6770A")`
     (a LANES mission keeps the fixture cheap and has no coordination branch to reason about).
  3. Attempt 1: `_consolidate(mission, monkeypatch)` (copy the helper shape from
     `tests/terminus/test_rollback_door.py`) with `MergeOutcomeVerifier.verify` patched to
     return `VerifyResult.failed(Divergence(missing_approved=(("WP01", "a" * 40),)))` on its
     **first** call only, delegating to the real method afterwards. Expect `typer.Exit`.
  4. Precondition assertions (true before AND after the fix): `ref_shas(mission)` is unchanged
     by the failed attempt and the target is back at `T0`; `git status --porcelain` in the
     repository root checkout is clean. Do **not** assert that the record still exists — that is
     the defect, and the test must pin its absence instead (step 7).
  5. Commit on the target between attempts: write `TEAM.md`, `git add`, `git commit` in
     `mission.repo` (the root checkout is on the target; assert that first, like
     `test_rollback_door._commit_on_target`). Capture `T1 = rev-parse HEAD`.
  6. Wrap `specify_cli.consolidation.phase_claim.build_approved_wp_set` to append
     `kwargs["excluded_window_base"]` to a list and delegate; run attempt 2 with the real gate.
  7. Post-fix expectations (these are what must be asserted; they fail on the un-fixed tree):
     - the record is gone after attempt 1 →
       `assert state_path(mission) is None`
     - attempt 2 exits cleanly (no exception) and `captured_window_base == T1`
     - `T1` is an ancestor of the target (`git merge-base --is-ancestor T1 <target>`), and both
       WPs' files are on the target (`blob_present_at`)
- **Files**: `tests/terminus/test_repro_6770.py` (new).
- **Parallel?**: no.
- **Notes**: `pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]`.

### Subtask T002 – The plain `--abort` half of the regression

- **Purpose**: pin the wedged-recovery symptom the issue reports.
- **Steps**: in the same file, a second test on the same fixture: run attempt 1 (one-shot FAIL),
  then `run_terminus(mission, ["consolidate", "--mission", mission.slug, "--abort"])` and assert
  `returncode == 0` and that the collapsed output names no active merge state
  (`rollback_harness.flat`). On the un-fixed tree this returns 1 with
  "Kept the consolidation record ...".
- **Files**: `tests/terminus/test_repro_6770.py`.
- **Notes**: use an explicit `--mission` so the abort cannot adopt a slug from state.

### Subtask T003 – Re-pin `test_record_is_truthful_after_rollback_and_a_rerun_succeeds`

- **Purpose**: the existing assertion ("a fully-rolled-back run keeps its record for a resume")
  pins the behaviour this Mission changes.
- **Steps**: in `tests/terminus/test_rollback_door.py`, replace the
  `assert record is not None` / `record["completed_wps"] == []` / `mission_number_baked is False`
  block with: `assert _record(mission) is None` and a one-line docstring/comment explaining the
  new rule (a record survives only while some of its attempt is on the target). Keep the
  "precondition: the failed run was fully rolled back" assertion and the re-run half (both lanes
  land) untouched. Rename the test only if the name would otherwise lie.
- **Files**: `tests/terminus/test_rollback_door.py`.
- **Notes**: do not delete the test; it is the re-run positive control for the fix.

### Subtask T004 – Re-pin `_assert_failed_run_restored_the_snapshot`

- **Purpose**: same pinned behaviour in the CLI-level coord-worktree test.
- **Steps**: in `tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py`,
  replace the `load_state(...) is not None` block with an assertion that the record is gone, and
  update the surrounding docstrings ("kept record resumes from the snapshot" → "cleared record
  makes the re-run fresh"). Keep every rollback/restore assertion above it.
- **Files**: `tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py`.
- **Notes**: two tests call this helper; both must still prove the re-run reaches `done`.

### Subtask T005 – Record the red run

- **Purpose**: evidence, not narrative.
- **Steps**: run
  `uv run pytest tests/terminus/test_repro_6770.py tests/terminus/test_rollback_door.py tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py -x -q`
  on the un-fixed tree, keep the exact assertion lines, then:
  `spec-kitty agent tasks add-history WP01 --note "<command> => <n> failed, <n> passed; <first failure line>"`.
  Append one line each to the mission's tracer files with
  `spec-kitty agent tracer-append --mission consolidate-rerun-fresh-baseline --category approach --entry "..."`.
- **Notes**: no `xfail`, no `skip`, no weakening to make the red suite green.

## Test Strategy

- New file: `tests/terminus/test_repro_6770.py` (integration + git_repo + regression).
- Re-pinned: `tests/terminus/test_rollback_door.py`,
  `tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py`.
- Command:
  `uv run pytest tests/terminus/test_repro_6770.py tests/terminus/test_rollback_door.py tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py -x -q`
- No compiler gate applies to test-only Python beyond `mypy` being repo-wide; keep annotations
  on every helper (`from __future__ import annotations`).

## Risks & Mitigations

- **Patching the verifier for good would make attempt 2 vacuous** — fail once, delegate after.
- **Fixture drift**: reuse `build_lanes_mission` + `run_terminus` rather than a new builder.
- **Slow fixture**: the LANES builder is the cheapest real one (~30s setup); do not add WP03/WP04.

## Review Guidance

- Does the new test fail on the un-fixed tree for the reported reason (not a fixture error)?
- Is the window-base assertion on the production path (`build_approved_wp_set`), not on a
  helper-only proxy?
- Do the two re-pins keep every other assertion, and is the new expectation stated in a
  docstring a future reader can check against `spec.md`?

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) — never in this
file. Use `spec-kitty agent tasks add-history WP01 --note "..."` and
`spec-kitty agent tasks move-task WP01 --to <status>`.
