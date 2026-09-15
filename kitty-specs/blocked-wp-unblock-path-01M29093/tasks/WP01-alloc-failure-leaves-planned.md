---
work_package_id: WP01
title: 'F-50: allocation failure leaves the work package recoverable (planned)'
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-004
planning_base_branch: fix/3937-blocked-wp-unblock
merge_target_branch: fix/3937-blocked-wp-unblock
branch_strategy: Planning artifacts for this mission were generated on fix/3937-blocked-wp-unblock. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/3937-blocked-wp-unblock unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-blocked-wp-unblock-path-01M29093
base_commit: 9c8d6ce543357dde7e8ad547382c5f7dc4090e99
created_at: '2026-09-11T20:08:25.068643+00:00'
subtasks:
- T001
- T002
- T003
- T004
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/implement.py
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/implement.py
- tests/integration/test_status_emit_on_alloc_failure.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#3937'
---

# WP01: F-50 — allocation failure leaves the work package recoverable

## ⚡ Do This First: Load Agent Profile

Use `/ad-hoc-profile-load` (alias for `spk-doctrine-profile-load`) BEFORE reading the rest of this prompt.

- Profile: `python-pedro`
- Role: `implementer`
- Agent/tool: `claude`

Load the resolver-backed profile + action context, apply its initialization, directives, tactics, and the reviewer-handoff boundary. If structured governance is empty, disclose it and read the binding charter/profile sources explicitly — do not invent activation.

## Objective

When `spec-kitty implement WP##` hits a workspace-allocation failure (a dependency-lane merge conflict, or a planning-commit merge conflict), the work package must remain in `planned` — the CLI must NOT manufacture a `planned → blocked` transition — and it must print the exception's actionable resolution step. This closes finding F-50 of #3937.

## Root cause (verified)

`src/specify_cli/cli/commands/implement.py`: `create_lane_workspace` runs (~line 1952) BEFORE the claim transition (~line 1966). So when allocation raises `DependencyLaneMergeConflictError` (`src/specify_cli/lanes/worktree_allocator.py:90`, `next_step` at :89) or `PlanningCommitMergeConflictError` (~:150-181), the WP is still `planned`. The `except Exception as exc:` handler (~:1993-1998) calls `_emit_blocked_on_alloc_failure` (~:1445-1476), which emits `planned → blocked` — a state whose only legal exits are `{in_progress, canceled}` (`wp_state.py:541-542`), and which `start_implementation_status` (`work_package_lifecycle.py`) has no branch for, so a re-run hits the generic reject at :256. The allocator self-cleans (abort + `reset --hard`, no `lanes.json` write), so leaving the WP `planned` strands nothing; the persisted worktree is the allocator's reentrancy vehicle. The already-shipped orchestrator-api path (`orchestrator_api/commands.py:1268-1303`) never emits blocked — this change brings the CLI to parity.

## Subtasks

### T001 — RED-first ATDD: dependency-lane conflict leaves `planned`, no blocked event
Rewrite the bug-encoding assertion in `tests/integration/test_status_emit_on_alloc_failure.py` (currently asserts the transition list equals `[("planned","blocked")]` around lines 189/192, and its docstring documents the OLD behavior). The rewritten test is the F-50 acceptance test:
- Arrange a WP in `planned` and a `create_lane_workspace` that raises `DependencyLaneMergeConflictError` (with a real `next_step`).
- Assert (observable STATE, not message substrings):
  - the WP's reduced lane after the failed `implement` is `planned`;
  - NO event with `from_lane="planned", to_lane="blocked"` was appended for this WP;
  - the printed output contains the exception's `next_step` text.
- This test MUST be RED against the current code and committed as the FIRST commit of the lane (ATDD, charter C-011).

### T002 [P] — RED-first ATDD: planning-commit conflict path + clean re-run
- Add a sibling case for `PlanningCommitMergeConflictError`: allocation failure likewise leaves the WP `planned` with `next_step` surfaced and no blocked event.
- Add a case proving a re-run after the failure does NOT acquire a `review-cycle://` feedback pointer (Fix mode is not triggered) — i.e. recovery needs no fabricated review artifact.

### T003 — Implement the fix in `implement.py`
- In the allocation-failure `except` handler, STOP calling `_emit_blocked_on_alloc_failure` (remove the manufactured `planned → blocked` emit). Leave the WP in `planned`.
- Print the exception's `next_step` (for both `DependencyLaneMergeConflictError` and `PlanningCommitMergeConflictError`) as the actionable remediation — not a generic "re-run the implement command".
- If `_emit_blocked_on_alloc_failure` becomes dead after this, remove it (campsite) and drop any now-dead import; do not leave an unused helper.
- Preserve the non-zero exit (`typer.Exit(1)`), the printed "Workspace allocation failed: …" line, and behavior for the non-`planned` guard path.

### T004 — Validate
- `PWHEADLESS=1 .venv/bin/python -m pytest tests/integration/test_status_emit_on_alloc_failure.py tests/agent/test_orchestrator_lane_allocation.py tests/agent/cli/commands/test_implement_preflight.py -q`
- `.venv/bin/mypy --strict` on the changed module surface and `.venv/bin/ruff check` + `.venv/bin/ruff format --check` on changed files — zero new issues, no new suppressions.

## Definition of Done
- FR-001/FR-002/FR-003 satisfied; T001/T002 were RED-first then GREEN; no `planned→blocked` event on allocation failure; `next_step` surfaced for both conflict paths; targeted tests + mypy + ruff green.
- No `blocked → in_progress` recovery driver added (C-001); this WP does not touch the FSM or the move-task guards (that is WP02).

## Reviewer guidance (reviewer-renata)
- Verify the acceptance test pins STATE (lane unchanged + absent blocked event), not message text — a cosmetic message change alone must not pass it.
- Confirm both conflict codepaths are covered and `_emit_blocked_on_alloc_failure` is genuinely no longer reached (dead-code removed, not merely skipped).
- Confirm red→green: the rewritten test was RED on `planning_base_branch` and GREEN on the final commit.
