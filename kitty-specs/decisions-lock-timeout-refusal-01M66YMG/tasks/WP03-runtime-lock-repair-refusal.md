---
work_package_id: WP03
title: Runtime-lock repair refuses a busy decisions lock
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-005
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-6763-decisions-lock-timeout-refusal
merge_target_branch: issue-6763-decisions-lock-timeout-refusal
branch_strategy: Planning artifacts for this mission were generated on issue-6763-decisions-lock-timeout-refusal. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6763-decisions-lock-timeout-refusal unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-decisions-lock-timeout-refusal-01M66YMG
base_commit: f7407d91cc4c20c83a80b5631214f3c23aa92ced
created_at: '2026-10-30T19:31:15.576809+00:00'
subtasks:
- T010
- T011
- T012
- T013
phase: Phase 3 - Runtime-lock repair refusal
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty tasks/generated
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/decision.py
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/decision.py
- tests/integration/test_owned_decision_runtime_lock.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – `agent decision repair-runtime-lock` refuses a busy decisions lock

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the
frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before
starting. Address every feedback item before declaring the work complete.

---

## Objectives & Success Criteria

- `spec-kitty agent decision repair-runtime-lock --mission <m> --owned-checkout <path>` with
  the decisions lock held prints exactly one JSON document
  `{"status": "error", "code": "DECISION_LOCK_TIMEOUT", "message": "<seam message>"}` on
  stdout, exits 1, and leaves the owned checkout unchanged (HEAD, index, untracked files and
  the lock inode).
- A free lock behaves exactly as today: the repair still untracks the lock, provisions the
  ignore rule and commits.
- The C2 owned-refusal path is untouched.

Covers [spec.md](../spec.md) FR-001 and FR-005; reproduction in [quickstart.md](../quickstart.md) §3.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6763.
- `decision.py::_repair_runtime_lock` takes the lock late, after
  `_runtime_lock_preflight`, `preflight_commit` and the `dry_run`/no-change short-circuits —
  so a refusal at the acquire still writes nothing. Preserve that ordering.
- `_echo_runtime_lock_failure` renders `{status, code, message}` on stdout and exits 1; it
  derives `code` from `_runtime_lock_error_code(exc)`. ADR
  `docs/adr/4.x/2026-10-27-2-owned-refusals-use-the-c2-error-contract.md` (decision 7) pins
  that this verb's non-refusal failures KEEP that shape; only the C2 owned refusal moved.
- The code must be the seam's own `DECISION_LOCK_TIMEOUT`, not `RUNTIME_LOCK_REPAIR_FAILED`,
  so a script can match one code across all three commands (spec NFR-003).

## Branch Strategy

- **Strategy**: `lanes` mission on branch `issue-6763-decisions-lock-timeout-refusal`; merge target is the same branch.
- **Planning base branch**: `issue-6763-decisions-lock-timeout-refusal`
- **Merge target branch**: `issue-6763-decisions-lock-timeout-refusal`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not edit by hand.

## Subtasks & Detailed Guidance

### Subtask T010 – Red-first integration test

- **Purpose**: prove the escape through the real verb, on the existing owned-checkout
  fixture that owns this contract.
- **Steps**:
  1. In `tests/integration/test_owned_decision_runtime_lock.py`, add a test using the existing
     `owned_checkouts` fixture and the module's `seed()`, `invoke()` and `snapshot()` helpers
     (state `"tracked"` so the repair would otherwise change something).
  2. `monkeypatch.setattr("specify_cli.decisions.service._LOCK_ACQUIRE_TIMEOUT_S", 0.2)` and
     hold `seed()`'s returned lock path with
     `machine_file_lock(lock, blocking=True, timeout_s=5)` while invoking the verb.
  3. Assert: `result.exit_code == 1`; `json.loads(result.stdout)["code"] == "DECISION_LOCK_TIMEOUT"`;
     `"retry"` in the message; `snapshot(c.owned_root) == before`; the lock inode is unchanged.
  4. Record the pre-fix failure (`LockAcquireTimeout` escaping the command) for the PR body.
- **Files**: `tests/integration/test_owned_decision_runtime_lock.py`
- **Notes**: the module is `integration` + `git_repo`; it is the right tier for a verb that
  commits. Keep the runtime of the new test small (one repo fixture, no parametrisation).

### Subtask T011 – Route the acquisition through the seam

- **Steps**: in `decision.py::_repair_runtime_lock`, replace the raw
  `machine_file_lock(lock, blocking=True, timeout_s=_LOCK_ACQUIRE_TIMEOUT_S)` with
  `_decisions_lock(lock, timeout_s=_LOCK_ACQUIRE_TIMEOUT_S, mission_slug=owned.mission_slug, decision_id=None)`
  imported from `specify_cli.decisions.service` (function-local, matching the module's cold
  import discipline). Extend the function's docstring to name the refusal.
- **Files**: `src/specify_cli/cli/commands/decision.py`
- **Notes**: leave the preflight/`dry_run` short-circuits exactly where they are.

### Subtask T012 – Map the seam's error to its own code

- **Steps**: extend `_runtime_lock_error_code(exc)` so a
  `specify_cli.decisions.service.DecisionError` returns `exc.code.value` before the existing
  `_RuntimeLockRaceError` / `ValueError` / fallback branches. `DecisionError` is already
  imported at module scope. Update the helper's docstring.
- **Files**: `src/specify_cli/cli/commands/decision.py`
- **Notes**: do not add a per-command `except DecisionError` that duplicates the renderer; the
  existing `except Exception` arm already routes to `_echo_runtime_lock_failure`, and the code
  mapping is the one place that decides the code. (If you prefer an explicit arm for
  readability, it must still call `_echo_runtime_lock_failure` and must not change the shape.)

### Subtask T013 – Positive control

- **Purpose**: prove the refusal is not a verb that always fails, on the same fixture.
- **Steps**: with no held lock and state `"tracked"`, assert the verb exits 0, the lock leaves
  the index, and the ignore rule is provisioned; then run the whole existing module
  (`tests/integration/test_owned_decision_runtime_lock.py`) green.
- **Files**: `tests/integration/test_owned_decision_runtime_lock.py`
- **Notes**: the module's `test_repair_preserves_payload_inode_and_other_roots` already covers
  most of this; add the explicit same-fixture row only if the new test's fixture differs.

## Test Strategy

- `uv run pytest tests/integration/test_owned_decision_runtime_lock.py -q` (integration tier;
  no full heavy suite).
- `uv run pytest tests/specify_cli/cli/test_decision_command_shape_consistency.py tests/specify_cli/cli/commands/test_decision.py -q`
- `uv run ruff check src/specify_cli/cli/commands/decision.py`
- `uv run mypy src/specify_cli/cli/commands/decision.py`
- Capture the pre-fix T010 failure for the PR body.

## Risks & Mitigations

- Committing a partial repair → the snapshot assertion covers HEAD, index, untracked files and
  the lock inode.
- Changing the C2 owned-refusal shape → only `_runtime_lock_error_code` changes; the
  `except ActionContextError` arm stays.
- `--dry-run` must never report a timeout → it returns before the acquire; assert nothing
  changed there if you touch the ordering.

## Review Guidance

- Confirm the acquired lock is the seam, not `machine_file_lock`, and that the preflight still
  runs before any acquire.
- Confirm the emitted code is `DECISION_LOCK_TIMEOUT` and the shape is `{status, code, message}`.
- Confirm the refusal leaves the checkout byte-identical, and that a free lock still repairs.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
