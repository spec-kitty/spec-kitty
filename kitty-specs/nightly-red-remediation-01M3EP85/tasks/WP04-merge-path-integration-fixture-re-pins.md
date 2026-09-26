---
work_package_id: WP04
title: Merge-path integration fixture re-pins
dependencies:
- WP03
requirement_refs:
- FR-002
- FR-003
- FR-005
planning_base_branch: claude/lucid-ptolemy-fjtzep
merge_target_branch: claude/lucid-ptolemy-fjtzep
branch_strategy: Planning artifacts for this mission were generated on claude/lucid-ptolemy-fjtzep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/lucid-ptolemy-fjtzep unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
- T016
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
- tests/integration/test_post_merge_index_refresh.py
- tests/integration/test_post_merge_unrelated_untracked.py
- tests/integration/sparse_checkout/test_merge_refresh_and_invariant.py
- tests/integration/test_merge_resume.py
- tests/integration/test_merge_lane_worktree_safety.py
- tests/integration/test_merge_primary_checkout_safety.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Merge-path integration fixture re-pins

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

- All 13 merge-path tests in these 6 files pass. This includes `TestMergeResumeBounded::test_resume_completes_within_30s_budget` under `SPEC_KITTY_RUN_PERFORMANCE=1`.

## Context & Constraints

- Product changes: 6545dc532f (#5001 reconciliation claim + FR-012 marker), 7da1750ebb (#4982 resume anchor integrity), b8878872a9 (#4764 merge-ready precondition, bisected).
- Stubs are allowed ONLY where the test's subject is not the reconciliation gate, following the 26be43c804 precedent.

## Subtasks & Detailed Guidance

### Subtask T012 – Index-refresh tests (3)

- **Steps**: Add `patch("specify_cli.merge.executor._capture_reconciliation_claim")` and `patch("specify_cli.merge.executor._phase_reconcile_before_teardown")` to the shared patch stack, with the 26be43c804 comment.

### Subtask T013 – Untracked-tolerance tests (2)

- Same as T012 in `test_post_merge_unrelated_untracked.py`.

### Subtask T014 – Sparse refresh/invariant tests (2)

- Same as T012 in `sparse_checkout/test_merge_refresh_and_invariant.py`. The invariant-ordering assertion must still observe the real order of refresh and invariant.

### Subtask T015 – Resume tests (4 including perf)

- **Tests**: `test_merge_resume.py` — `TestMergeResumeIdempotence::test_resume_full_state_is_no_op_for_mark_done`, `TestMergeResumeAfterInterruption::test_resume_skips_completed_marks_remaining`, `TestMergeResumeBounded::test_resume_completes_all_wps`, and `test_resume_completes_within_30s_budget`.
- **Steps**:
  - Preferred: seed a post-fix state. Call `write_post_fix_marker(repo, mission_id)` and give the manifest a real `mission_slug`/`mission_id`.
  - If the harness fakes git so the claim cannot be built, append the two reconciliation stubs plus a no-op `_enforce_resume_anchor_integrity` **at the END of `_patches()`**, because inserting earlier shifts the positional `mocks[10..12]` indices.
  - Keep a comment naming #5001 FR-012 and #4982.

### Subtask T016 – Checkout-safety fixtures seed approval (cause C3)

- **Tests**: `test_merge_lane_worktree_safety.py::test_clean_lane_worktree_removed_as_today` and `test_merge_primary_checkout_safety.py::test_clean_on_target_checkout_merge_completes_unchanged`.
- **Steps**: Seed WP01 approved through the status event log, as `_seed_wp_approved` does in `test_merge_lane_planning_data_loss.py`. Copy the minimal helper locally and cite b8878872a9 (#4764).

## Test Strategy

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/integration/test_post_merge_index_refresh.py tests/integration/test_post_merge_unrelated_untracked.py tests/integration/sparse_checkout/test_merge_refresh_and_invariant.py tests/integration/test_merge_resume.py tests/integration/test_merge_lane_worktree_safety.py tests/integration/test_merge_primary_checkout_safety.py -q
SPEC_KITTY_RUN_PERFORMANCE=1 .venv/bin/python -m pytest -m performance tests/integration/test_merge_resume.py -q
```

## Risks & Mitigations

- Positional mock indices in `test_merge_resume.py`: append-only changes to `_patches()`.

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
