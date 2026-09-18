---
affected_files: []
cycle_number: 1
mission_slug: mission-handle-resolution-consistency-01M2TPWG
reproduction_command: spec-kitty agent tasks move-task WP03 --to approved --mission mission-handle-resolution-consistency-01M2TPWG
reviewed_at: '2026-09-18T19:18:42Z'
reviewer_agent: user
wp_id: WP03
---

Approved by user: Review passed: explicit unmatched --mission on plan (setup-plan) and tasks (check-prerequisites) now emits canonical 'Mission not found: <handle>' from the WP01 mission_not_found_message seam. Branch keys on explicit-handle-present + shared _NOT_FOUND_HANDLE_MARKER (not on mission count); ambiguous-handle NOT relabeled (test_ambiguous_handle_is_not_treated_as_not_found). No-handle multi-mission disambiguate + zero-mission payloads byte-unchanged; pinned tests green (test_mission_feature_resolution.py + test_agent_feature.py). available_missions stays a string list. Tests proven real red-first (5 new-behavior tests fail on pre-fix source, 4 regression guards stay green). Blast radius 2077 passed/0 failed; ruff check+format clean on diff; mypy clean on diff (sole error is pre-existing _read_feature_meta no-any-return, base-identical). mission_setup_plan.py/mission_check_prerequisites.py byte-unchanged; their base ruff-format drift is not a WP03 defect.
