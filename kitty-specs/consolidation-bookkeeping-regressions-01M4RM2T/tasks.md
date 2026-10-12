# Tasks: Consolidation / done-bookkeeping regressions (#6071, #6073)

Bugfix mission, single_branch topology, direct_repo execution on
`issue-6071-consolidation-bookkeeping-regressions`. Each WP is one independently-reviewable
slice mapping to named tests; red-first reproductions are recorded in `research/`.

| WP | Slice | Cluster | Fixes (named tests) | Surface |
|----|-------|---------|---------------------|---------|
| WP01 | Diagnosis + scaffolding | — | records red-first reproductions; no product/test change | `research/`, mission docs |
| WP02 | Post-merge done-check via canonical reducer | A (FR-001/002) | `test_merge_coord_topology_1772::test_post_merge_validation_reads_in_branch_status_path` | `consolidation/done_bookkeeping.py`, `tests/consolidation/test_done_bookkeeping_seam.py` |
| WP03 | Bare-slug composed-dir teardown on resume | B (FR-003) | `test_bare_slug_coord_mission_consolidates_again_after_the_bookkeeping_commit_failed` | `consolidation/phase_teardown.py` |
| WP04 | Skip-lanes fixture realism (test-data re-pin) | C (FR-004) | `test_issue_2745_merge_skip_lanes` ×3 | `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py` |
| WP05 | Interrupted-fold dirty detection | D (FR-005) | `test_a_run_killed_inside_the_fold_...` ×2 | pre-mutation preflight (`entry_preflight`/`resume_recovery`/`preflight`) |

Dependencies: WP02–WP05 are independent of each other; all depend on WP01 (diagnosis-first).
Validation surface per WP is its named test plus the owning directory; see `plan.md` §Testing.
