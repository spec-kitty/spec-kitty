---
work_package_id: WP01
title: Non-merge integration fixture re-pins
dependencies: []
requirement_refs:
- FR-001
- FR-006
- FR-007
planning_base_branch: claude/lucid-ptolemy-fjtzep
merge_target_branch: claude/lucid-ptolemy-fjtzep
branch_strategy: Planning artifacts for this mission were generated on claude/lucid-ptolemy-fjtzep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/lucid-ptolemy-fjtzep unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-red-remediation-01M3EP85
base_commit: 9810f2cfa014b77704d58b99c93a915717d7f6ba
created_at: '2026-09-26T11:14:16.326917+00:00'
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Remediation
history:
- at: '2026-09-26T11:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/integration/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/integration/test_surface_translation_seam.py
- tests/integration/test_coord_unprotected_lifecycle_loop.py
- tests/integration/test_review_durability_matrix.py
- tests/integration/test_implement_review_retrospect_smoke.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Non-merge integration fixture re-pins

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`). Address all feedback before completing.

---

## Objectives & Success Criteria

- The two coordination-seam tests assert the ADR 2026-09-24-2 fail-closed contract instead of the retired fallback to the primary checkout.
- The three arbiter-override review-durability tests pass. A new negative cell proves the #4758 lanes.json guard still refuses without a manifest.
- The retrospect smoke test passes with a causally seeded rework history.

## Context & Constraints

- Spec FR-001, FR-006, FR-007; research R-1.
- Product changes: 2fd7eabf01 (#4959, ADR `docs/adr/3.x/2026-09-24-2-coord-read-fail-closed.md`), 788db8ffb4 (#4758/#4786), f33a70fb6c (spec-kitty-events 10.4, events#69).
- Do NOT change product code. These are stale fixtures (Standing Order 4: judge the test, stale → re-pin).

## Subtasks & Detailed Guidance

### Subtask T001 – Surface-seam unmaterialized test

- **Purpose**: `test_unmaterialized_coord_resolves_primary_and_stamps_primary` (~line 162) pins the retired #1718 leniency.
- **Steps**: Rename it to `test_unmaterialized_coord_raises_fail_closed`. Assert `pytest.raises(CoordinationWorktreeUnmaterialized)` from `resolve_artifact_surface`, and check `error_code == "COORDINATION_WORKTREE_UNMATERIALIZED"`, mirroring the DELETED-branch sibling test in the same file. The docstring cites the ADR and 2fd7eabf01.
- **Validation**: The test passes. Reverting 2fd7eabf01's raise would make it fail.

### Subtask T002 – Guard4 split-brain unmaterialized test

- **Purpose**: `TestGuard4NoSplitBrain::test_gate_read_surface_equals_issue_matrix_authority_unmaterialized` (~line 239) expects both reads to agree on PRIMARY.
- **Steps**: Assert that `resolve_artifact_surface(ISSUE_MATRIX)` raises. Also check whether the gate read (`resolve_feature_dir_for_mission`) still returns PRIMARY silently. If it does, keep an assertion that documents the current behaviour and record it as a residual split-brain follow-up in the mission tracer notes. Do not fix it here.

### Subtask T003 – Arbiter fixture lanes.json + negative cell

- **Steps**:
  - In `_seed_arbiter_fixture` (~lines 924-982), call `_write_lanes_json(feature_dir, mission, wp_id)` before `return feature_dir`, as `_seed_fixture` does (~line 287).
  - Add `test_arbiter_override_without_lanes_json_is_refused_by_move_guard`. It seeds the arbiter fixture, deletes `lanes.json`, runs the same override command, and asserts a non-zero exit whose output names `lanes.json is absent`.

### Subtask T004 – Retrospect smoke causal rework

- **Steps**: At ~lines 120-135, after the rejection event, append the rework transitions `planned→claimed→in_progress→for_review→in_review` with strictly increasing timestamps. Then make the approval `from_lane=Lane.IN_REVIEW`. A comment cites events#69: a forward event whose `from_lane` does not follow from the preceding rollback is dropped as stale.

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/integration/test_surface_translation_seam.py tests/integration/test_coord_unprotected_lifecycle_loop.py tests/integration/test_review_durability_matrix.py tests/integration/test_implement_review_retrospect_smoke.py -q
```

## Risks & Mitigations

- Weakening the Guard4 intent: keep its split-brain assertion meaningful by asserting that the authority read refuses.

## Review Guidance

- Each re-pin cites its product change. No `xfail` or `skip`. The negative cell really exercises the guard.

## Branch Strategy

- **Strategy**: single_branch mission; the execution workspace is resolved per computed lane from `lanes.json`.
- **Planning base branch**: `claude/lucid-ptolemy-fjtzep`
- **Merge target branch**: `claude/lucid-ptolemy-fjtzep`

## Definition of Done

- Every listed test passes locally.
- No test is skipped, xfailed, deleted or retried (C-001).
- `ruff check` and `ruff format --check` are clean on the touched files.
- Every re-pin carries a docstring or comment citing the product change that moved the contract.

## Activity Log

- 2026-09-26T11:30:00Z – system – Prompt created.
