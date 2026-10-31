---
work_package_id: WP02
title: The rollback door clears a record it has fully undone
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- SC-004
planning_base_branch: issue-6770-consolidate-rerun-fresh-baseline
merge_target_branch: issue-6770-consolidate-rerun-fresh-baseline
branch_strategy: Planning artifacts for this mission were generated on issue-6770-consolidate-rerun-fresh-baseline. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6770-consolidate-rerun-fresh-baseline unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 2 - Fix
history:
- at: '2026-10-30T23:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/rollback.py
- src/specify_cli/consolidation/executor.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – The rollback door clears a record it has fully undone

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
  (`spec-kitty agent tasks status`). Address every item, then record what changed with
  `spec-kitty agent tasks add-history WP02 --note "..."`.

---

## Objectives & Success Criteria

Make the mission's invariant true on disk: **a consolidation record survives only while some of
its attempt is still on the target.**

- A rollback whose report says the attempt was undone clears the record — `state.json` **and**
  its post-fix marker — through `state.clear_state`.
- A rollback that left anything behind (a `NOT_RESTORED` branch, a kept verified landing, a
  missing run-movable branch) keeps the record exactly as today, so its
  `pre_mutation_target_sha` stays the honest window base.
- The door still prints its rollback report and still re-raises the original error; a failed
  clear warns and never replaces that error.
- WP01's tests go green; no other test changes behaviour.

Acceptance: FR-001, FR-002, FR-004, FR-005, NFR-001, NFR-002, C-001, C-002.

## Context & Constraints

Read first:

- `kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/spec.md` (Edge Cases and FR-004/FR-005).
- `kitty-specs/consolidate-rerun-fresh-baseline-01M67HZD/research.md` (D1–D4: why clear instead
  of re-anchor, why the abort path is left alone).
- The module docstrings of `src/specify_cli/consolidation/rollback.py` (guarantees 1–5) and
  `src/specify_cli/consolidation/executor.py::_report_rollback`.

Hard constraints:

- **C-001**: `state.clear_state` is the only owner of clearing a record. Do not `unlink`.
- **C-002**: one rollback site. Do not add a second rollback, a second door, or a new phase.
- **C-003**: do not touch `resolve._load_or_create_merge_state`, `phase_claim`, the abort path or
  the `--release-branch` flow.
- **NFR-001**: no new persisted field, no new file, no migration.
- **NFR-002**: the rollback authority's per-branch decisions are unchanged.

## Branch Strategy

- **Strategy**: single_branch on `issue-6770-consolidate-rerun-fresh-baseline`
- **Planning base branch**: `issue-6770-consolidate-rerun-fresh-baseline`
- **Merge target branch**: `issue-6770-consolidate-rerun-fresh-baseline`

Run `spec-kitty agent action implement WP02 --agent claude --mission consolidate-rerun-fresh-baseline`
— never hand-pick a base branch.

## Subtasks & Detailed Guidance

### Subtask T001 – One verdict on the report: "the attempt was undone"

- **Purpose**: answer the question once, where the rollback outcome already lives, instead of
  re-deriving "does anything remain?" at the caller.
- **Steps**:
  1. In `rollback.py`, add a read-only `RollbackReport` property (suggested name
     `left_nothing_behind`) next to `fully_restored`.
  2. Its docstring must state the rule and the counter-examples: a `refused_verified_landing`
     report keeps the record (the verified landing is still on the target); any
     `NOT_RESTORED` outcome keeps it; lane outcomes (`UNCHANGED_BY_RUN`, `LANE_MISSING`) do not
     by themselves keep it, because consolidation never moves a lane and a vanished lane is not
     restorable. Explain that "the record's `pre_mutation_target_sha` is only honest while
     attempt 1's landing is still on the target", which is why a full restore must drop it.
  3. Implement it from the existing kind sets (reuse `_OK_KINDS`/`_SETTLING_KINDS` if that keeps
     it honest; do not duplicate a new literal set of kinds if one already says it).
  4. Do **not** change `fully_restored`: the abort path depends on it.
- **Files**: `src/specify_cli/consolidation/rollback.py`.
- **Notes**: keep it a pure property — no I/O, no state mutation.

### Subtask T002 – The door clears on that verdict

- **Purpose**: deliver the behaviour at the single door, after the report the operator must see.
- **Steps**:
  1. In `executor.py::_report_rollback`, after `console.print(report.render(), markup=False)`
     and only when the new verdict holds, call
     `clear_state(run.main_repo, run.canonical_id)` (import it with the other `state` imports).
  2. Wrap the clear in the same guarded shape `phase_claim._clear_fresh_record_on_pre_mutation_exit`
     uses: catch `OSError`, `logger.warning(...)`, print a short yellow line, and never raise —
     the caller re-raises the original failure and that must stay the headline.
  3. Print one operator line after a successful clear, e.g.
     `"Cleared the consolidation record: nothing of this attempt remains, so the next run starts from <target>'s current tip."`
     Keep it `markup=False`-safe and do not claim success about the consolidation itself.
  4. Update the function docstring: the door now also settles the record on a clean rollback, and
     why (window base honesty + the `--abort` wedge). Note `never raises` still holds.
  5. Make it explicit in a comment why a partial rollback returns early (no clear) — that is
     FR-004 and the reason #5687 still needs `--release-branch`.
- **Files**: `src/specify_cli/consolidation/executor.py`.
- **Notes**: `run.canonical_id` is the record's mission id, the same key `clear_state` takes.

### Subtask T003 – Prove the partial-rollback shape is unchanged

- **Purpose**: FR-004 is a ratchet: the fix must not trade the bug for a lost record.
- **Steps**: run
  `uv run pytest "tests/terminus/test_rollback_door.py::test_dirty_target_checkout_is_reported_not_restored_and_the_record_is_kept" -x -q`
  and confirm it passes untouched, then confirm (by reading the code path, and the test's own
  `_record(mission) is not None` assertion) that the kept record still carries attempt 1's
  `pre_mutation_target_sha`. If that assertion is only implied, strengthen it in the test to
  assert the persisted `pre_mutation_target_sha` equals the pre-run target tip and record why in
  a comment — this is the "same fixture, both halves" positive control the non-vacuity tactic
  requires.
- **Files**: read `tests/terminus/test_rollback_door.py`; a small assertion addition there is in
  scope if needed (note it in the PR body as a WP01/WP02 boundary crossing with its rationale).
- **Notes**: do not move the dirty-checkout test's expectations.

### Subtask T004 – Targeted suites, lint and types

- **Steps**:
  1. `uv run pytest tests/terminus/test_repro_6770.py tests/terminus/test_rollback_door.py tests/consolidation/test_rollback_authority.py tests/consolidation/test_single_rollback_authority.py tests/consolidation/test_executor_rollback_wiring.py tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py -q`
  2. `uv run ruff check src/specify_cli/consolidation/rollback.py src/specify_cli/consolidation/executor.py`
     and `uv run ruff format --check` on the same two files.
  3. `uv run mypy src/specify_cli/consolidation/rollback.py src/specify_cli/consolidation/executor.py`
     (strict, as CI runs it).
  4. Record command + counts in the WP history.
- **Notes**: no full-directory or heavy suite locally (NO_FULL_HEAVY_SUITES_IN_MISSION).

## Test Strategy

The coverage that matters for this WP is behavioural and lives in WP01's files; this WP adds no
new test file. Every new branch must be exercised: the clear path by WP01 T001/T002, the kept
path by WP02 T003.

## Risks & Mitigations

- **Clearing on the wrong verdict** would drop a record that still holds un-restored content —
  key strictly on the report verdict, and keep the `NOT_RESTORED`/verified-landing cases tested.
- **Masking the operator's error** — guarded clear, warning only, original exception re-raised.
- **Double-clearing on `--abort`** — the abort path clears on its own and never reaches the door;
  add nothing there.

## Review Guidance

- Is the verdict derived from the report alone (no second probe of git state)?
- Does any path now clear a record after a `NOT_RESTORED` outcome?
- Is `fully_restored` untouched, and is `--abort` behaviour unchanged?
- Are the operator line and the docstring honest about what was and was not done?

## Progress & Status

Use `spec-kitty agent tasks add-history WP02 --note "..."` and
`spec-kitty agent tasks move-task WP02 --to <status>`.
