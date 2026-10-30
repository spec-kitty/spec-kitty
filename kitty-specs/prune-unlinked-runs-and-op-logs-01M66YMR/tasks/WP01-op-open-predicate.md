---
work_package_id: WP01
title: One owner for is-this-Op-open
dependencies: []
requirement_refs:
- FR-005
- FR-006
- FR-013
- C-004
- NFR-001
planning_base_branch: issue-6739-prune-unlinked-runs-and-op-logs
merge_target_branch: issue-6739-prune-unlinked-runs-and-op-logs
branch_strategy: Planning artifacts for this mission were generated on issue-6739-prune-unlinked-runs-and-op-logs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6739-prune-unlinked-runs-and-op-logs unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Foundational
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/invocation/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/invocation/writer.py
- src/specify_cli/doctor/ops.py
- tests/specify_cli/invocation/test_doctor_ops.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – One owner for is-this-Op-open

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter (or any user-defined profile), and behave according to its guidance before
parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best
match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via
  `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the
status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code
blocks: ````python`, ````bash`.

---

## Objectives & Success Criteria

Ship one public predicate that answers "which Ops are still open in this checkout",
owned by the module that owns the Op records, and make the existing doctor surface use
it — so the retention engine (WP02) can ask the same question without a second copy of
the rule.

Done when:

- `specify_cli.invocation.writer.open_invocation_ids(repo_root) -> set[str]` exists,
  is documented, and returns exactly the ids `doctor ops` already calls orphans;
- `specify_cli.doctor.ops.list_orphan_ops` keeps its signature, ordering and output
  (`list[Path]`) by delegating to it;
- the whole `tests/specify_cli/invocation/test_doctor_ops.py` still passes untouched;
- `mypy --strict` and `ruff` are clean on the changed files.

## Context & Constraints

- Mission: `kitty-specs/prune-unlinked-runs-and-op-logs-01M66YMR/` — read `spec.md`,
  `plan.md` (IC-01), `data-model.md` ("An Op log's owner is its Op") and
  `research.md` (decision D5) before writing code.
- The two durable traces of an Op are the per-record `kitty-ops/<id>.jsonl` file and the
  append-only closure spine `kitty-ops/op-closures.jsonl`. An Op is **open** when its
  record exists, carries no `{"event": "completed"}` line, and its id is not on the
  spine (`specify_cli.invocation.writer.closed_invocation_ids`).
- `kitty-ops/` also holds files that are not Ops: `ops-index.jsonl`,
  `lifecycle.jsonl`, `propagation-errors.jsonl` and `op-closures.jsonl`. They are
  never Ops; today that exclusion lives in `doctor/ops.py::_NON_OP_JSONL`.
- Single canonical authority is a charter principle: this predicate must exist once.
  Do not add a second "is it closed" check in the retention engine.
- Reader side only: reading an Op record is a plain file read; never append to an
  event log from here.
- Performance: one pass over the record directory per call, returning a set (the
  engine calls it once per scan; 1,000 records must stay well inside its budget).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on
  `issue-6739-prune-unlinked-runs-and-op-logs`; completed changes merge back into
  `issue-6739-prune-unlinked-runs-and-op-logs`.
- **Planning base branch**: `issue-6739-prune-unlinked-runs-and-op-logs`
- **Merge target branch**: `issue-6739-prune-unlinked-runs-and-op-logs`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first tests for `open_invocation_ids`

- **Purpose**: pin the predicate's contract before it exists (ATDD-first, charter
  C-011).
- **Steps**: in `tests/specify_cli/invocation/test_doctor_ops.py` add focused tests
  that build a `tmp_path` `kitty-ops/` directory and assert:
  1. a record with only a `started` line is open;
  2. a record with a later `completed` line is not open;
  3. a record with only `started` whose id is on `kitty-ops/op-closures.jsonl` is not
     open;
  4. `ops-index.jsonl`, `lifecycle.jsonl`, `propagation-errors.jsonl` and
     `op-closures.jsonl` contribute no ids;
  5. a missing `kitty-ops/` directory yields an empty set;
  6. a malformed line in a record does not raise and does not make a closed Op open
     (best-effort parsing, the same tolerance `_has_completed_event` has today).
- **Files**: `tests/specify_cli/invocation/test_doctor_ops.py`
- **Parallel?**: No — first commit of the lane, before any implementation.
- **Notes**: run the tests and confirm they fail for the *right* reason
  (`ImportError`/`AttributeError` on the missing name), not because of a fixture bug.
  Record the red run in the WP history note.

### Subtask T002 – Implement `open_invocation_ids`

- **Purpose**: give the Op record owner the predicate the doctor surface and the
  cleanup engine both need.
- **Steps**: in `src/specify_cli/invocation/writer.py`:
  - move the non-Op filename exclusion next to the other Op-record layout constants
    (same four names, same reason) and give it a docstring;
  - add `open_invocation_ids(repo_root: Path) -> set[str]` that reads
    `repo_root / EVENTS_DIR`, skips non-Op filenames, subtracts
    `closed_invocation_ids(repo_root)`, and skips a record that carries a completed
    event;
  - keep the `EVENTS_DIR` / `OP_CLOSURES_*` constants as they are and do not change
    `closed_invocation_ids`.
- **Files**: `src/specify_cli/invocation/writer.py`
- **Parallel?**: No.
- **Notes**: the completed-event probe is the same best-effort JSONL scan
  `doctor/ops.py::_has_completed_event` performs today (skip blank and malformed
  lines, tolerate `OSError` as "not closed"). Move it, do not copy it, and keep the
  docstring's reason: a corrupt record must read as open (fail safe), because an
  unreadable record is not evidence of closure.

### Subtask T003 – Route `list_orphan_ops` through the predicate

- **Purpose**: one rule, two callers; `doctor ops` behaviour must not change.
- **Steps**: in `src/specify_cli/doctor/ops.py`, make `list_orphan_ops` return the
  record paths for `open_invocation_ids(repo_root)` in the same sorted order it
  returns today, and delete the now-unused local set and helper. Keep the public
  name, signature and docstring meaning.
- **Files**: `src/specify_cli/doctor/ops.py`
- **Parallel?**: No.
- **Notes**: `close_stale_ops` in the same module also calls `list_orphan_ops`; it
  must keep working (its tests are in the same file). If a sorted-path construction
  would change ordering for names that are not `*.jsonl`, prefer keeping the
  directory iteration that produced the original order.

### Subtask T004 – Verify

- **Purpose**: prove the WP is green and the pre-existing behaviour is intact.
- **Steps**:
  ```bash
  uv run pytest tests/specify_cli/invocation/test_doctor_ops.py -q
  uv run mypy --strict src/specify_cli/invocation/writer.py src/specify_cli/doctor/ops.py
  uv run ruff check src/specify_cli/invocation/writer.py src/specify_cli/doctor/ops.py tests/specify_cli/invocation/test_doctor_ops.py
  ```
- **Files**: none.
- **Parallel?**: No.
- **Notes**: if the repository's configured mypy target differs, use the project's
  command from `pyproject.toml` / CI rather than inventing flags.

## Test Strategy

Red first: T001's tests are committed before T002/T003 (charter C-011). The reviewer
checks the tests fail on the planning base and pass at the WP head. The existing
`test_doctor_ops.py` tests are the regression net and must pass **unmodified**.

## Risks & Mitigations

- **Behaviour drift in `doctor ops`.** The existing tests pin the return value; run
  them after every edit. Do not "improve" ordering.
- **A second copy of the rule.** If you are tempted to re-implement "has a completed
  event" inside `list_orphan_ops`, stop: that is exactly what this WP removes.
- **Reading a huge directory.** One `iterdir()` pass, one read per record file; do not
  call `closed_invocation_ids` inside the loop.

## Review Guidance

- Confirm the predicate lives in `invocation/writer.py`, not `doctor/ops.py`.
- Confirm `list_orphan_ops` still returns `list[Path]` sorted, still excludes the four
  non-Op files, and still treats a corrupt record as open.
- Confirm no event-log append door is called (grep the diff for `append_event`).
- Confirm the red-first commit precedes the implementation commits.

## Progress & Status

Progress, history and status live in the status event log (`status.events.jsonl`) —
never in this prompt file.

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP01 --to <status>`
- **View history and status**: `spec-kitty agent tasks status --mission prune-unlinked-runs-and-op-logs-01M66YMR`
