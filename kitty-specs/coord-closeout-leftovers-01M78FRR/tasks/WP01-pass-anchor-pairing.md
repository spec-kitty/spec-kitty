---
work_package_id: WP01
title: PASS-anchor pairing (tidy-first)
dependencies: []
requirement_refs:
- C-001
- FR-004
planning_base_branch: fix/7598-coord-closeout-leftovers
merge_target_branch: fix/7598-coord-closeout-leftovers
branch_strategy: Planning artifacts for this mission were generated on fix/7598-coord-closeout-leftovers. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/7598-coord-closeout-leftovers unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Tidy-first enablers
history:
- at: '2026-11-12T18:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/state.py
create_intent:
- tests/consolidation/test_reconciliation_pass_pair.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/state.py
- src/specify_cli/consolidation/executor.py
- tests/consolidation/test_reconciliation_pass_pair.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – PASS-anchor pairing (tidy-first)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.
- **Report progress**: `spec-kitty agent tasks add-history WP01 --note "..."`.

---

## Objectives & Success Criteria

A **behaviour-preserving** enabler (charter Standing Order 2, tidy-first) for WP02. Today the
reconciliation PASS anchor `ConsolidationState.reconciliation_passed_target_sha` is written in six
places:

| Site | Write |
|---|---|
| `consolidation/phase_gate.py:152` (`_record_reconciliation_pass`) | set to the verified target SHA |
| `consolidation/phase_teardown.py:305` | advanced to a cleanup commit on top of the landing |
| `consolidation/executor.py:801-802` (`_report_rollback`) | restored to `anchor_before` |
| `consolidation/rollback.py:830` (`_clear_bookkeeping`) | cleared |
| `consolidation/rollback.py:904-906` (`rebaseline_after_full_restore`) | cleared |
| `consolidation/rollback.py:969` (F4 in `rollback_to_snapshot`) | cleared |

WP02 adds one paired field (`coord_tip_after_projection`) that must be cleared and restored
**with** the anchor (data-model.md invariant: non-`None` only while the anchor is non-`None`).
This WP introduces small methods on `ConsolidationState` and routes the **clear** and **restore**
sites through them, so WP02 adds the paired field in one place.

Done when:
- `ConsolidationState` exposes `clear_reconciliation_pass() -> bool` (returns whether anything changed) and `restore_reconciliation_pass(anchor: str | None) -> bool`.
- The three `rollback.py` clears and the `executor.py` restore call them.
- No behaviour change: every existing test in `tests/consolidation/` and `tests/terminus/` that touches rollback passes unchanged.

## Context & Constraints

- Spec: FR-004, C-001. Plan: IC-01. Research: `research/code-grounding.md` §7 (#7491 refinement).
- **C-001**: no new rollback or restore path. These are field writes on the record, not branch restores. `tests/consolidation/test_single_rollback_authority.py` pins callers of `rollback_to_snapshot`, `restore_branch_ref` and revert only; keep it green.
- `phase_gate.py:152` and `phase_teardown.py:305` (the two *set* sites) are left for WP02, which owns those files and adds the paired field there.
- Ownership-map leeway: the three `rollback.py` call-site edits are outside this WP's `owned_files` (WP05 owns `rollback.py`). They are three one-line replacements; record them with a one-line rationale in the WP history (`add-history`). WP05 depends on this WP, so there is no parallel edit.

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `fix/7598-coord-closeout-leftovers`
- **Merge target branch**: `fix/7598-coord-closeout-leftovers`

Execution worktrees are allocated per computed lane from `lanes.json`. Run:

```bash
spec-kitty agent action implement WP01 --agent claude --mission coord-closeout-leftovers-01M78FRR
```

## Subtasks & Detailed Guidance

### Subtask T001 – Red: unit cells for the clear/restore helper

- **Purpose**: pin the helper's contract before it exists (C-011 red-first; the commit precedes the implementation commit).
- **Steps**:
  1. Create `tests/consolidation/test_reconciliation_pass_pair.py`, marked `unit` / `fast` like its neighbours (check `tests/consolidation/test_constants_seam.py` for the marker idiom).
  2. Cells:
     - `clear_reconciliation_pass()` on a state with an anchor sets it to `None` and returns `True`; on a state without returns `False`.
     - `restore_reconciliation_pass("abc")` on a state at `"def"` sets `"abc"` and returns `True`; same value returns `False`; `None` clears.
     - A state round-trips through `to_dict` / `from_dict` unchanged after each call.
  3. Run it: it must fail with `AttributeError` (the methods do not exist). Commit `test(consolidation): pin one clear/restore door for the PASS anchor (red)`.
- **Files**: `tests/consolidation/test_reconciliation_pass_pair.py`.

### Subtask T002 – Add the helper to `ConsolidationState`

- **Steps**:
  1. In `src/specify_cli/consolidation/state.py`, on the `ConsolidationState` dataclass (field `reconciliation_passed_target_sha` at ~line 267), add the two methods with docstrings citing #5021 (the anchor) and this Mission (#7491 pairing in WP02).
  2. Keep them pure field mutators: no `save_state`, no git. Callers persist as they do today.
  3. Do not add `__all__` changes unless the module declares one (it does not need to: `src/specify_cli` is outside the `__all__` convention).
  4. T001 cells go green.

### Subtask T003 – Route the clear and restore sites through the helper

- **Steps**:
  1. `rollback.py:830` (`_clear_bookkeeping`): `state.clear_reconciliation_pass()`.
  2. `rollback.py:904-906`: `if state.clear_reconciliation_pass(): changed = True`.
  3. `rollback.py:969`: `state.clear_reconciliation_pass()`.
  4. `executor.py:801-803`: `if run.state.restore_reconciliation_pass(anchor_before): save_state(...)`.
  5. Grep to confirm no other clear/restore writes remain: `grep -rn "reconciliation_passed_target_sha\s*=" src/` should list only `phase_gate.py` and `phase_teardown.py` (the set sites).
- **Validation**: run the suites below; they must pass unchanged.

## Test Strategy

```bash
.venv/bin/python -m pytest -q tests/consolidation/test_reconciliation_pass_pair.py tests/consolidation/test_single_rollback_authority.py tests/consolidation/test_rollback_authority.py tests/terminus/test_rollback_record_rebaseline.py tests/terminus/test_rollback_door.py
.venv/bin/ruff check src/specify_cli/consolidation/state.py src/specify_cli/consolidation/executor.py src/specify_cli/consolidation/rollback.py tests/consolidation/test_reconciliation_pass_pair.py
.venv/bin/ruff format --check --force-exclude <same files>
.venv/bin/mypy src/specify_cli/consolidation/state.py src/specify_cli/consolidation/executor.py src/specify_cli/consolidation/rollback.py
```

## Risks & Mitigations

- A silent behaviour change in the tidy step: the diff must be the method extraction only.
- `executor.py` currently saves only when the value changed; keep that.

## Review Guidance

- Verify red→green: T001's commit fails on the base, passes on the final commit.
- Verify no change in semantics at each of the four sites, and that the rollback AST pin is green.
- The `rollback.py` leeway edit is recorded in the WP history.

## Progress & Status

Progress lives in the status event log. Use `spec-kitty agent tasks add-history`, `move-task`, `status`.
