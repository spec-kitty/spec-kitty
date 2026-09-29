# WP02 red proofs (#5345): unstub gates in legacy harnesses

Protocol: plant a break in production source (scratch edit, one line), run the
file -> must FAIL; `git checkout src` -> must PASS. Targeted single-file runs only.

## 1. tests/integration/test_post_merge_unrelated_untracked.py  (commit 95eaba96)

Replaced a 23-positional-patch harness (incl. bake + teardown-reconciliation stubs) with the real-git terminus coord-mission fixture and real CLI.

| Planted break (production) | RED result | GREEN (reverted) |
|---|---|---|
| `src/specify_cli/consolidation/git_probes.py::_classify_porcelain_lines`: `continue  # untracked files ...` -> `pass` (untracked no longer tolerated) | 4 failed, 2 passed: `test_untracked_worktrees_dir_dropped`, `test_mixed_untracked_and_tracked`, `test_merge_succeeds_with_untracked_worktrees_and_tmp`, `test_merge_aborts_on_unrelated_tracked_change` | 6 passed |
| same function: `offending.append(line)` -> `pass` (tracked divergence never offends) | 3 failed, 3 passed: `test_tracked_unrelated_modification_is_offending`, `test_mixed_untracked_and_tracked`, `test_merge_aborts_on_unrelated_tracked_change` | 6 passed |

## 2. tests/specify_cli/acceptance/test_acceptance_cores.py  (commit 85318284)

`test_negative_invariants_enforced_when_mutate_true` stubbed `locked_reread_splice_and_write` and asserted `enforce_calls and write_calls`. Now a real `acceptance-matrix.json`, real invariant command, real locked seam; asserts persisted result + verdict on disk (2 parametrized cases).

| Planted break | RED | GREEN |
|---|---|---|
| `src/specify_cli/acceptance/gates_core.py`: `acc_matrix.negative_invariants = enforce_negative_invariants(...)` -> `pass` | 2 failed, 45 passed (both `test_negative_invariants_enforced_and_persisted_when_mutate_true[...]` cases) | 47 passed |

## 3. tests/cli/commands/test_merge_status_commit.py  (commit 37022e89)

Removed `test_safe_commit_is_called_with_correct_files`, `test_merge_commits_baseline_merge_commit_metadata`, `test_safe_commit_called_before_worktree_removal` (all ~25 patches: reconciliation, bake, gates, integrate, `commit_merge_bookkeeping`; asserted mock call args). Their contracts are covered by `TestRealMergeCommitsBookkeeping` (3 tests, one module-scoped real `consolidate` on the terminus coord mission, oracle = `git show <target>:...` after real teardown).

| Planted break | RED | GREEN |
|---|---|---|
| `src/specify_cli/consolidation/executor.py::_phase_commit_and_assert`: `has_bookkeeping_changes = _paths_have_status_changes(...)` -> `= False` (bookkeeping commit never lands) | 2 failed, 5 passed, 3 errors: the 3 `TestRealMergeCommitsBookkeeping` tests ERROR in the `real_merge` fixture (real merge exits non-zero: "Post-merge baseline validation failed ... baseline_merge_commit is missing from committed meta.json"); also `TestDoneEventsCommittedToGit` x2 fail | 10 passed |

Note: the red for this file arrives through the fixture precondition (`returncode == 0`), because production fails closed on the missing bookkeeping commit; the per-test git-show assertions are the oracle in the green path and the fail-closed gate is what trips first when the break is planted.

## Honest note on remaining stubbing

`tests/cli/commands/test_merge_status_commit.py` still contains ExitStack/`patch` harnesses in `TestDoneEventsCommittedToGit::test_done_events_committed_to_git` and `::test_modern_coord_done_events_land_on_target_history` (reconciliation-claim, reconcile-before-teardown, lane consolidation, integrate, stale-assertion/merge-gates/policy, run_command, has_remote stubs; the latter also stubs the mission-number bake). These are outside the three sites named by T009 (:203, :322, :460), do assert on real git state (done events in target history) and went red under the planted break above, but they do not exercise those gates for real. They are the next candidates for unstubbing (the real-merge fixture now makes that cheap). `TestMergeDoneTransitions::test_mark_wp_merged_done_uses_lightweight_emit_path` still asserts on a mock (`emit_status_transition_transactional`) by design (call-shape contract).
