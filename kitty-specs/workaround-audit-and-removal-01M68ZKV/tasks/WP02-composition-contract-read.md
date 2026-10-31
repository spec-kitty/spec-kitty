---
work_package_id: WP02
title: Composition reads the executor contract, not a test double
dependencies: []
requirement_refs:
- FR-006
- FR-007
- NFR-001
- SC-003
planning_base_branch: issue-6745-workaround-audit-and-removal
merge_target_branch: issue-6745-workaround-audit-and-removal
branch_strategy: Planning artifacts for this mission were generated on issue-6745-workaround-audit-and-removal. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6745-workaround-audit-and-removal unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-workaround-audit-and-removal-01M68ZKV
base_commit: bfd2830b74f7cd1983e5ca38091117e299dbdf96
created_at: '2026-10-31T13:18:50.625644+00:00'
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Contract read
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-31T12:50:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/runtime/next/
create_intent: []
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/runtime/next/runtime_bridge_composition.py
- tests/specify_cli/next/test_runtime_bridge_composition.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#6745'
---

# Work Package Prompt: WP02 – Composition reads the executor contract, not a test double

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter
before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Issue #6745, finding **S8** (`research.md` §4). `_compose_action` reads its executor result
defensively, and says so:

```python
# Defensive ``getattr`` + duck-typed length so test mocks (MagicMock) and
# real ``StepContractExecutionResult`` instances both flow through cleanly.
invocation_ids = getattr(result, "invocation_ids", ()) or ()
try:
    invocation_count = len(invocation_ids)
except TypeError:
    invocation_count = 0
```

`StepContractExecutionResult` (`src/specify_cli/mission_step_contracts/executor.py:145-163`)
always carries `invocation_ids` and `steps`; `StepContractStepResult` always carries
`unresolved_candidates`. The tolerance exists only for a `MagicMock` — production code bent to
fit a double, the most literal instance of the bias this issue names. And a test pins the
tolerance by setting `fake_result.invocation_ids = object()`, so the double- shaped read is
guarded in two places at once.

Delivered state:

- `_compose_action` reads `result.invocation_ids` and iterates `result.steps` directly.
- The tolerance-pinning test asserts the contract (a real tuple produces the logged count)
  instead of asserting that a contract violation is absorbed.
- The `except Exception` **above** this code is kept: it is the documented FR-009 structured
  failure surface for executor failures, not a test-double accommodation.

- **FR-006 / FR-007**: direct contract read; the tolerance test asserts the contract.
- **NFR-001**: the diff removes a `getattr(..., default)` chain and one `except TypeError`.
- **SC-003**: the bridge log reports the executor's real invocation count.

## Context & Constraints

- Read first: `research.md` §4 row S8 and §6 Q3; `plan.md` IC-02; charter DIRECTIVE_041 (a
  test only where it guards real behaviour) and NFR-001 (no new tolerance).
- Current code: `src/runtime/next/runtime_bridge_composition.py:615-645`.
- The tests faking `StepContractExecutor.execute` all use `MagicMock` (no `Mock()`), and most
  already set real `invocation_ids` tuples; `MagicMock` still supports both attribute reads
  and iteration, so the production change does not require rewriting those fakes.
- The one test that must change:
  `tests/specify_cli/next/test_runtime_bridge_composition.py::test_dispatch_handles_non_sized_invocation_ids_and_returns_guard_failures`
  (`:641-676`). It asserts `emitted 0 invocation(s)` for `invocation_ids = object()`. Rewrite
  it to assert the contract while keeping its guard-failure coverage — do **not** delete it.

## Branch Strategy

- **Strategy**: completed changes merge back into `issue-6745-workaround-audit-and-removal`.
- **Planning base branch**: `issue-6745-workaround-audit-and-removal`
- **Merge target branch**: `issue-6745-workaround-audit-and-removal`

## Subtasks & Detailed Guidance

### Subtask T006 – Rewrite the tolerance test as a contract test

- **Purpose**: no test may keep the tolerance alive (FR-007).
- **Steps**: rename the test to describe the contract, e.g.
  `test_dispatch_logs_the_executor_invocation_count_and_returns_guard_failures`. Keep the
  guard-failure half exactly as it is (the guard failure is still returned, and logged). Replace
  `fake_result.invocation_ids = object()` with a real tuple
  (e.g. `("inv-001", "inv-002")`), and assert the log reports `emitted 2 invocation(s)`.
  Keep the assertion that fails if the guard failure is swallowed.
- **Files**: `tests/specify_cli/next/test_runtime_bridge_composition.py`.
- **Verification**: run it against the pre-change source to see it fail on the count
  (`emitted 2` vs `emitted 0`), then with T007 to see it pass.

### Subtask T007 – Read the executor result contract directly

- **Purpose**: remove the second authority on the result shape.
- **Steps**: replace the block above with

  ```python
  invocation_ids = result.invocation_ids
  logger.info(
      "composed %s/%s emitted %d invocation(s): %s",
      mission,
      action,
      len(invocation_ids),
      invocation_ids,
  )
  ```

  and `for step in result.steps:` / `unresolved = step.unresolved_candidates`. Delete the two
  "Defensive ``getattr`` … test mocks (MagicMock)" comments and say plainly that the executor's
  result type is the contract.
- **Files**: `src/runtime/next/runtime_bridge_composition.py`.
- **Do not**: touch the `except StepContractExecutionError` / `except Exception` pair above —
  they are the FR-009 surface and are documented as such.

### Subtask T008 – Focused verification

- **Steps**:
  - `uv run pytest tests/specify_cli/next/test_runtime_bridge_composition.py -q`
  - `uv run pytest tests/runtime/test_bridge_composition.py tests/specify_cli/mission_step_contracts/test_executor.py -q`
  - `uv run ruff check src/runtime/next/runtime_bridge_composition.py tests/specify_cli/next/test_runtime_bridge_composition.py`
  - `uv run mypy src/runtime/next/runtime_bridge_composition.py`
- **Never** run a full heavy suite.

## Definition of Done

- `grep -n "getattr(result" src/runtime/next/runtime_bridge_composition.py` returns nothing,
  and `grep -n "except TypeError" …` returns nothing.
- The rewritten test passes and still fails if the guard failure is swallowed.
- Focused suites, ruff and mypy green; no test deleted.

## Risks & Mitigations

- **A fake that returns a plain `Mock()`**: none exists today; if one appears later it fails
  loudly at the seam, which is the point.
- **Silent behaviour change**: with the real type the logged count is unchanged (it was already
  computed from `len(invocation_ids)`), so the only difference is that a non-sized value now
  raises instead of logging 0.

## Reviewer Guidance

- Confirm the FR-009 `except Exception` is untouched and still justified in its comment.
- Confirm the rewritten test still asserts the guard failure (its other half), so coverage did
  not shrink.
