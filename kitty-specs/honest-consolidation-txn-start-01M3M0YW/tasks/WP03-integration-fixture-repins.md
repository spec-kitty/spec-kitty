---
work_package_id: WP03
title: '#5044 integration fixture re-pins + sc007 verdict'
dependencies:
- WP01
requirement_refs:
- FR-005
- FR-006
- FR-007
planning_base_branch: issue-5111-honest-consolidation-txn-start
merge_target_branch: issue-5111-honest-consolidation-txn-start
branch_strategy: Planning artifacts for this mission were generated on issue-5111-honest-consolidation-txn-start. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5111-honest-consolidation-txn-start unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-honest-consolidation-txn-start-01M3M0YW
base_commit: 337213d98a651ad0aeae9da6af01eb0febe6d673
created_at: '2026-09-28T13:51:01.382632+00:00'
subtasks:
- T008
- T009
- T010
- T011
- T012
- T013
- T014
phase: Phase 2 - Nightly integration lane
history:
- at: '2026-09-28T13:02:22Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/integration/
create_intent: []
execution_mode: code_change
owned_files:
- tests/integration/test_merge_resume.py
- tests/integration/test_surface_translation_seam.py
- tests/integration/test_review_durability_matrix.py
- tests/integration/test_implement_review_retrospect_smoke.py
- tests/integration/test_wp_file_hash_stability.py
- tests/integration/test_merge_lane_planning_data_loss.py
- tests/integration/test_post_merge_index_refresh.py
- tests/integration/test_post_merge_unrelated_untracked.py
- tests/integration/sparse_checkout/test_merge_refresh_and_invariant.py
- tests/integration/test_merge_lane_worktree_safety.py
- tests/integration/test_merge_primary_checkout_safety.py
- tests/integration/test_coord_unprotected_lifecycle_loop.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – #5044 integration fixture re-pins + sc007 verdict

Load the `python-pedro` profile first.

**Objective**: FR-005–FR-007. Per DIRECTIVE_041, judge each test rather than git-blame: a stale fixture gets re-pinned to the current contract, and a real regression gets a product fix. Never skip, quarantine or retry. `test_sc007_in_review_to_in_progress_is_force_free` is not edited without an operator verdict.
