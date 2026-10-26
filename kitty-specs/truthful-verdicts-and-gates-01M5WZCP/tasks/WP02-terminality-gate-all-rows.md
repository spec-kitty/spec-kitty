---
work_package_id: WP02
title: Terminality gate evaluates every row it reports on
dependencies: []
requirement_refs:
- FR-007
- FR-008
- FR-009
- FR-010
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: issue-6652-verdict-gate-truthfulness
merge_target_branch: issue-6652-verdict-gate-truthfulness
branch_strategy: Planning artifacts for this mission were generated on issue-6652-verdict-gate-truthfulness. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6652-verdict-gate-truthfulness unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-truthful-verdicts-and-gates-01M5WZCP
base_commit: b39d1918d2d382be3cbe9e87b6ec90f4c5de8137
created_at: '2026-10-26T21:53:33.730627+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 1 - Defect fixes
history:
- at: '2026-10-26T21:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/tasks/issue_matrix_approval.py
create_intent:
- tests/policy/test_merge_gates_issue_matrix_6653.py
execution_mode: code_change
owned_files:
- src/specify_cli/tasks/issue_matrix_approval.py
- src/specify_cli/policy/merge_gates.py
- tests/policy/test_merge_gates_issue_matrix_6653.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Terminality gate evaluates every row it reports on

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objective

Under `merge_gates.mode: block`, the terminality gate prints "No unresolved (in-mission/unknown) issue-matrix rows" and lands a Mission that still has an `in-mission` row, when that row's issue is not a cited gating reference (#6653). With zero gating references it skips the matrix entirely. Make the gate evaluate every row it reports on.

Operator decision: at done, with zero gating references but a matrix present, evaluate the whole matrix (in-mission and unknown/invalid rows fail). No matrix → PASS that says so.

## Branch Strategy

Planning branch and merge target: `issue-6652-verdict-gate-truthfulness`; worktree per computed lane:

```bash
spec-kitty agent action implement WP02 --agent claude --mission truthful-verdicts-and-gates-01M5WZCP
```

## Subtasks

### T006 — Red-first tests

New `tests/policy/test_merge_gates_issue_matrix_6653.py`, reusing the fixtures/helpers of `tests/policy/test_merge_gates_issue_matrix.py` (`TestTerminalVerdictEnforcement`, `TestZeroGatingReferencesNeverProbesCoordination`). Cases:

1. Spec cites `#1234` (fixed); matrix also has `#5678: in-mission` → terminality gate FAIL naming `#5678`; `_issue_matrix_approval_blocker(target_lane=Lane.DONE)` returns a message naming it.
2. Same matrix at `target_lane=Lane.APPROVED` → no blocker (ratchet).
3. Spec cites nothing; matrix has `#5678: in-mission` → gate FAIL; blocker at DONE returns a message.
4. Spec cites nothing; no matrix → gate PASS whose details mention no gating references and no matrix; coord Mission without matrix does not FAIL on the probe (keep the existing #5222 F1 test green).
5. One-digit cited `#8` row in-mission → FAIL (the detector skips one-digit refs; the all-rows rule catches it).

### T007 — All rows at done

`issue_matrix_approval._issue_matrix_in_mission_rows` / `_issue_matrix_evaluation`: collect in-mission rows over every row; the blocker already clears the list when `target_lane != Lane.DONE`. Update the docstrings (classification decides requirement; verdict decides resolution for every existing row).

### T008 — Zero-reference evaluation in the blocker

`_issue_matrix_approval_blocker`: when there are no gating refs, return `None` unless `target_lane == Lane.DONE` and `issue_matrix_artifact_present(feature_dir, content=matrix_content)`; then evaluate as normal (missing issues is empty). Keep complexity ≤ 15.

### T009 — Consolidation gate zero-reference arm

`policy/merge_gates.py` terminality gate: with no gating refs, resolve the partition inside a guard; `IssueMatrixRefReadError`, `CoordinationWorktreeUnmaterialized`, `ActionContextError` there mean "no matrix readable" → PASS with details `No gating issue references and no issue matrix — nothing to enforce`. When a matrix source exists, run the blocker. Keep the existing PASS text only for a real all-rows pass.

## Validation

```bash
uv run --frozen pytest -q tests/policy/test_merge_gates_issue_matrix_6653.py tests/policy/test_merge_gates_issue_matrix.py tests/policy/ tests/tasks/
grep -rl "_issue_matrix_approval_blocker\|issue_matrix_verdict_terminality" tests/ | xargs uv run --frozen pytest -q
```

## Definition of Done

- T006 committed red first; green after.
- `in-mission` still accepted at `approved`.
- ruff/format/mypy clean; no suppressions.

## Reviewer guidance

Check the zero-reference coord case does not probe-fail; check the PASS text never claims rows it skipped.
