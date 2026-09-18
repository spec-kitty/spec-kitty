---
affected_files: []
cycle_number: 1
mission_slug: mission-handle-resolution-consistency-01M2TPWG
reproduction_command: spec-kitty agent tasks move-task WP04 --to approved --mission mission-handle-resolution-consistency-01M2TPWG
reviewed_at: '2026-09-18T19:25:02Z'
reviewer_agent: user
wp_id: WP04
---

Approved by user: Review passed: FR-004/FR-005 met. Fresh (merge.py:678) + resume (_dispatch_resume:429) gate emits canonical 'Mission not found: <handle>' via WP01 seam BEFORE lanes-load/no-state checks. Gate confined to two live callers via new _resolved_mission_dir_exists helper — NOT in shared _resolve_slug_or_exit, NOT in _dispatch_abort; resolve.py::_resolve_mission_slug untouched (raw slug on miss). Abort tolerance PROVEN: test_abort_unknown_handle_stays_tolerant exits 0 non-raising in both green and gate-reverted runs. 'not resume' guard protects resume-adopts-state-slug (that test still green). Red-first genuine: reverting gate reds fresh+resume with misleading downstream msgs. Blast-radius edit test_merge_preflight_mission_branch.py stubs _resolved_mission_dir_exists->True in dry-run harness (legit: harness mocks collaborators). test_executor_coverage.py unmodified. tests/merge/ 746 passed; ruff/format/mypy clean; C901<=15.
