---
affected_files: []
cycle_number: 1
mission_slug: move-task-executor-seam-lanes-01M43FAG
reproduction_command:
reviewed_at: '2026-10-04T13:38:46Z'
reviewer_agent: reviewer-renata
wp_id: WP03
---

# WP03 review (reviewer-renata, opus): REJECT

Verified: 21 moved bodies AST-identical modulo lazy imports; T009 args identical (explicit operation=None equals default); no dead intercepts; `_tasks.` bridges preserved; no import cycle; 10-file architectural battery 415 passed; ruff/format/mypy clean.

Required:
1. Add `test_review_lock_released_after_emits` to tests/specify_cli/cli/commands/agent/test_tasks_move_task_executor.py: drive `_mt_execute`, assert the review-lock release runs after the emits/persist, and is not reached when an emit raises.
2. Cite existing coverage for verdict revert on emit failure: test_move_task_durability.py::test_failed_transition_emit_is_reverted_leaving_no_committed_verdict, test_owned_checkout_move_task.py::test_owned_approval_emit_failure_compensates_selected_verdict, integration/review/test_verdict_save_topologies.py::test_compensation_failure_is_loud_and_leaves_only_noncurrent_history.
