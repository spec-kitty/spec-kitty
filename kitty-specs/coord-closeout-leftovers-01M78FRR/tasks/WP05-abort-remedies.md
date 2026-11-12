---
work_package_id: WP05
title: An --abort refusal completes the abort (#7600)
dependencies:
- WP01
requirement_refs:
- FR-011
- FR-012
- SC-004
planning_base_branch: fix/7598-coord-closeout-leftovers
merge_target_branch: fix/7598-coord-closeout-leftovers
branch_strategy: Planning artifacts for this mission were generated on fix/7598-coord-closeout-leftovers. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7598-coord-closeout-leftovers unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
phase: Phase 2 - Closeout fixes
history:
- at: '2026-11-12T18:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/rollback.py
create_intent:
- tests/consolidation/test_abort_remedies.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/git/ref_advance.py
- src/specify_cli/consolidation/rollback.py
- src/specify_cli/cli/commands/consolidate.py
- src/specify_cli/cli/commands/agent/workflow.py
- tests/consolidation/test_abort_remedies.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP05 – An `--abort` refusal completes the abort (#7600)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile in the frontmatter before reading further.

- **Profile**: `python-pedro` · **Role**: `implementer` · **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` via `spec-kitty agent tasks status`; address all feedback; record progress with `add-history`.

---

## Objectives & Success Criteria

Operator ruling Decision `01M78G5ZPT2R106TZ26HB4EG5W`: neutral `RefAdvanceDirtyWorktreeError`
text; each caller appends its own next step (`--abort`, `--resume`, review).

Done when (FR-011, FR-012, SC-004; contract `contracts/cli-refusals.md`):
- `consolidate --abort` that cannot restore a branch because a checkout is dirty names the checkout and says commit or stash, then re-run `spec-kitty consolidate --abort`. No `--resume`.
- A branch moved by another actor → remedy names `spec-kitty consolidate --abort --release-branch <b> --release-reason "..."`.
- Coordination checkout not resynced during `--abort` → commit or stash in the coordination worktree, then re-run `--abort`.
- Kept verified landing (`refused_verified_landing`) → says the landing is kept and offers `spec-kitty consolidate --resume` as the way to finish teardown, labelled as such.
- The review lane fast-forward (`cli/commands/agent/workflow.py:2255-2256`) no longer prints consolidate advice.
- The fresh-run / `--resume` rollback door keeps a working remedy (`--resume` there is correct).

## Context & Constraints

Map (`research/code-grounding.md` §4, §7):
- `git/ref_advance.py:318-320` bakes "then resume the consolidation (`spec-kitty consolidate --resume`)" into `RefAdvanceDirtyWorktreeError`, raised by `advance_branch_ref` / `restore_branch_ref` (imported by ~30 modules: implement, mission create, topology settlement, finalize, lane_tip, commit_helpers, orchestrator_api…).
- `rollback.py:774` folds `str(exc)` into the NOT_RESTORED reason on both the door and `--abort`; `rollback.py:135-139` `_COORD_RESYNC_REMEDY` says "re-run `--resume` or `--abort`"; `rollback.py:789-791` "moved by another actor" / `_UNRECORDED_MOVE_REASON` never mention `--release-branch`; `rollback.py:698-706` kept-verified-landing.
- `RollbackReport.render()` (`rollback.py:244`) is shared by `--abort` (`cli/commands/consolidate.py:588`) and the executor door (`executor.py:809`). Abort flow: `_dispatch_abort` (`consolidate.py:707`) → `_abort_lock_restore_clear` (`:669-704`) → `_abort_exit_keeping_record` (`:614-618`) with `_ABORT_KEPT_RECORD_MESSAGE` (`:447-449`).
- Pattern to copy: `teardown_coordination_topology(follow_up_command=...)` / `CoordTeardownKeptOnlyCopy` (`coordination/teardown.py:75-100`): the caller supplies the follow-up command.
- Recommended shape: `RefAdvanceDirtyWorktreeError` message ends at the blocker ("Commit, stash, or revert these changes in <path>."), and `RollbackReport.render(follow_up: RollbackFollowUp)` (an enum `ABORT` / `RESUME`, default `RESUME` so the executor door is unchanged in effect) appends the right next step per outcome kind. Any OTHER caller that printed `str(exc)` and relied on the consolidate advice must append its own (grep `RefAdvanceError` / `RefAdvanceDirtyWorktreeError` in `src/` and inspect each `except` that renders it; the consolidate fresh/resume paths keep a `--resume` hint).
- C-002: no exit code or refusal code changes. C-001: no new restore path; `rollback.py` remains the authority — text only.
- C-004 / R2: `ref_advance.py` is next to safe-commit, which sub-epic C (#7546) may change. Touch only the exception message.
- Rich wraps long commands: tests normalise whitespace before matching (tracer from #7544).
- WP01 already routed the PASS-anchor clears in `rollback.py` through a helper; keep them.

## Branch Strategy

Planning base / merge target: `fix/7598-coord-closeout-leftovers`.

```bash
spec-kitty agent action implement WP05 --agent claude --mission coord-closeout-leftovers-01M78FRR
```

## Subtasks & Detailed Guidance

### Subtask T018 – Red: abort remedies and a non-consolidate caller

- **Steps**:
  1. `tests/consolidation/test_abort_remedies.py`:
     - Unit: a `RollbackReport` with a NOT_RESTORED dirty-checkout outcome rendered for `ABORT` contains "re-run `spec-kitty consolidate --abort`" and not "--resume"; for `RESUME` keeps a resume hint.
     - Unit: moved-by-another-actor outcome rendered for `ABORT` names `--release-branch`.
     - Unit: kept-verified-landing rendered for `ABORT` offers `--resume` labelled as finishing teardown.
     - Unit: `str(RefAdvanceDirtyWorktreeError(...))` does not contain "consolidate".
     - CLI: drive `spec-kitty consolidate --abort` through the existing abort fixtures (`tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py`, `tests/terminus/test_rollback_door.py` builders) with a dirty tracked edit in a checkout the restore must resync; assert the remedy text (normalised whitespace) and exit code unchanged.
  2. Red on the base. Commit `test(consolidate): --abort refusals name a remedy that completes the abort (#7600, red)`.

### Subtask T019 – Neutral `RefAdvanceDirtyWorktreeError` text

- **Steps**: end the message at "Commit, stash, or revert these changes in {worktree_path}." Keep `error_code`, attributes and the dirty-entry list. Update any test that pinned the old sentence (grep tests for "resume the consolidation").

### Subtask T020 – Callers append their own remedy

- **Steps**:
  1. `rollback.py`: add the follow-up parameter to `render()` (or to `rollback_to_snapshot` → report) and per-outcome next-step lines; replace `_COORD_RESYNC_REMEDY` with a mode-aware builder.
  2. Executor door: unchanged effect (`RESUME`) — it may print the `--resume` hint as today.
  3. `cli/commands/agent/workflow.py:2255-2256`: the review fast-forward appends only "Then re-run the review." (now accurate).
  4. Inspect every other `except RefAdvanceError` that prints the message (grep) and confirm its text still tells the operator what to do; record the list in the WP history.

### Subtask T021 – Abort kept-record message by outcome

- **Steps**:
  1. `cli/commands/consolidate.py`: `_abort_exit_keeping_record` builds the message from the report's outcomes instead of the constant `_ABORT_KEPT_RECORD_MESSAGE` ("resolve the branches named above, then re-run `--abort`" stays the fallback). When every kept outcome is the verified-landing case, print the labelled `--resume` alternative.
  2. Render the report with `follow_up=ABORT` at `consolidate.py:588`.
  3. Keep complexity ≤ 15 (extract a small `_abort_next_steps(report) -> list[str]`).

## Test Strategy

```bash
.venv/bin/python -m pytest -q tests/consolidation/test_abort_remedies.py tests/consolidation/test_rollback_authority.py tests/git/test_ref_advance_resync_to_tip.py tests/terminus/test_rollback_door.py tests/terminus/test_rollback_record_rebaseline.py tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py tests/consolidation/test_single_rollback_authority.py
.venv/bin/python -m pytest -q --dist loadfile -n 8 tests/consolidation tests/git tests/specify_cli/git
.venv/bin/python -m pytest -q tests/architectural/test_destructive_op_routing.py
ruff / format --force-exclude / mypy on changed files
```

## Risks & Mitigations

- A caller that relied on the consolidate advice now prints none: T020 inventories every renderer.
- Overlap with sub-epic C on `ref_advance.py`: message-only change.

## Review Guidance

- No `--abort` path prints `--resume` except the labelled verified-landing case.
- The executor door's remedy still works for fresh/resume runs.

## Progress & Status

Event log only.
