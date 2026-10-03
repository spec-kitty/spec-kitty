---
work_package_id: WP03
title: Teardown deletes the coordination branch only at the checked tip (#5570)
dependencies:
- WP02
requirement_refs:
- FR-005
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-004
- SC-001
- SC-002
planning_base_branch: kitty/rc5-consolidate-regressions
merge_target_branch: kitty/rc5-consolidate-regressions
branch_strategy: Planning artifacts for this mission were generated on kitty/rc5-consolidate-regressions. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/rc5-consolidate-regressions unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rc5-consolidate-regressions-01M4189Z
base_commit: fe5ea1df9fbba9fd6906a10557cff1f521e46d1f
created_at: '2026-10-03T17:10:44.452603+00:00'
subtasks:
- T010
- T011
- T012
- T013
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/
create_intent:
- tests/git/test_delete_branch_ref.py
- tests/terminus/test_repro_5570.py
execution_mode: code_change
model: claude-sonnet-5-5-high
owned_files:
- src/specify_cli/git/ref_advance.py
- src/specify_cli/coordination/teardown.py
- tests/coordination/test_projection_teardown.py
- tests/git/test_delete_branch_ref.py
- tests/terminus/test_repro_5570.py
role: implementer
tags: []
tracker_refs: []
---

# Work Package Prompt: WP03 – Teardown deletes the coordination branch only at the checked tip (#5570)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

Implementation command: `spec-kitty agent action implement WP03 --agent claude`

## Objective

Coordination teardown must delete the mission/coordination branch only if it still points at the
tip the teardown gate approved. A status commit landing after the gate and before deletion must
survive, and the command must exit non-zero with recovery advice.

## Context

> **Ownership note (executor.py).** `src/specify_cli/consolidation/executor.py` is owned by WP02
> (finalize-tasks forbids overlapping ownership). This WP depends on WP02 and may edit ONLY
> `_delete_mission_branch`, `_teardown_coordination_triple` and the expected-tip plumbing in that file, under the charter's ownership-map leeway. Any other executor.py
> change needs the orchestrator's approval first.

Read `research.md` (#5570) and `plan.md` (IC-03).

- Gate: `_enforce_projection_teardown_gate` (`coordination/teardown.py:185-207`, single
  `rev-parse` via `_current_coord_ref_sha` ~134-148); teardown writes the retrospective (~354)
  and removes the worktree (~362).
- Delete: `_delete_mission_branch` (`consolidation/executor.py:2863-2897`) runs an unconditional
  `git branch -D` (~2888). `_teardown_coordination_triple` (~2967-2996); the expected tip comes
  from `coord_tip_after_projection` (~1619, set into the gate ~2943). Non-coordination missions
  reach `_delete_mission_branch` at ~3061.
- **No CAS delete helper exists** — `delete_bookkeeping_ref` (`git/ref_advance.py:793-803`) is
  2-arg and bookkeeping-only. Add `delete_branch_ref(repo, ref, expected_sha)` in
  `git/ref_advance.py` beside `advance_branch_ref` / `restore_branch_ref`, implemented as
  `git update-ref -d refs/heads/<b> <expected_sha>`; raise a typed error on mismatch.
- Never restore on mismatch outside `rollback_to_snapshot` (AST pin
  `tests/consolidation/test_single_rollback_authority.py`). On mismatch: keep the branch, keep the
  coordination marker (skip the flatten), raise `CoordinationTeardownError` (or the existing
  teardown error type) so the CLI exits non-zero with advice naming the branch and the moved SHA.
- Executor.py is shared with WP02 and WP04: touch only `_delete_mission_branch`,
  `_teardown_coordination_triple` and the expected-tip plumbing.
- Out of scope: `orchestrator_api/commands.py:990` (no gate; pre-existing documented limitation
  — the orchestrator files a follow-up issue). Lane-branch deletes (~3164) out of scope.

> Post-tasks squad: reuse the existing `CoordinationTeardownError` (`consolidation/executor.py:202`, already caught and rendered non-zero at `cli/commands/consolidate.py:716`); do not add a new error type, so `consolidate.py` stays untouched. For T010, the injection wrapper must call the real `_destroy_coordination_worktree` (a concurrency-injection seam, not a behaviour mock).

### Subtask T010: Red-first window test (separate commit)

- **Steps**: in `tests/coordination/test_projection_teardown.py` (real git helpers `_init_repo`,
  `_make_coord_branch`, `_append_coord_commit`) add a test driving `_teardown_coordination_triple`
  (or the teardown entry the CLI uses) where only
  `coordination.teardown._destroy_coordination_worktree` is wrapped to first append a commit to
  the coordination branch, then call the original. Assert ideal: error raised, branch still exists
  at the injected commit, marker kept. Add an end-to-end variant in `tests/terminus/test_repro_5570.py`
  through `spec-kitty consolidate` with a real `agent status emit … --force` commit in the window
  if the terminus fixtures allow it without mocking product code beyond that one seam.
- **Validation**: RED on base; commit alone (`test(WP03): red-first #5570`).

### Subtask T011: `delete_branch_ref` CAS helper

- **Steps**: implement + unit tests in `tests/git/test_delete_branch_ref.py`: deletes at expected
  tip; refuses and leaves the ref on mismatch; refuses on missing ref (define the semantics).

### Subtask T012: Wire teardown to the CAS delete

- **Steps**: pass the gated tip into `_delete_mission_branch`; replace `branch -D`; surface the
  refusal as a non-zero CLI outcome with recovery advice; non-coordination path uses the tip read
  at the same phase so behaviour is unchanged when nothing moved.
- **Validation**: T010 green; positive control (unmoved branch is deleted) green.

### Subtask T013: Regression sweep

- **Steps**: `tests/coordination/`, `tests/terminus/test_repro_4981.py`,
  `tests/consolidation/test_single_rollback_authority.py`, consolidate abort/teardown tests.

## Definition of Done

- Window test red on base, green on tip; positive control green; AST pin green.
- Lint/format/mypy clean; subtasks marked done.

## Risks

- Windows/git quirks of `update-ref -d` with an expected value on packed refs — test on packed refs too.

## Reviewer Guidance

- Verify the delete is atomic CAS and failure is loud (non-zero) and non-destructive.
