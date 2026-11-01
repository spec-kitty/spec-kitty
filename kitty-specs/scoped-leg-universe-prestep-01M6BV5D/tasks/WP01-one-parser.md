---
work_package_id: WP01
title: One parser for the selected-gates file
dependencies: []
requirement_refs:
- FR-005
- C-001
planning_base_branch: issue-7001-universe-prestep-scope
merge_target_branch: issue-7001-universe-prestep-scope
branch_strategy: Planning artifacts for this mission were generated on issue-7001-universe-prestep-scope. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7001-universe-prestep-scope unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-scoped-leg-universe-prestep-01M6BV5D
base_commit: a84a6adf146f7798e14185f9090e14d5f9b44931
created_at: '2026-11-01T15:28:45.354432+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Foundation
history:
- at: '2026-11-01T15:25:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: scripts/ci/battery_scope.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- scripts/ci/battery_scope.py
- scripts/ci/battery_partition_plugin.py
- tests/ci/test_battery_scope.py
- tests/ci/test_battery_partition_plugin.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – One parser for the selected-gates file

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave
according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: implementer
- **Agent/tool**: t3-code

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field via `spec-kitty agent tasks status` before starting; address every
feedback item first, recording each with `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

The selected-gates file (#6994) has exactly one writer and exactly one parser, both in
`scripts/ci/battery_scope.py`, and the battery plug-in keeps its documented
`SK_BATTERY_GATES_FILE` contract while reading through that parser. WP02 then hands the same
file to the universe decision, so the pre-step and the running leg can never disagree about
which gates a leg runs.

Done when:

- `scripts/ci/battery_scope.py` exports `write_selected_gates(gates, out)` and
  `read_selected_gates(named)`, and `output_lines` writes through the former.
- `battery_partition_plugin.read_gates_file(env)` returns `None` for an unset/empty variable,
  the parsed set for a readable file, and raises `pytest.UsageError` for a missing one —
  unchanged contract, one parser.
- `tests/ci/test_battery_scope.py` and `tests/ci/test_battery_partition_plugin.py` pass, and
  the whole existing `tests/ci/test_battery_partition_plugin.py` file stays green.

## Context & Constraints

- Mission spec: `kitty-specs/scoped-leg-universe-prestep-01M6BV5D/spec.md` (FR-005, C-001).
- Plan: `kitty-specs/scoped-leg-universe-prestep-01M6BV5D/plan.md` (IC-01, IC-02).
- Contract: `kitty-specs/scoped-leg-universe-prestep-01M6BV5D/contracts/selected-gates-file.md`.
- The plug-in's contract text is its module docstring ("An unset or empty variable runs the
  whole part; a named file that is missing or lists nothing of the part fails closed"). Do not
  change that behaviour; only where the parsing lives.
- Keep the smallest viable diff: no new module, no new dependency, no signature change.

## Branch Strategy

- **Strategy**: mission branch `issue-7001-universe-prestep-scope`, merge target `main`
- **Planning base branch**: `main`
- **Merge target branch**: `main`

## Subtasks & Detailed Guidance

### Subtask T001 – Move the selected-gates write/parse pair into `battery_scope`

- **Purpose**: One authority for the file format, next to the writer that already exists.
- **Steps**:
  1. In `scripts/ci/battery_scope.py`, add
     `write_selected_gates(gates: Iterable[str], out: Path) -> None` that writes
     `"".join(f"{gate}\n" for gate in sorted(gates))` with UTF-8 encoding.
  2. Add `read_selected_gates(named: str) -> frozenset[str]` that reads that path as UTF-8,
     splits lines, strips whitespace, drops blanks, and returns a `frozenset`. Let
     `FileNotFoundError`/`OSError` propagate — callers decide what a missing file means.
  3. Make `output_lines` call `write_selected_gates`.
  4. Extend `__all__` in sorted order with the two new names.
- **Files**: `scripts/ci/battery_scope.py`
- **Notes**: The module docstring says the module "only reads the diff and the leg's part";
  update that sentence to say it also owns the selected-gates file format, since it now does.

### Subtask T002 – Point the plug-in's `read_gates_file` at that parser

- **Purpose**: A single parser, so a format change cannot leave the leg and the decision
  disagreeing.
- **Steps**:
  1. In `scripts/ci/battery_partition_plugin.py`, rewrite the body of `read_gates_file` to:
     return `None` when the variable is unset/blank; raise
     `pytest.UsageError(f"{_PREFIX}: {GATES_FILE_ENV} names a missing file: {named}")` when the
     path is not a file; otherwise return `read_selected_gates(named)`.
  2. Import `read_selected_gates` from `scripts.ci.battery_scope` — at module top (the plug-in
     already imports `scripts.ci.shard_select` at top, so this is the same dependency direction),
     unless that creates a cycle; `battery_scope` imports the plug-in lazily inside
     `_part_files`, so a top-level import of `battery_scope` in the plug-in would close a cycle.
     **Therefore import it inside `read_gates_file`**, matching the module's existing lazy-import
     style, and say why in a one-line comment.
  3. Keep the docstring's meaning; no signature change.
- **Files**: `scripts/ci/battery_partition_plugin.py`
- **Notes**: `tests/ci/test_battery_partition_plugin.py` already pins the unset and
  missing-file cases; do not weaken them.

### Subtask T003 – Round-trip tests for the writer and both readers

- **Purpose**: Prove the two readers agree on one fixture, and that blank lines and duplicates
  do not split them.
- **Steps** (write these first, red against today's split implementation where possible):
  1. `tests/ci/test_battery_scope.py`: a test that writes a set through
     `battery_scope.output_lines(..., out=path)` (or `write_selected_gates`) and reads it back
     with `read_selected_gates`, asserting the equal set; include a file written by hand with a
     blank line, a trailing newline and a duplicated gate, asserting the de-duplicated set.
  2. `tests/ci/test_battery_partition_plugin.py`: a test that, for the same file content, asserts
     `read_gates_file({GATES_FILE_ENV: str(path)}) == read_selected_gates(str(path))` — one
     fixture, both readers — plus the existing unset (`None`) and missing (`UsageError`) cases.
  3. Follow the style of both files: `pytestmark = pytest.mark.fast`, `tmp_path`, no network, no
     subprocess.
- **Files**: `tests/ci/test_battery_scope.py`, `tests/ci/test_battery_partition_plugin.py`
- **Notes**: These are [P] relative to T001/T002 (different files), but they must exist and
  fail before the implementation lands (ATDD-first).

## Test Strategy

```bash
uv run --frozen pytest -q tests/ci/test_battery_scope.py tests/ci/test_battery_partition_plugin.py
uv run --frozen ruff check scripts/ci/battery_scope.py scripts/ci/battery_partition_plugin.py tests/ci/test_battery_scope.py tests/ci/test_battery_partition_plugin.py
uv run --frozen mypy scripts/ci/battery_scope.py scripts/ci/battery_partition_plugin.py
```

Record the red run and the green run in the WP history.

## Risks & Mitigations

- An import cycle between `battery_scope` and `battery_partition_plugin`: keep the import
  inside `read_gates_file` and note why.
- A silently changed plug-in contract: the existing plug-in tests are the guard; run them.

## Review Guidance

- Confirm the plug-in's unset/empty and missing-file behaviour is byte-for-byte what it was.
- Confirm one parser: grep for `splitlines` in `scripts/ci/` and expect the single occurrence in
  `read_selected_gates`.
- Confirm `__all__` orderings and that no new dependency appears in `pyproject.toml`.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- **Change status**: `spec-kitty agent tasks move-task WP01 --to <status>`
