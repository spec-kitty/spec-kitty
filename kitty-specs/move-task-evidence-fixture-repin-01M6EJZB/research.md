# Research: the eight refusals in `tests/tasks/test_move_task_git_validation_unit.py`

**Issue**: [#7057](https://github.com/spec-kitty/spec-kitty/issues/7057)
**Grounding base**: `origin/main` `9aed3a8012` (issue reported at `bec07fb57`)
**Verdict**: pre-existing red on `main`, out-of-matrix, **test-fixture staleness, not a
product defect**. The gate introduced by #6715 is the contract; the fixture predates it.

## 1. Reproduction (red on the planning base)

```bash
git worktree add --detach /tmp/wt-7057 origin/main    # 9aed3a8012
cd /tmp/wt-7057 && uv run --frozen pytest -q -p no:randomly -n0 \
  tests/tasks/test_move_task_git_validation_unit.py
# 8 failed, 7 passed
```

Failing nodes (exactly the issue's list):

```
TestMoveTaskGitValidation::test_move_to_done_with_override_reason_succeeds_when_unmerged
TestMoveTaskGitValidation::test_move_to_for_review_persists_transition_event
TestMoveTaskGitValidation::test_move_to_for_review_fails_when_event_readback_is_blocked
TestMoveTaskGitValidation::test_move_to_for_review_still_validates
TestMoveTaskGitValidation::test_move_to_done_with_staged_but_uncommitted_fails
TestMoveTaskGitValidation::test_move_for_review_blocks_when_lane_branch_has_kitty_specs_commits
TestMoveTaskGitValidation::test_move_for_review_from_worktree_keeps_commit_history_unchanged
TestMoveTaskCommitsLaneDeliverables::test_for_review_auto_commits_uncommitted_deliverables
```

Seven of the eight are refused with the same payload; the eighth
(`..._with_override_reason_succeeds_when_unmerged`) additionally asserts exit 0, so it
surfaces the refusal as a bare `assert 1 == 0`:

```
IMPLEMENTATION_MISSING: WP01 cannot move into review: no change to its owned_files in
its evidence window <planning_sha>..kitty/mission-017-test-feature-lane-a (lane-a).
Commit the work package's implementation to its owned_files (on its lane branch, or on
the target branch for a planning-artifact work package), then retry (ticked subtask
checkboxes are not shipped code).
```

## 2. Where the refusal comes from

`move-task` runs the evidence gate before the readiness decision
(`src/specify_cli/cli/commands/agent/tasks_move_task.py:1938`, deferred for the
`for_review` auto-commit arm at `:1433`/`:1415`):

- `_mt_require_implementation_evidence` (`:974`) — fires when the move crosses into
  `_REVIEW_WARD_LANES` (`for_review`, `in_review`, `approved`, `done`) from below, is not
  `--force`, and is not an owned checkout.
- `_mt_require_lane_evidence` (`:1057`) — computes the window
  `planning_commit_sha..<lane branch>`, reads its changed paths
  (`wp_evidence.evidence_paths`) and calls `wp_evidence.has_owned_change(paths, patterns)`.
- `_mt_owned_file_patterns` (`:898`) — the patterns are the **authored WP frontmatter's
  `owned_files`**, read with `read_authored_wp_frontmatter` and normalized by
  `wp_evidence.owned_patterns` (`src/specify_cli/consolidation/wp_evidence.py:111`).
- `has_owned_change` (`wp_evidence.py:165`) with an **empty** pattern tuple matches
  nothing, so the refusal is unconditional.

Introduced by #6715 (`8c5703e48f`, refined by `864f20fb9`, `998424417`, `c8383fe2d`,
#6780) and reported in the changelog as "a work package with no committed work ... is now
refused on every topology".

## 3. Why the fixture trips it

`git_repo_with_worktree` (`tests/tasks/test_move_task_git_validation_unit.py:42`):

1. Writes `kitty-specs/017-test-feature/tasks/WP01-test-task.md` with frontmatter that has
   `work_package_id`, `title`, `agent`, `shell_pid`, `subtasks` — **no `owned_files`**.
2. Writes `lanes.json` with `write_scope=("src/**",)` and records the current tip as
   `planning_commit_sha` (`write_single_lane_manifest`, `tests/lane_test_utils.py`).
3. Cuts `kitty/mission-017-test-feature-lane-a` and commits **`implementation.txt`** at
   the repository root as its "Add implementation" commit.

So the window is computable (the gate gets past
`EVIDENCE_WINDOW_UNCOMPUTABLE`) and the branch does carry a commit, but the WP owns
nothing and the deliverable is outside the lane's own `src/**` write scope: no changed
path can match. The fixture models a Mission state `finalize-tasks` cannot produce —
`finalize-tasks` requires each WP to declare `owned_files` and lanes `compute` refuses
overlap.

## 4. Judging the test (test-remediation discipline)

- The gate's behaviour is intended and covered by its own tests
  (`tests/integration/test_6715_lane_autowalk_guards.py`,
  `tests/integration/test_6715_squad_identity_and_evidence.py`,
  `tests/orchestrator_api/test_consolidate_mission_lane_evidence_6715.py`). None of them
  ask for a change.
- The 8 nodes test other guards: uncommitted/staged work, kitty-specs contamination,
  status-event persistence readback, auto-commit recovery, commit-history preservation,
  done-override. Every one of them is currently unreachable because the evidence gate
  fires first.
- Therefore the subject to fix is the **fixture**, not the gate: declare the WP's
  ownership, commit inside it, and supply the approver identity the independence gate
  requires for a done move. No skip/xfail/force, no assertion removal.

## 5. The done-override node, once the evidence gate passes

With the fixture honest, `test_move_to_done_with_override_reason_succeeds_when_unmerged`
reaches the next #6715 gate, `_mt_require_independent_approval` (`:1142`). A `done` move
is an approval; without `--agent` the hop records the placeholder `user`, so the gate
refuses with `REVIEW_NOT_INDEPENDENT: ... cannot be approved without a reviewer identity`.
That is correct too (operator ruling A, 2026-10-29): the node adds
`--agent reviewer-renata` — a named identity, as an operator would. The gate is exercised,
not bypassed. The remaining done-transition nodes use `--force`, which both gates skip by
design (ruling 3), and stay untouched.

## 6. Validation of the chosen remediation (prototype, reverted before planning)

Applied the fixture change in a scratch working tree and ran the module: **15 passed**
(was 8 failed / 7 passed), plus the single done-override node green on its own after the
`--agent` addition. The patch is re-applied as the WP's implementation commit; this
section records that the shape was verified, not the final artifact.

## 7. Overlap and supersession check

- `git log -S "IMPLEMENTATION_MISSING" -- src/` — only #6715 and its #6780 follow-ups; no
  later change relaxes the gate.
- `git log --oneline -- tests/tasks/test_move_task_git_validation_unit.py` — the last
  three touches are renames/seed-helper refactors (`67d21a78cd`, `2258a40ae8`,
  `9a01217bb8`) and the #2335 auto-commit feature (`204470a861`); none declares
  `owned_files`.
- No open issue names this file's 8 nodes, and no open PR touches the module (searched
  `gh pr list --search 7057`). #7058 (`issue-7022-test-fast-red`) closed the sibling
  `test-fast` red, not this one.
