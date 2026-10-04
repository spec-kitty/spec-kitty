---
work_package_id: WP01
title: Status-surface guard for a failed finalize-tasks run
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
- NFR-001
- NFR-002
- NFR-003
- C-001
- C-002
- C-003
- C-004
planning_base_branch: kitty/fix-5641-finalize-tasks-atomic-status
merge_target_branch: kitty/fix-5641-finalize-tasks-atomic-status
branch_strategy: Planning artifacts for this mission were generated on kitty/fix-5641-finalize-tasks-atomic-status. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into kitty/fix-5641-finalize-tasks-atomic-status unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Fix
history:
- at: '2026-10-04T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/agent/
create_intent:
- src/specify_cli/cli/commands/agent/finalize_status_surface.py
execution_mode: code_change
owned_files:
- src/specify_cli/cli/commands/agent/finalize_status_surface.py
- src/specify_cli/cli/commands/agent/mission_finalize.py
- tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Status-surface guard for a failed finalize-tasks run

## Objectives & Success Criteria

- The #5641 reproduction `test_final_commit_failure_leaves_every_branch_and_checkout_as_found` passes for `coord`, `lanes_with_coord`, `lanes` and `single_branch` with its `regression` marker removed (SC-001).
- A foreign commit on the status surface survives a failed run and the output names the branch and the commits left behind; exit non-zero (SC-002).
- Every other test in `test_finalize_atomicity.py` and the owned finalize suites stay green (SC-004).

## Context & Constraints

- Read `plan.md` and `research/code-grounding.md` first.
- The ref move goes through `specify_cli.git.ref_advance.restore_branch_ref` with the default `resync_checkouts=False`. `resync_checkouts=True` is reserved to `consolidation/rollback.py` (gate `tests/consolidation/test_single_rollback_authority.py`).
- The index is restored with `git read-tree <captured tree>`, as in `core/mission_creation.py`. Add no new `reset --hard` (gate `tests/architectural/test_destructive_op_routing.py`) and no path-listing argv (gate `tests/architectural/test_git_path_listing_owner.py`).
- Byte restores reuse `_snapshot_mission_write_scope` / `_restore_mission_write_scope`.
- Do not touch `consolidation/executor.py`, `pytest.ini`, `tests/conftest.py` or `tests/_support/p0_repro.py`.
- Keep the original error output and exit code. The left-over-commit report is an additional note (`{"warning": ...}` in JSON mode, a yellow line in text mode), in the same style as `_report_target_branch_revert_failure`.

## Subtasks & Detailed Guidance

### Subtask T001 – the guard module
- **Steps**: dataclass `StatusSurfaceGuard`:
  - `capture(status_dir)` resolves the checkout root (`git rev-parse --show-toplevel`), the branch (`git symbolic-ref -q HEAD`), the tip and `git write-tree`.
  - `record_tip_after()` reads the tip again.
  - `restore(repo_root)` returns `True` when the ref was restored (or never moved), and otherwise a report of the commits left.
- An unguardable surface (a detached HEAD, a git error) yields a report rather than a guess.

### Subtask T002 – wiring
- Capture before `_emit_local_canonical_events`; record the tip in a `finally` around the status writes.
- In both `except` arms, when `not commit_landed.landed`:
  - restore the Mission directory bytes (unchanged);
  - then the guard;
  - then, if the guard restored and the status dir lies outside the Mission directory, the status-dir bytes.

### Subtask T003 – one authority
- Remove `_capture_owned_head`, `_restore_owned_head`, `owned_head_before` and its dataclass field. The guard covers P's branch for owned runs.

### Subtask T004 – tests
- Un-mark the reproduction and update its docstring to a guard.
- Add one test: a foreign commit lands on the status surface's branch after the seeds (inside the failing final commit), and the run leaves it and reports the left-over commits.

### Subtask T005 – truth in the comment
- Rewrite the COVERED / NOT COVERED comment so it states what a failed run now restores and what remains (the non-owned `.kittify/derived/<slug>` view; a materialized coordination worktree that did not exist before the run).

## Test Strategy

- `PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/specify_cli/cli/commands/agent/test_finalize_atomicity.py`
- The owned finalize suites: `tests/integration/test_owned_lifecycle_acceptance_finalize.py` and the other test files that reference finalize under owned checkouts.
- Named gates: `tests/architectural/test_destructive_op_routing.py`, `tests/consolidation/test_single_rollback_authority.py`, `tests/architectural/test_git_path_listing_owner.py`, `tests/architectural/test_status_events_writes_gate.py`, `tests/architectural/test_status_unsafe_allowlist.py`, `tests/architectural/test_untrusted_path_containment.py`, `tests/architectural/test_issue_named_test_census.py`.
- `ruff check`, `ruff format --check --force-exclude`, `mypy` on the changed files.

## Risks & Mitigations

- A partial bootstrap: the `finally` records the tip even when a seed raises.
- A coordination worktree diverged by a byte restore after a refused ref restore: restore its bytes only after a successful ref restore.

## Review Guidance

- Revert `src/` to the base and confirm the un-marked reproduction and the foreign-commit test go red.
- Check that no gate allowlist grew.

## Activity Log
