---
work_package_id: WP03
title: Op-record appends take the lock
dependencies:
- WP01
requirement_refs:
- FR-009
planning_base_branch: issue-6603-6606-eventbridge-gate-and-locked-appends
merge_target_branch: issue-6603-6606-eventbridge-gate-and-locked-appends
branch_strategy: Planning artifacts for this mission were generated on issue-6603-6606-eventbridge-gate-and-locked-appends. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6603-6606-eventbridge-gate-and-locked-appends unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-eventbridge-gate-and-locked-appends-01M5T0TN
base_commit: 94fd6e68b452a12dc484129492fc6906a4f51fa9
created_at: '2026-10-25T18:41:44.587416+00:00'
subtasks:
- T009
- T010
- T011
history:
- at: '2026-10-25T17:30:00Z'
  actor: claude
  note: Created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/invocation/
create_intent:
- tests/specify_cli/invocation/test_writer_locked_appends.py
execution_mode: code_change
owned_files:
- src/specify_cli/invocation/writer.py
- tests/specify_cli/invocation/test_writer_locked_appends.py
role: implementer
tags: []
tracker_refs: []
---

# WP03: Op-record appends take the lock

## ⚡ Do This First: Load Agent Profile

Load the assigned profile with the `/spk-charter-profile-load` skill (`python-pedro`) before reading anything else, then run `spec-kitty charter context --action implement`.

## Branch Strategy

Planning base and merge target: `issue-6603-6606-eventbridge-gate-and-locked-appends`. Execution worktrees are allocated per computed lane from `lanes.json`; run
`spec-kitty agent action implement WP03 --agent claude --mission eventbridge-gate-and-locked-appends-01M5T0TN`. Never choose a base branch by hand.

## Objective

FR-009: the `kitty-ops` index, the closure spine and the per-Op appends take the same lock. Keep no-follow, the 0o600 mode and the started-event identity check, which now runs under the lock.

## Subtasks

### T009 — Red-first

`tests/specify_cli/invocation/test_writer_locked_appends.py`:
- A torn per-Op file: `write_completed` and `append_correlation_link` refuse and the file is unchanged. Today a torn tail fails JSON parsing as `InvocationError`. Keep the same exception type for the parse failure, and assert it is byte-identical.
- A torn `op-closures.jsonl`: `append_op_closure` raises `EventLogTornTailError`, and the file is unchanged.
- A torn index: `_append_to_index` swallows the error, and the index is unchanged (it was extended before).
- While `event_log_lock(<file>)` is held, an append with a short timeout refuses.
- A symlink is still refused.

### T010 — `_append_line_no_follow`

It becomes `append_event_log_lines(path, [line.rstrip("\n")], no_follow=True, mode=0o600)`. Map `EventLogSymlinkError` the way a symlink `OSError` was handled before. Callers pass the line without the newline, so remove `+ "\n"` at the two call sites.

### T011 — Validated appends

Replace `_validated_append_handle` with a helper `_append_validated(path, invocation_id, line, *, refuse_if_completed=False)`:
- It calls `append_event_log_lines(path, [line], lock_anchor=self._dir, create=False, no_follow=True, precondition=check)`. The family anchor means one lock file serves every per-Op file (review finding 10). A torn tail maps to `InvocationError("Invocation record is unreadable")`, as before.
- `check(existing: bytes)` parses the rows and raises `InvocationError` or `AlreadyClosedError` exactly as today.
- `FileNotFoundError` maps to `InvocationError("Invocation record not found")`, and other `OSError`s to `InvocationWriteError`, matching today's messages.
- Keep the symlink refusal from `invocation_path`.

## Definition of Done

`tests/specify_cli/invocation/` and `tests/invocation*` pass. `#6564`'s refuse-before-writing tests (`grep -rl "invocation.writer" tests`) pass.
