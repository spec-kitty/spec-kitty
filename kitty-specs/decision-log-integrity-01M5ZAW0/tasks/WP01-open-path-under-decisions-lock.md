---
work_package_id: WP01
title: One opening per decision under concurrent opens
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-001
- NFR-002
- C-001
- C-002
- SC-001
planning_base_branch: issue-4848-decision-open-lock
merge_target_branch: issue-4848-decision-open-lock
branch_strategy: Planning artifacts for this mission were generated on issue-4848-decision-open-lock. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4848-decision-open-lock unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Open path
history:
- at: '2026-10-27T19:05:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/decisions/
create_intent:
- tests/specify_cli/decisions/test_service_open_concurrency.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/decisions/service.py
- tests/specify_cli/decisions/test_service_open_concurrency.py
- tests/decisions/test_decisions_concurrency.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – One opening per decision under concurrent opens

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Objectives & Success Criteria

- Exactly one `DecisionPointOpened` row per `decision_point_id` under:
  - ARM A: a first open paused inside its opening append + an identical second open;
  - ARM B: an interrupted open (index saved, no row) + two retries, the first paused inside its repair append.
- Both arms red on the planning base (`2 == 1`), green after the fix (FR-001, FR-002, NFR-001).
- Serial controls stay at 1 row. Lock order unchanged: decisions lock → Mission status lock (C-001).
- No new write site; the writes gates stay green unchanged.

## Context & Constraints

- Issue #4848 (open half), Ivan-Melck's 2026-10-16 comment (ARM A/ARM B reproducer).
- #6294 / #5681 fixed the terminal half: read `_terminal_command` in
  `src/specify_cli/decisions/service.py` — one `machine_file_lock` hold covers index save,
  artifact write and terminal emit, and the idempotent retry's check + repair.
- `kitty-specs/decision-log-integrity-01M5ZAW0/{spec,plan,research}.md` (R-1, R-2 lock order).
- Charter: ATDD red-first commit first; tidy-first refactor as its own commit; complexity ≤ 15;
  no new `noqa` / `type: ignore`.
- Out of scope: envelopes, `emit.py` (C-002). Do not touch `emit.py`.

## Branch Strategy

- **Strategy**: single_branch
- **Planning base branch**: issue-4848-decision-open-lock
- **Merge target branch**: issue-4848-decision-open-lock

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.

Implement with: `spec-kitty agent action implement WP01 --agent claude --mission decision-log-integrity-01M5ZAW0`

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first interleaving tests

- **Purpose**: Pin the user-observable behaviour before any fix (charter C-011).
- **Steps**:
  1. Create `tests/specify_cli/decisions/test_service_open_concurrency.py`, `pytestmark = [pytest.mark.unit]`,
     modelled on `tests/specify_cli/decisions/test_service_terminal_concurrency.py`
     (`_Pause` wrapping the REAL `_emit.emit_decision_opened` on its first call; `_Worker`
     daemon threads with bounded joins; `@pytest.mark.timeout(60)`).
  2. Fixture: `kitty-specs/<slug>/meta.json` with `mission_id`/`mission_slug`; open with
     `origin_flow=OriginFlow.CHARTER, step_id, input_key, question, actor="alice"`.
  3. Tests:
     - `test_first_open_paused_in_emit_blocks_identical_open` (ARM A): A paused → start B,
       `b.thread.join(0.5)`, assert B still alive (waiting on the decisions lock); release;
       assert one opening row, B returns `idempotent=True`, same `decision_id`, and
       `fold_events` of the decision's rows succeeds.
     - `test_retries_after_interrupted_open_write_one_opening` (ARM B): first open with
       `_emit._append_raw_event` raising `OSError` (monkeypatch context) → index entry, 0 rows;
       pause the next emit; retry A paused, retry B started and blocked; release; 1 row; the
       blocked retry reports `event_lamport is None` (nothing repaired).
     - Serial controls: identical open twice → 1 row; interrupted then two serial retries → 1 row.
  4. Run on the planning base and record the red output (both arms `2 == 1`; the "B still alive"
     assertion also fails) for the PR's Tests run section.
- **Files**: the new test file only. Commit alone: `test(decisions): red-first ... (#4848)`.

### Subtask T002 – Tidy-first extraction (behaviour-preserving)

- **Purpose**: Make room for the lock-scope change without pushing `open_decision` over C901 15.
- **Steps**: Restructure `_locate_or_create_open_entry` so the code that runs inside the lock is
  a function that receives what it needs (e.g. `_open_locked(...)` returning
  `(existing, entry, is_new)`), with `open_decision` unchanged in behaviour. Keep the
  `build_opened_entry` route (T008 "one canonical constructor").
- **Validation**: T001 tests still red in the same way; `tests/specify_cli/decisions/` and
  `tests/decisions/` otherwise green. Separate commit `refactor(decisions): ...`.

### Subtask T003 – Fresh path inside the lock

- **Purpose**: FR-001. Close ARM A.
- **Steps**: Within the single `machine_file_lock(_decisions_lock_path(mission_dir), ...)` hold:
  dedup lookup → (new) `append_entry` → `_store.write_artifact` → `_emit.emit_decision_opened`.
  `on_minted` is called after the lock is released (a callback must not run under the lock).
  The write-side pre-resolve `_write_events_path(...)` stays BEFORE the lock (it may materialize
  the coordination surface), exactly as in `_terminal_command`.
- **Notes**: If the emit raises, the index entry is already saved (unchanged from today); the next
  retry repairs under the lock (T004).

### Subtask T004 – Retry path inside the lock

- **Purpose**: FR-002. Close ARM B.
- **Steps**: For an existing non-terminal entry, call `_repair_missing_opened_event` inside the
  same lock hold. The `ALREADY_CLOSED` refusal for a terminal entry is unchanged. Keep
  `_opened_event_exists`'s signature and its read-side path (research R-2/plan: after the
  write-side pre-resolve, read and write sides resolve to the same file). Update the docstring
  of `_repair_missing_opened_event` to state the "must run under the decisions lock" invariant,
  mirroring `_repair_missing_terminal_event`.
- **Edge cases**: unreadable log still raises `DecisionEventLogReadError` (lock released by the
  `with`); missing `opened_by` still raises `EVENT_REPAIR_FAILED`.

### Subtask T005 – Stress supplement and comments

- **Steps**:
  1. Add `test_concurrent_identical_opens_write_one_opening` to
     `tests/decisions/test_decisions_concurrency.py` (stress lane, `start_state` in
     {"fresh", "interrupted"}, 8 barrier-released workers, 20 iterations), mirroring
     `test_concurrent_identical_terminal_calls_write_one_event`.
  2. Fix every comment/docstring in `service.py` that describes the old scope (e.g. the
     `_locate_or_create_open_entry` and `open_decision` comments saying the emit follows the
     lock; the `_terminal_command` docstring's "terminal half of #4848" may now say both halves).
  3. Note: `src/specify_cli/cli/commands/decision.py` comments around lines 394/518 only name
     the call chain; leave them unless they claim the old lock scope (out of owned files —
     record a one-line rationale if you must touch them).

## Test Strategy

```bash
uv run --frozen pytest -q tests/specify_cli/decisions/test_service_open_concurrency.py
uv run --frozen pytest -q -n0 -m stress tests/decisions/test_decisions_concurrency.py
uv run --frozen pytest -q tests/specify_cli/decisions tests/decisions tests/specify_cli/cli/commands/test_decision.py \
  tests/specify_cli/orchestrator_api/test_decision_verbs.py tests/specify_cli/orchestrator_api/test_decision_event_log_read_error_envelope.py \
  tests/specify_cli/test_audit_tail_readers.py
uv run --frozen pytest -q tests/architectural/test_event_log_writes_gate.py tests/architectural/test_status_events_writes_gate.py
uv run --frozen ruff check src/specify_cli/decisions/service.py <tests>
uv run --frozen ruff format --check --force-exclude src/specify_cli/decisions/service.py <tests>
uv run --frozen mypy src/specify_cli/decisions/service.py <new test file>
```

## Risks & Mitigations

- Deadlock: only if some path holds the status lock and then takes the decisions lock — none
  exists (research R-2). Do not add one.
- Flaky interleaving: decide the interleaving with events (`_Pause`), never sleeps; bounded joins.

## Review Guidance

- Red→green: T001 red on the planning base, green on the WP head.
- One lock hold per open call; `on_minted` outside it; pre-resolve before it.
- No change to `emit.py`, no new write site, writes gates unchanged.
- ruff, `ruff format --check --force-exclude`, mypy clean; complexity ≤ 15.

## Progress & Status

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks mark-status T001 --status done`
- `spec-kitty agent tasks status`
