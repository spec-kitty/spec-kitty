# Slice B red-proofs — implementation follow-through (#5353)

Worktree: `/home/stijn/Documents/_code/SDD/fork/SHADOW_CLONES/spec-kitty_TWO/.claude/worktrees/agent-a65b1745117eb5228`
Branch: `worktree-agent-a65b1745117eb5228` (fast-forwarded onto `issue-5353-consolidation-test-quality`, then 6 commits on top)

All planted breaks below were applied to `src/`, tested, then reverted with `git checkout -- src/` before commit; `git diff --stat src/` was empty at every commit.

| Test | Planted break | Current (pre-fix) test result | Fixed test on break | Fixed test on real code | Verdict change |
| --- | --- | --- | --- | --- | --- |
| `test_merge_state_authority.py::TestRollbackTargetAfterFailedReconciliation::test_guard_skips_when_target_ref_unresolvable` | `executor.py::_rollback_target_after_failed_reconciliation`: `if not current_sha or current_sha == pre_merge_sha:` → `if current_sha is None or current_sha == pre_merge_sha:` | GREEN (vacuous — only asserted "must not raise") | RED (`ghost-branch` got created, `assert ghost_lookup.returncode != 0` failed) | GREEN (30 passed) | none — FIX as specified |
| `test_wp_attribution.py::test_merge_commit_outside_windows_is_not_flagged` | `wp_attribution.py::_canceled_content_walk`: removed `if merge_cache[sha]: continue` | GREEN (vacuous — original side commit only touched an already-exempt bookkeeping path and sat on the merge's 2nd parent) | RED (`Unattributable`/`COMMIT_OUTSIDE_WINDOWS` on the evil-merge's own `merge_only.py`) | GREEN (45 passed) | none — FIX as specified (evil-merge construction) |
| `test_wp_attribution.py::test_dependency_lane_merged_after_work_began_is_off_spine_without_an_anchor` (renamed from `..._needs_the_dependency_anchor`) | `wp_attribution.py::resolve_canceled_wp`: `first_parent_commits_in_range(...)` → `commits_in_range(...)` | RED already on the PRE-rename test (confirms rename-only, no new oracle needed) | RED (same failure mode, oracle unchanged) | GREEN (45 passed) | none — FIX as specified (rename + strengthened assertion) |
| `test_merge_rollback_resume_coherence.py::test_direct_on_target_refuse_originates_from_precondition_not_missing_lanes` | `executor.py::_assert_mission_terminal_ready`: inserted `return` as first statement | GREEN (vacuous — a later refusal, "Post-merge status validation failed", still satisfied the loose `BaseException`/non-zero-exit/WP-id-present oracle) | RED (`"Mission is not merge-ready" in printed` failed — proves the merge proceeded past the removed precondition instead of refusing there) | GREEN (4 passed) | none — FIX as specified |
| `test_terminus_absent_snapshot_precondition_fold.py::test_wp_declared_but_absent_from_snapshot_refuses_merge_not_vacuous_pass` | `executor.py::_assert_mission_terminal_ready`: `mission_terminal_acceptability(relevant, expected_wp_ids=run.all_wp_ids)` → `mission_terminal_acceptability(relevant)` | RED already (confirms the behavioural core — folding an absent WP into `missing` — is real, not vacuous) | RED (same break, precise `"missing review approval: WP01"` oracle also fails) | GREEN (1 passed) | none — verdict's own framing confirmed: FIX is specificity-only (narrowed `pytest.raises`, exact message, dropped noqa), not a new oracle |
| `test_squash_target_newer_planning_3942.py::test_squash_merge_preserves_target_newer_planning_files` | none (structure-only per verdict — stale `lanes/merge.py:635` / `-X theirs` file:line pin in assertion messages) | n/a (oracle unchanged, byte-equality of target-newer files) | n/a | GREEN (message text only, still passes) | none — message text change only |
| `test_merge_driver_goldens.py::test_every_registered_config_key_resolves_through_replay[*]` (**RETIRED**) | `git_probes.py::_resolve_registered_driver_callable`: `driver = MERGE_DRIVER_BODIES.get(match.group(1))` → `MERGE_DRIVER_BODIES.get("merge-driver-traces")` | GREEN — all 6 parametrized cases passed (`assert callable(driver)` is satisfied by the WRONG driver body) — proves vacuity | n/a (deleted) | Covering guard `test_in_process_leg_matches_golden[*]` went RED for all 5 non-traces commands (14 failed, 11 passed; `traces` cases stayed green since the break always returns the traces body) | RETIRE as specified — covered by `test_merge_driver_goldens.py::test_in_process_leg_matches_golden` |

## Full per-file test counts (after revert, real code)

- `tests/consolidation/test_merge_state_authority.py`: 30 passed
- `tests/consolidation/test_wp_attribution.py`: 45 passed
- `tests/consolidation/test_merge_rollback_resume_coherence.py`: 4 passed
- `tests/consolidation/test_terminus_absent_snapshot_precondition_fold.py`: 1 passed
- `tests/consolidation/test_squash_target_newer_planning_3942.py`: 4 passed
- `tests/consolidation/test_merge_driver_goldens.py`: 53 passed (was 54 before the retirement — one vacuous parametrized-by-6 test removed)

Combined run of all six files together: 137 passed.

`ruff check` and `ruff format --check` both pass with zero issues on every touched file. No `# noqa` or `# type: ignore` added. No WP/FR/T ids in new test names.
