---
work_package_id: WP02
title: Owned next refuses a busy decisions lock
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-004
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- SC-001
- SC-002
planning_base_branch: issue-6763-decisions-lock-timeout-refusal
merge_target_branch: issue-6763-decisions-lock-timeout-refusal
branch_strategy: Planning artifacts for this mission were generated on issue-6763-decisions-lock-timeout-refusal. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6763-decisions-lock-timeout-refusal unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-decisions-lock-timeout-refusal-01M66YMG
base_commit: f7407d91cc4c20c83a80b5631214f3c23aa92ced
created_at: '2026-10-30T19:18:14.047675+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 2 - Owned next refusal
history:
- at: '2026-10-30T17:50:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/next_cmd.py
create_intent:
- tests/specify_cli/cli/commands/test_next_owned_lock_timeout.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/next_cmd.py
- tests/specify_cli/cli/commands/test_next_owned_lock_timeout.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Owned `next` refuses a busy decisions lock

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

- An owned `spec-kitty next --owned-checkout <path>` whose commit step cannot acquire the
  decisions lock reports a lock-timeout refusal in `next`'s own error contract — human mode
  `Error:` + `Next:` on stderr, `--json` mode one document with `result: "error"`,
  `error_code: "DECISION_LOCK_TIMEOUT"`, the lock path, the wait and a retry `next_step` —
  and exits 1. No traceback reaches the agent loop.
- A free lock behaves exactly as today: the advancement is committed and the decision printed.

Covers [spec.md](../spec.md) FR-001 and FR-004; reproduction in [quickstart.md](../quickstart.md) §2.

## Context & Constraints

- Issue: spec-kitty/spec-kitty#6763.
- `next_cmd._commit_owned_next_mutations(owned)` takes `_decisions_lock_path(owned.mission_dir)`
  through a `nullcontext`-vs-`machine_file_lock` ternary, because the lock file only exists
  once the decisions service created it. That "no lock file yet → nothing to guard" case must
  be preserved.
- `next` renders typed failures with a dual helper pair (JSON on stdout,
  `Error:`/`Next:` on stderr): see `_emit_meta_read_error` and `_emit_read_path_error`. The
  JSON envelope keys are `result`, `error_code`, `error`, `next_step` and
  `spec_kitty_version` (plus payload-specific keys).
- `_commit_owned_next_mutations` runs after the advancement and its lifecycle record are
  durable and before `_print_decision`. A refusal here means the ordered commit did not
  happen, so the message must say the retry is safe.

## Branch Strategy

- **Strategy**: `lanes` mission on branch `issue-6763-decisions-lock-timeout-refusal`; merge target is the same branch.
- **Planning base branch**: `issue-6763-decisions-lock-timeout-refusal`
- **Merge target branch**: `issue-6763-decisions-lock-timeout-refusal`

> Populated by `spec-kitty agent mission finalize-tasks`. Do not edit by hand.

## Subtasks & Detailed Guidance

### Subtask T006 – Red-first test for owned `next`

- **Purpose**: prove the escape through `next`'s own dispatch before fixing it.
- **Steps**:
  1. Create `tests/specify_cli/cli/commands/test_next_owned_lock_timeout.py` (`pytest.mark.fast`),
     reusing the `_fact(tmp_path)` / `_boom()` construction style of
     `tests/specify_cli/cli/commands/test_next_owned_fact.py`.
  2. Create the lock: `lock = _decisions_lock_path(fact.mission_dir)`, `lock.parent.mkdir()`,
     `lock.write_bytes(b"")` so `runtime_lock.exists()` is true.
  3. `monkeypatch.setattr("specify_cli.decisions.service._LOCK_ACQUIRE_TIMEOUT_S", 0.2)`;
     hold the lock with `machine_file_lock` while driving
     `next_cmd._dispatch_advancing_mode("claude", "unit-owned-mission", "success", fact.repository_root, json_output=True, answered_id=None, answer=None, owned=fact)`
     with `_pair_previous_lifecycle_record`, `decide_next`, `_emit_mission_next_invoked` and
     `_write_issuance_lifecycle_record` monkeypatched to no-ops that return a stub decision
     object (`kind="step"`).
  4. Assert: `typer.Exit` with `code == 1`; captured stdout parses as one JSON document with
     `result == "error"` and `error_code == "DECISION_LOCK_TIMEOUT"`; `next_step` mentions
     retry; `_print_decision` was never called (patch it and assert not called).
  5. Record the pre-fix failure (`LockAcquireTimeout` propagates, no JSON) for the PR body.
- **Files**: `tests/specify_cli/cli/commands/test_next_owned_lock_timeout.py`
- **Parallel?**: no.
- **Notes**: do not drive the full integration mission loop — this WP is about the dispatch
  seam. `capsys` is enough; no worktree needed.

### Subtask T007 – Route the acquisition through the seam

- **Steps**: in `_commit_owned_next_mutations`, keep the `runtime_lock.exists()` guard and
  replace the raw `machine_file_lock(...)` with
  `_decisions_lock(runtime_lock, timeout_s=_LOCK_ACQUIRE_TIMEOUT_S, mission_slug=owned.mission_slug, decision_id=None)`
  imported from `specify_cli.decisions.service`. Drop the now-unneeded local import of
  `machine_file_lock`.
- **Files**: `src/specify_cli/cli/commands/next_cmd.py`
- **Notes**: the absent-lock branch stays `nullcontext()`; a `DecisionError` must be able to
  escape this function so the caller can render it (do not catch here).

### Subtask T008 – Render the `next` refusal

- **Steps**:
  1. Add `_emit_decisions_lock_timeout(exc: DecisionError, json_output: bool) -> None` next to
     `_emit_meta_read_error`; JSON: `{"result": "error", "error_code": exc.code.value,
     "error": str(exc), "lock_path": exc.details.get("lock_path"),
     "timeout_seconds": exc.details.get("timeout_seconds"),
     "next_step": "Retry the command; the advancement is already recorded and nothing was
     left half-committed.", "spec_kitty_version": __version__}`. Human: `Error: {exc}` and
     `  Next: {next_step}` to stderr.
  2. In `_dispatch_advancing_mode`, wrap ONLY `_commit_owned_next_mutations(owned)` in
     `except DecisionError as _exc: _emit_decisions_lock_timeout(_exc, json_output); raise typer.Exit(1) from _exc`.
  3. Update `_commit_owned_next_mutations`'s docstring to name the refusal.
- **Files**: `src/specify_cli/cli/commands/next_cmd.py`
- **Notes**: catch `DecisionError` only. Other commit failures (`RuntimeError` from
  `safe_commit`) keep propagating as today. Re-run T006 and
  `tests/specify_cli/cli/commands/test_next_owned_commit_guard.py` + `test_next_owned_fact.py`.

### Subtask T009 – Positive control on the same fixture

- **Purpose**: the refusal assertion must not be satisfiable by a `next` that always fails.
- **Steps**: with the same fact and no held lock (lock file still present), assert
  `_commit_owned_next_mutations(fact)` reaches `safe_commit` (patch and record) and the
  dispatch returns a decision and does not raise. Keep it in the same module as T006 so both
  rows run on one fixture.
- **Files**: `tests/specify_cli/cli/commands/test_next_owned_lock_timeout.py`
- **Notes**: this is the same-fixture positive control required by the
  `acceptance-criteria-non-vacuity` tactic.

## Test Strategy

- `uv run pytest tests/specify_cli/cli/commands/test_next_owned_lock_timeout.py tests/specify_cli/cli/commands/test_next_owned_commit_guard.py tests/specify_cli/cli/commands/test_next_owned_fact.py -q`
- `uv run ruff check src/specify_cli/cli/commands/next_cmd.py`
- `uv run mypy src/specify_cli/cli/commands/next_cmd.py`
- Capture the pre-fix T006 failure for the PR body.

## Risks & Mitigations

- Printing a decision after the refusal → the catch wraps only the commit call, before
  `_print_decision`.
- Regressing the lazy-import footprint (`tests/specify_cli/next/test_next_import_footprint.py`)
  → keep the new imports function-local in `_commit_owned_next_mutations`.
- A refusal after durable state → the message must not claim nothing happened.

## Review Guidance

- Confirm only the commit step is translated and no other `next` failure changed shape.
- Confirm the JSON and human messages both name the lock and say retry is safe.
- Confirm the absent-lock (no file) path is unchanged.

## Progress & Status

- **Record a progress note**: `spec-kitty agent tasks add-history WP02 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP02 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
