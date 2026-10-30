---
work_package_id: WP01
title: Informational duplicate-opening finding
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-003
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
planning_base_branch: issue-6764-doctor-decisions-duplicate-openings
merge_target_branch: issue-6764-doctor-decisions-duplicate-openings
branch_strategy: Planning artifacts for this mission were generated on issue-6764-doctor-decisions-duplicate-openings. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6764-doctor-decisions-duplicate-openings unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-doctor-decisions-duplicate-openings-01M66YMR
base_commit: dca1dde6a39036b06147ffc8fde5367019b9db1c
created_at: '2026-10-30T17:49:22.192384+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Implementation
history:
- at: '2026-10-30T17:46:26Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/decisions/index_fold.py
- src/specify_cli/cli/commands/_decisions_doctor.py
- tests/decisions/test_decisions_reconciler.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Informational duplicate-opening finding

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter (or any user-defined profile), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match
for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your
  implementation TODO list.
- **Report progress**: record what you changed with
  `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``.
Use language identifiers in code blocks: ````python`,````bash`.

---

## Objectives & Success Criteria

Deliver the whole user-visible change of this mission:

1. `spec-kitty doctor decisions` (default, read-only) prints an informational line naming
   every decision whose event log holds several `DecisionPointOpened` rows that the
   canonical fold already tolerates (#4848).
2. `spec-kitty doctor decisions --json` carries the same information as one additive key,
   `duplicate_openings_tolerated: [<decision_id>, ...]`, always present and `[]` when
   there is nothing to report.
3. Nothing else changes: `clean` stays `true` on such a log, the diagnose exit code stays
   0, and `--repair` behaves exactly as before (it rebuilds the index and never rewrites
   the event log).
4. The predicate is not re-derived in the doctor: it comes from `index_fold`, the module
   that already applies it, so openings that differ beyond `recorded_at` remain a
   `malformed_folds` error and can never appear as an informational duplicate.

Success criteria (from `spec.md`): SC-001 … SC-005.

## Context & Constraints

Read before coding:

- `kitty-specs/doctor-decisions-duplicate-openings-01M66YMR/spec.md` — FR-001 … FR-006,
  NFR-001 … NFR-003, C-001 … C-003.
- `kitty-specs/doctor-decisions-duplicate-openings-01M66YMR/plan.md` — D1 … D5, IC-01 /
  IC-02.
- `kitty-specs/doctor-decisions-duplicate-openings-01M66YMR/research.md` — D-1 … D-6.
- `src/specify_cli/decisions/index_fold.py` — `_select_opened_event`, `_opened_identity`,
  `_OPENED_VOLATILE_FIELD`, `fold_events`, `FoldError`, `__all__`.
- `src/specify_cli/cli/commands/_decisions_doctor.py` — `DecisionsReconciliationReport`,
  `_fold_diagnostics`, `_diagnose`, `_emit_lossy_attribution_warning`,
  `_emit_malformed_fold_warning`, `_emit_status_mismatch_warning`, `_emit_human`,
  `_emit_json`, `run_decisions_reconciliation`.
- `tests/decisions/test_decisions_reconciler.py` — helpers `_setup_meta`,
  `_mission_dir`, `_events_for_decision`, `_invoke_doctor_decisions_json`, and the #4848
  test `test_doctor_and_repair_accept_identical_duplicate_openings`.

Constraints:

- **Do not** change `index_fold.fold_events` behaviour or `_select_opened_event`'s choice.
- **Do not** add the finding to the `clean` property or to `findings` (a `findings` code
  would flip `clean: false` and break FR-003). `clean` is computed from the error
  conditions only.
- **Do not** touch `--repair`: the repair path already re-runs `_diagnose`, so the finding
  appears on the post-repair report for free (FR-006, C-001).
- No new dependency, no new module (C-003). Keep the diff to the three owned files.
- Read-only: nothing in the diagnose path may write (NFR-002).

## Branch Strategy

- **Strategy**: coord topology, one lane; the mission's planning branch is the merge
  target (`issue-6764-doctor-decisions-duplicate-openings`).
- **Planning base branch**: `issue-6764-doctor-decisions-duplicate-openings`
- **Merge target branch**: `issue-6764-doctor-decisions-duplicate-openings`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Claim and run this package with:

```bash
spec-kitty agent action implement WP01 --agent python-pedro --mission doctor-decisions-duplicate-openings-01M66YMR
```

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: a duplicate log is reported clean AND names the decision

- **Purpose**: This is the failing test that proves the gap. Today
  `duplicate_openings_tolerated` does not exist, so the assertion cannot pass.
- **Steps**:
  1. In `tests/decisions/test_decisions_reconciler.py`, add a test beside
     `test_doctor_and_repair_accept_identical_duplicate_openings` (keep the module's
     existing helpers and `pytestmark`).
  2. Build the fixture the way that test does: `_setup_meta(tmp_path)`, create
     `.kittify/`, `open_decision(...)`, then append a second `DecisionPointOpened` row
     whose `event_id`, `at` and `payload.recorded_at` differ but whose remaining payload
     bytes are identical.
  3. Run the REAL CLI through `_invoke_doctor_decisions_json(tmp_path, MISSION_SLUG,
     repair=False)`.
  4. Assert: `exit_code == 0`; `payload["clean"] is True`; `payload["malformed_folds"]
     == []`; `resp.decision_id in payload["duplicate_openings_tolerated"]`.
  5. Run it and confirm it fails for the right reason (`KeyError:
     'duplicate_openings_tolerated'`), not a fixture error.
- **Files**: `tests/decisions/test_decisions_reconciler.py`
- **Parallel?**: yes, with T002/T003.
- **Notes**: keep the fixture local to the test (no new shared factory) — the module
  builds its fixtures inline throughout.

### Subtask T002 – Red-first: three duplicates name the id once; a clean log is silent

- **Purpose**: Pin the counting rule and the empty case (FR-004, SC-002, and user story 2
  acceptance scenario 2).
- **Steps**:
  1. Extend the duplicated fixture (or add a second test) with a THIRD identical opening;
     assert the decision id appears exactly once in `duplicate_openings_tolerated`
     (`payload["duplicate_openings_tolerated"].count(id) == 1`).
  2. Add a test on a mission with a single opening per decision: assert
     `payload["duplicate_openings_tolerated"] == []`.
  3. Also assert the human surface is quiet: invoke `doctor decisions` (no `--json`) via
     the same `CliRunner` pattern and assert the output does not contain the word
     "informational" for the clean fixture.
- **Files**: `tests/decisions/test_decisions_reconciler.py`
- **Parallel?**: yes.
- **Notes**: use the module's `_runner` and `contextlib.chdir` helper shape.

### Subtask T003 – Red-first: differing duplicates stay an error, never "tolerated"

- **Purpose**: Proves the single-authority rule (FR-005, SC-003, user story 2 acceptance
  scenario 1). A second, drifting duplicate rule would pass T001/T002 and fail this one.
- **Steps**:
  1. Build the same fixture but change a real payload field on the duplicate (for example
     `payload["question"]`) instead of only `recorded_at`.
  2. Assert `payload["malformed_folds"] == [resp.decision_id]`.
  3. Assert `resp.decision_id not in payload["duplicate_openings_tolerated"]`.
  4. Assert the command's exit code is 0 read-only (diagnose is report-only) and that
     `payload["clean"] is False` (a malformed fold is a non-clean condition — this is the
     pre-existing behaviour, pinned so the new field cannot mask it).
- **Files**: `tests/decisions/test_decisions_reconciler.py`
- **Parallel?**: yes.
- **Notes**: this is the positive-control partner of T001 on the same fixture shape.

### Subtask T004 – The exported `index_fold` helper

- **Purpose**: One place answers "how many openings beyond the tolerated one does this
  group hold", using the fold's own notion of equality.
- **Steps**:
  1. In `src/specify_cli/decisions/index_fold.py`, beside `_select_opened_event`, add:

     ```python
     def tolerated_duplicate_openings(events: Iterable[Mapping[str, Any]]) -> int:
         """How many ``DecisionPointOpened`` rows *events* holds beyond the one folded."""
     ```

  2. Implementation: collect the openings (`e.get("event_type") == DECISION_POINT_OPENED`),
     return `0` for fewer than two, otherwise count how many share the FIRST opening's
     `_opened_identity()` — i.e. the rows `_select_opened_event` would accept alongside it.
     Use `_opened_identity()` and `_OPENED_VOLATILE_FIELD`; do not restate the field name.
  3. Do NOT raise: differing payloads are the fold's refusal, not this helper's. Return
     the count of identical duplicates only.
  4. Add `"tolerated_duplicate_openings"` to `__all__` (repo `__all__` convention, C-007).
  5. Document the helper in the module docstring's consumer list if it reads naturally, and
     state in the docstring that it shares `_select_opened_event`'s equality rule so the
     two cannot drift.
- **Files**: `src/specify_cli/decisions/index_fold.py`
- **Parallel?**: no — T005 depends on it.
- **Notes**: keep it ≤15 lines. Do not alter `fold_events`.

### Subtask T005 – Collect the ids in `_fold_diagnostics` and carry them on the report

- **Purpose**: The diagnose path already folds every decision once; piggyback the count so
  there is no extra read and no extra fold (NFR-001).
- **Steps**:
  1. Add to `DecisionsReconciliationReport`:

     ```python
     duplicate_openings_tolerated: list[str] = field(default_factory=list)
     ```

     with a short docstring comment saying it is INFORMATIONAL, never part of `clean`,
     and introduced for #6764 (the deferred R-7 finding on #4848).
  2. Change `_fold_diagnostics` to return a third value,
     `tuple[list[str], list[dict[str, str]], list[str]]` =
     `(malformed_ids, status_mismatch, duplicate_ids)`.
  3. In its loop, AFTER `fold_events` succeeded, append `decision_id` when
     `_index_fold.tolerated_duplicate_openings(grouped[decision_id]) > 0`. A malformed
     decision `continue`s before this, so the two lists are disjoint by construction.
  4. Update the `_diagnose` call site and the `DecisionsReconciliationReport(...)`
     construction to thread `duplicate_openings_tolerated=sorted(duplicate_ids)`.
  5. Update both docstrings (`_fold_diagnostics`, `_diagnose`) to describe the new value
     and state that it never affects `clean`.
  6. Do NOT touch the `clean` property.
- **Files**: `src/specify_cli/cli/commands/_decisions_doctor.py`
- **Parallel?**: no.
- **Notes**: keep the return type annotation exact; `mypy` runs in CI.

### Subtask T006 – Emit on both surfaces

- **Purpose**: FR-001 (human) and FR-002 (`--json`), in the shape #4919 established.
- **Steps**:
  1. Add `_emit_duplicate_openings_notice(report)` next to the other
     `_emit_*_warning` helpers:

     ```python
     def _emit_duplicate_openings_notice(report: DecisionsReconciliationReport) -> None:
         """#6764: name the decisions whose log holds tolerated duplicate openings."""
     ```

     It returns early when the list is empty; otherwise prints ONE `cyan` line (never
     red) stating that the rows were tolerated, how many decisions, the decision ids, and
     that the log is left unchanged. Suggested text:

     ```
       informational (N) decision(s) with duplicate openings the fold tolerates (log left unchanged): <ids>
     ```

  2. Call it from `_emit_human` AFTER the `if report.clean:` / `else:` block and alongside
     the existing `_emit_lossy_attribution_warning(report)` /
     `_emit_malformed_fold_warning(report)` / `_emit_status_mismatch_warning(report)`
     calls, so it prints on both clean and diverged reports.
  3. In `_emit_json`, add `"duplicate_openings_tolerated": report.duplicate_openings_tolerated,`
     next to `malformed_folds` / `status_mismatch`. Always present; never conditional.
  4. Update the `_emit_json` and `run_decisions_reconciliation` docstrings to mention the
     additive key and that exit codes are unchanged.
- **Files**: `src/specify_cli/cli/commands/_decisions_doctor.py`
- **Parallel?**: no.
- **Notes**: "informational" must appear in the human line so nobody reads it as a failure.

### Subtask T007 – Prove read-only and suite stability

- **Purpose**: NFR-002, C-001, SC-004, SC-005.
- **Steps**:
  1. In the T001 test, capture `status.events.jsonl` and `decisions/index.json` bytes
     before the read-only run and assert them unchanged after (mirroring the existing
     #4848 test's `log_before` assertion).
  2. Add a `--repair` assertion: after `repair=True`, the finding still lists the decision
     and the log bytes are unchanged (FR-006).
  3. Run:
     - `uv run pytest tests/decisions/test_decisions_reconciler.py -q`
     - `uv run pytest tests/decisions -q`
     - `uv run ruff check src/specify_cli/decisions/index_fold.py src/specify_cli/cli/commands/_decisions_doctor.py tests/decisions/test_decisions_reconciler.py`
     - `uv run ruff format --check` on the same three files
     - `uv run mypy src/specify_cli/decisions/index_fold.py src/specify_cli/cli/commands/_decisions_doctor.py`
  4. Record the exact commands and results in your hand-off note.
- **Files**: `tests/decisions/test_decisions_reconciler.py`
- **Parallel?**: no — last.
- **Notes**: do NOT run full heavy suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`); the two
  commands above are the mission's scope.

## Test Strategy

- Location: `tests/decisions/test_decisions_reconciler.py` (the module that already owns
  the `doctor decisions` contract; do not create a `test_issue_6764*` file).
- Style: real CLI through `_invoke_doctor_decisions_json` (`typer.testing.CliRunner`) —
  no direct private-function calls for the acceptance assertions.
- Red-first: T001–T003 must fail before T004–T006 and pass after.
- Type check: `mypy` on the two touched source files must be clean (CI gate).

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| The new field accidentally gates `clean` or the exit code | T001 asserts `clean: true` and exit 0 on a duplicate log; do not add to `findings`. |
| A duplicate rule is re-implemented in the doctor | The helper lives in `index_fold` and reuses `_opened_identity()`; T003 fails on any divergence. |
| A malformed decision is also reported as "tolerated" | The collector runs only after `fold_events` succeeded, and malformed decisions `continue` first. |
| A second read of the event log sneaks in | The count uses the `grouped` dict `_diagnose` already read. |

## Review Guidance

- Confirm the human line is not red and says "informational".
- Confirm `duplicate_openings_tolerated` is present but `[]` on a healthy log.
- Confirm `clean`, `--repair` semantics and both exit codes are untouched by diffing those
  code paths.
- Confirm the duplicate predicate is the fold's own (`_opened_identity`), not a copy.
- Confirm the tests fail without the fix (revert the source hunks locally or trust the
  recorded red run in the hand-off).

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
