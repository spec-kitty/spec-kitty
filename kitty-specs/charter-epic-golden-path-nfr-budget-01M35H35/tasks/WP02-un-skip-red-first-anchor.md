---
work_package_id: WP02
title: 'FR-001 un-skip: red-first ATDD anchor'
dependencies: []
requirement_refs:
- FR-001
- C-004
- C-001
- C-002
- C-003
- SC-001
planning_base_branch: issue-4213-golden-path-nfr-budget
merge_target_branch: issue-4213-golden-path-nfr-budget
branch_strategy: Planning artifacts for this mission were generated on issue-4213-golden-path-nfr-budget. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4213-golden-path-nfr-budget unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-epic-golden-path-nfr-budget-01M35H35
base_commit: 4c99dc103113fcb4ddf5fb55ffb63f169d7ac6a2
created_at: '2026-09-23T03:42:47.848397+00:00'
subtasks:
- T006
- T007
- T008
history: []
agent_profile: python-pedro
authoritative_surface: tests/e2e/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/e2e/test_charter_epic_golden_path.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP02 – FR-001 un-skip: red-first ATDD anchor

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Remove ONLY the `@pytest.mark.skip(...)` decorator from
`test_charter_epic_golden_path` and confirm the test is now collected and fails
(times out) in its current, unmodified state — this failure IS the red-first
proof for FR-001 per the charter's ATDD-first / C-011 discipline. The test turns
green only once WP03 (fixture redesign), WP04 (freshness pre-check), and WP05
(lazy imports) land; this WP does not attempt to make it pass.

## Context

Per `spec.md` C-004 and `plan.md`'s Project Structure section, the skip decorator
sits at `tests/e2e/test_charter_epic_golden_path.py` lines ~797-805 (verify the
exact current line numbers yourself — the file may have shifted slightly since
plan.md was written; locate the decorator by its `reason="#4213: ...")` text, not
by line number alone). **Only the decorator itself is removed.** The
`@pytest.mark.timeout(120)` marker immediately below it (NFR-001/C-001 — the
unmodified 120s budget) and the `def test_charter_epic_golden_path(...)` line
below that must remain byte-for-byte untouched.

This WP is deliberately narrow and deliberately produces a still-failing test —
per `plan.md`'s "Red-first per changed behaviour" table: "removing the skip
decorator alone makes the test's own body... the red-first check: reverting the
skip-removal re-skips the test, which is itself the observable regression this
FR exists to prevent." Do not attempt to fix the underlying budget/hang issue in
this WP — that is WP03/WP04/WP05's job. A red (failing/timing-out) result here is
the correct, expected outcome of this WP.

**This WP is SC-001's own delivery point (added per post-tasks analysis, finding
B2).** SC-001 ("the `@pytest.mark.timeout(120)` marker on
`test_charter_epic_golden_path` is itself the falsifiable acceptance
mechanism... reverting the mission's fixture/CLI-startup changes must make it
fail (timeout) again, proving the marker is load-bearing rather than
incidentally green") is delivered exactly by this WP's own scope: removing
*only* the skip decorator, leaving `@pytest.mark.timeout(120)` as the real,
active enforcement mechanism, and observing it genuinely fail red before any
lever fix lands. This WP's own red-first evidence (T008) *is* the
non-vacuousness proof SC-001 requires — record it as such, not merely as
FR-001's own anchor.

**This WP also carries C-001, C-002, and C-003 (added per finding C3) as binding
constraints on its own scope, not merely on the mission overall**: removing
*only* the skip decorator, and nothing else, is exactly what keeps this change
compliant with C-001 (no loosening the 120s cap — the marker itself is
untouched) and C-002 (no cadence move — this WP does not touch the CI router or
this test's shard membership). C-003 (no in-process substitution) bounds the
"resist the urge to fix it here" instruction below: even if this WP's author
were tempted to make the test pass quickly, doing so via any in-process/library
substitution for the golden path's subprocess CLI calls would violate C-003 —
this WP touches none of those call sites at all, which is the simplest possible
compliance with C-003 for this WP's own narrow scope.

### Subtask T006: Remove the skip decorator only

**Purpose**: Un-skip the test per FR-001/C-004 without touching anything else in
the file.

**Steps**:
1. Open `tests/e2e/test_charter_epic_golden_path.py` and locate the
   `@pytest.mark.skip(reason="#4213: ...")` decorator immediately above
   `@pytest.mark.timeout(120)` and `def test_charter_epic_golden_path(...)`.
2. Delete the entire decorator (from its opening `@pytest.mark.skip(` through its
   closing `)`), and nothing else. Leave the blank-line spacing around it
   consistent with the surrounding style (run `ruff format` on just this file
   afterward if formatting looks off, but do not reformat unrelated code).
3. Confirm via `git diff tests/e2e/test_charter_epic_golden_path.py` that the
   diff contains ONLY the removed decorator lines — no other line in the file
   changed.

**Files**: `tests/e2e/test_charter_epic_golden_path.py` (deletion only, ~9 lines
removed).
**Validation**: `git diff` shows a pure deletion of the skip decorator block;
`@pytest.mark.timeout(120)` and the function signature are present, unchanged,
immediately below where the decorator was.

### Subtask T007: Confirm the test is now collected (not skipped)

**Purpose**: Prove the un-skip took effect — the test must now be a real
collected test item, not silently absent from collection.

**Steps**:
1. Run:
   ```bash
   .venv/bin/python -m pytest tests/e2e/test_charter_epic_golden_path.py --collect-only -q
   ```
2. Confirm `test_charter_epic_golden_path` appears in the collected list with no
   `SKIPPED` annotation.

**Files**: none changed (read-only verification).
**Validation**: the collection output lists the test as a real, runnable item.

### Subtask T008: Run the test and confirm it is RED (expected at this point)

**Purpose**: Establish the red-first proof this WP exists to produce. This test
is EXPECTED to fail or time out right now — WP03/WP04/WP05 have not landed yet.

**Steps**:
1. Run:
   ```bash
   .venv/bin/python -m pytest tests/e2e/test_charter_epic_golden_path.py::test_charter_epic_golden_path -q
   ```
   with `@pytest.mark.timeout(120)` active (do not pass `-p no:timeout` or any
   flag that disables the timeout plugin — the whole point is to observe the
   real, currently-over-budget behavior under the real budget).
2. Record the observed failure mode (timeout at 120s, or an assertion failure,
   whichever occurs) in this WP's own completion notes / commit message — this
   is the evidence that FR-001's red-first anchor is real, not vacuous.
3. Do **not** attempt to make this test pass in this WP. A red result here is
   success for this WP's own scope; WP08 is where the fully-fixed test is
   expected to pass.

**Files**: none changed (read-only verification).
**Validation**: the test ran (was not skipped), and its outcome (red) is
recorded as evidence, not silently discarded.

## Definition of Done

- The `@pytest.mark.skip(...)` decorator is removed; `@pytest.mark.timeout(120)`
  and the function definition are untouched (verified via `git diff`).
- `pytest --collect-only` shows the test as collected, not skipped.
- Running the test under its real 120s timeout produces a recorded red result
  (failure or timeout) — this is the expected, correct outcome of this WP.
- Per-subtask completion is recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` for T006–T008.
- No file other than `tests/e2e/test_charter_epic_golden_path.py` is touched by
  this WP.

## Risks

- **Scope creep into fixing the budget**: this WP's temptation is to "just fix
  it while I'm here." Resist this — C-003/C-001/C-002 and the mission's own WP
  split assign the actual fix to WP03/WP04/WP05; mixing them here breaks the
  red-first proof this WP exists to establish and creates an ownership overlap
  with WP03/WP04/WP05's `owned_files`.
- **Accidentally touching line 806/807**: a careless multi-line deletion could
  clip into the `@pytest.mark.timeout(120)` marker or the function signature.
  The `git diff` check in T006 is the guard against this.

## Reviewer Guidance

Confirm the diff is a pure decorator deletion (nothing else touched), confirm
`@pytest.mark.timeout(120)` is still present and unmodified, and confirm the WP's
own evidence shows the test collected and observed RED (not silently skipped,
not silently passing — a pass here would indicate either this WP quietly did
more than its scope, or a stale/cached result).

Implementation command: `spec-kitty agent action implement WP02 --agent claude`
