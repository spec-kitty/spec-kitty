---
description: "Work packages for cas-landed-branch-delete-01M6P3ER (#7212)"
---

# Work Packages: Compare-and-swap branch delete for `doctor workspaces --prune`

**Inputs**: `kitty-specs/cas-landed-branch-delete-01M6P3ER/` — spec.md, plan.md, research.md, data-model.md, contracts/guard-branch-delete-cas.md, quickstart.md
**Tests**: Required (red-first per charter ATDD-first; the defect is a data-loss race).

**Organization**: Subtasks (`Txxx`) roll up into work packages (`WPxx`). Subtasks are reference rows; record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Dependency graph

```
WP01 (guard CAS + prune binding + gate pin + docs)
```

One work package: the change is a single coherent safety fix across four
coupled surfaces (guard primitive → prune caller → architectural pin → docs).
Splitting it would make each half revertible into a green-but-unsafe state.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first test: a branch moved inside the guarded delete is kept (plus same-fixture positive control) | WP01 | |
| T002 | `guarded_branch_delete(..., expected_tip=...)`: require it under `LANDED_INTENT`, CAS via `ref_advance.delete_branch_ref`, typed refusals | WP01 | |
| T003 | Guard tests: matching tip deletes, stale tip refuses, missing tip `ValueError`, checked-out refusal | WP01 | |
| T004 | `_delete_landed_branch` passes `verdict.tip` and maps the guard codes onto `BRANCH_MOVED` / `BRANCH_IN_OTHER_WORKTREE`; module docstring updated | WP01 | |
| T005 | Routing gate: pin that the LANDED caller passes `expected_tip`, with a non-vacuity planted-caller proof | WP01 | |
| T006 | Docs: `--prune` paragraph in the landing runbook; changelog fragment | WP01 | |

---

## Work Package WP01: Compare-and-swap landed branch delete (Priority: P1)

**Goal**: The prune's branch delete succeeds only while the branch still holds the assessed tip; a branch that moves in the window is kept and reported.
**Independent Test**: Real-git prune fixture in which the branch moves between the prune's tip read and the guard's delete; the branch survives at its new tip with `BRANCH_MOVED`, while the same fixture without the move deletes the branch.
**Prompt**: `tasks/WP01-cas-landed-branch-delete.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, NFR-001, NFR-002, NFR-003, C-002, C-003, SC-001, SC-002, SC-003, SC-004

### Summary

The landed prune proved a tip absorbed, then deleted the branch through
`git branch -D` after a separate tip read. The delete is now bound to the
assessed tip: the guard takes an expected tip (mandatory under `LANDED_INTENT`)
and deletes through `ref_advance.delete_branch_ref`'s single
`git update-ref -d <ref> <expected>` compare-and-swap. The prune passes
`verdict.tip` and keeps its existing refusal vocabulary. Other intents and the
`git branch -D` path are untouched.

### Included Subtasks

- T001 Red-first test: a branch moved inside the guarded delete is kept (plus same-fixture positive control)
- T002 `guarded_branch_delete(..., expected_tip=...)`: require it under `LANDED_INTENT`, CAS via `ref_advance.delete_branch_ref`, typed refusals
- T003 Guard tests: matching tip deletes, stale tip refuses, missing tip `ValueError`, checked-out refusal
- T004 `_delete_landed_branch` passes `verdict.tip` and maps the guard codes onto `BRANCH_MOVED` / `BRANCH_IN_OTHER_WORKTREE`; module docstring updated
- T005 Routing gate: pin that the LANDED caller passes `expected_tip`, with a non-vacuity planted-caller proof
- T006 Docs: `--prune` paragraph in the landing runbook; changelog fragment

### Implementation Sketch

1. T001 first and red: wrap `landed_worktrees.guarded_branch_delete` so it moves
   the branch to a fresh `commit-tree` commit (reached by no other ref) before
   delegating; assert the branch survives and the outcome is `BRANCH_MOVED`.
2. T002: `expected_tip` keyword; `ValueError` for `LANDED_INTENT` without it;
   compare, keep-record at the expected tip, then `delete_branch_ref`; map
   `RefDeleteMismatchError`/`RefDeleteCheckedOutError`/`RefDeleteError` to
   `DestructiveOpRefused`. Keep the `git branch -D` path for the other intents.
3. T003: guard tests in the real-git style of `test_delete_branch_ref.py`.
4. T004: pass `expected_tip=tip`; map the new codes; update the module docstring
   paragraph that documents the non-atomic window.
5. T005: extend the routing gate's AST pin (no allowlist) and its planted proof.
6. T006: one runbook clause and the fragment (issue-number filename until the PR
   number exists, then rename).

### Parallel Opportunities

None: a single lane, and T001 must land red before T002/T004.

### Dependencies

None (root). The Mission base is the open #7196 branch (C-001).

### Risks

- The keep-record is written before the CAS; a refused CAS can leave the
  create-only record behind. Documented as harmless in the guard docstring.
- `delete_branch_ref` refuses a checked-out branch; the prune's pre-check makes
  that rare, but the guard must still map it to a typed refusal.
- Do not change `ref_advance.delete_branch_ref` or any other caller's behaviour.
